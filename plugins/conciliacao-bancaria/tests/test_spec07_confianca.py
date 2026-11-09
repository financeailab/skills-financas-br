# -*- coding: utf-8 -*-
"""SPEC-07 — confianca do motor. STDLIB-PURA (CI sem requirements).
  #4 match exato AMBIGUO (2+ candidatos de mesmo valor sem identificador que desempate)
     -> Lancamento.ambiguo=True + resumo.conciliados_ambiguos; com identificador -> False.
  #3 jornada `pasta` fecha a amarracao por conta quando ha saldo-razao.txt (+ LEDGERBAL do OFX);
     sem o arquivo -> nao calcula, mas nao crasha.

Rodar:  python tests/test_spec07_confianca.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import conciliar                                  # noqa: E402
from reconcile import match_banco, resumo_privado  # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _ext(d, v, desc="", doc=None, ident=None, cnpj=None):
    return {"data": d, "valor": Decimal(v), "doc": doc, "descricao": desc,
            "contraparte": desc, "cpf_cnpj": cnpj, "identificador": ident}


def _raz(d, v, nome="", doc=None, ident=None, cnpj=None):
    return {"data": d, "valor": Decimal(v), "doc": doc, "identificador": ident,
            "contraparte": nome, "cpf_cnpj": cnpj, "descricao": nome, "lote": None}


# ---------------------------------------------------------------------------
# #4 — ambiguidade de match exato
# ---------------------------------------------------------------------------

@caso("#4 dois razoes de mesmo valor/janela SEM identificador -> CONCILIADO ambiguo")
def _():
    D = date(2026, 1, 2)
    ext = [_ext(D, "-100.00", "DEBITO BANCO")]
    raz = [_raz(D, "-100.00", "FORN A"), _raz(D, "-100.00", "FORN B")]
    c = match_banco(ext, raz)
    conc = [l for l in c.lancamentos if l.lado == "EXTRATO" and l.status == "CONCILIADO"]
    assert len(conc) == 1, [(l.status, l.lado) for l in c.lancamentos]
    assert conc[0].ambiguo is True, "deveria marcar ambiguo (2 candidatos, afinidade empatada)"
    r = resumo_privado(c)
    assert r.get("conciliados_ambiguos") == 1, r.get("conciliados_ambiguos")


@caso("#4 com documento que desempata -> NAO ambiguo (casa o certo)")
def _():
    D = date(2026, 1, 2)
    ext = [_ext(D, "-100.00", "DEBITO", doc="DOC9")]
    raz = [_raz(D, "-100.00", "FORN A", doc="DOC9"), _raz(D, "-100.00", "FORN B")]
    c = match_banco(ext, raz)
    conc = [l for l in c.lancamentos if l.lado == "EXTRATO" and l.status == "CONCILIADO"]
    assert len(conc) == 1 and conc[0].ambiguo is False, [(l.status, l.ambiguo) for l in c.lancamentos]
    assert conc[0].par_idx == 0, conc[0].par_idx          # casou o de doc DOC9 (idx 0)
    assert resumo_privado(c).get("conciliados_ambiguos") == 0


@caso("#4 regressao: 1:1 unico candidato -> NAO ambiguo")
def _():
    D = date(2026, 1, 2)
    c = match_banco([_ext(D, "-100.00", "FORN A")], [_raz(D, "-100.00", "FORN A")])
    conc = [l for l in c.lancamentos if l.lado == "EXTRATO" and l.status == "CONCILIADO"]
    assert len(conc) == 1 and conc[0].ambiguo is False, conc
    assert resumo_privado(c).get("conciliados_ambiguos") == 0


# ---------------------------------------------------------------------------
# #3 — amarracao na jornada pasta (opt-in saldo-razao.txt)
# ---------------------------------------------------------------------------

def _w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _ofx(linhas, saldo="0.00"):
    corpo = "\n".join(f"<STMTTRN><DTPOSTED>{d}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
                      for i, (d, v, m) in enumerate(linhas, 1))
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
            "<BANKACCTFROM><BANKID>0341<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST>\n"
            f"{corpo}\n</BANKTRANLIST><LEDGERBAL><BALAMT>{saldo}<DTASOF>20260131</LEDGERBAL>"
            "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")


_H = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _razao(linhas):
    return _H + "\n" + "\n".join(f"{d};{v};;;{c};;;" for d, v, c in linhas) + "\n"


def _run_pasta(base):
    out = os.path.join(base, "res")
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = conciliar.main(["pasta", "--pasta", base, "--out", out])
        except SystemExit as e:
            rc = e.code
    res = None
    rp = os.path.join(out, "resumo.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            res = json.load(f)
    return (rc if rc is not None else 0), res, buf.getvalue()


@caso("#3 pasta com saldo-razao.txt (+LEDGERBAL) fecha a amarracao da conta")
def _():
    base = tempfile.mkdtemp(prefix="s07_")
    _w(os.path.join(base, "Itau", "extrato.ofx"), _ofx([("20260102", "-100.00", "FORN A")], saldo="900.00"))
    _w(os.path.join(base, "Itau", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORN A")]))
    _w(os.path.join(base, "Itau", "saldo-razao.txt"), "900,00")
    rc, res, _o = _run_pasta(base)
    assert rc == 0, rc
    conta = res["contas"][0]
    assert conta.get("amarracao") is not None, conta
    assert conta.get("integridade_ok") is True, conta


@caso("#3 pasta SEM saldo-razao.txt: nao calcula amarracao, mas nao crasha")
def _():
    base = tempfile.mkdtemp(prefix="s07_")
    _w(os.path.join(base, "Itau", "extrato.ofx"), _ofx([("20260102", "-100.00", "FORN A")], saldo="900.00"))
    _w(os.path.join(base, "Itau", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORN A")]))
    rc, res, _o = _run_pasta(base)
    assert rc == 0, rc
    conta = res["contas"][0]
    assert conta.get("amarracao") in (None, {}) or conta.get("integridade_ok") is None, conta


@caso("#4 marcador AMBIGUO tambem no CSV-fallback (sem openpyxl, = ambiente da CI)")
def _():
    D = date(2026, 1, 2)
    c = match_banco([_ext(D, "-100.00", "DEBITO")], [_raz(D, "-100.00", "FORN A"), _raz(D, "-100.00", "FORN B")])
    out = tempfile.mkdtemp(prefix="s07csv_")
    saved = sys.modules.get("openpyxl", "MISSING")
    sys.modules["openpyxl"] = None                  # forca ImportError -> branch CSV-fallback
    try:
        path = conciliar._escreve_relatorio(c, out)
    finally:
        if saved == "MISSING":
            sys.modules.pop("openpyxl", None)
        else:
            sys.modules["openpyxl"] = saved
    assert path.endswith(".csv"), path
    with open(path, encoding="utf-8-sig") as f:
        txt = f.read()
    assert "AMBÍGUO" in txt, "o marcador de ambiguidade tem que aparecer no CSV-fallback tambem"


@caso("#3 saldo-extrato.txt cobre LEDGERBAL zerado/0,00 (escape hatch /codex:review)")
def _():
    base = tempfile.mkdtemp(prefix="s07z_")
    _w(os.path.join(base, "Itau", "extrato.ofx"), _ofx([("20260102", "-100.00", "FORN A")], saldo="0.00"))  # LEDGERBAL 0 (quirk)
    _w(os.path.join(base, "Itau", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORN A")]))
    _w(os.path.join(base, "Itau", "saldo-razao.txt"), "900,00")
    _w(os.path.join(base, "Itau", "saldo-extrato.txt"), "900,00")     # override do saldo do banco
    rc, res, _o = _run_pasta(base)
    assert rc == 0, rc
    conta = res["contas"][0]
    assert conta.get("amarracao") is not None and conta.get("integridade_ok") is True, conta


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> SPEC-07 OK: {len(casos)} casos de confianca travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
