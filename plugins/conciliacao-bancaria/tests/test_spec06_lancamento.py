# -*- coding: utf-8 -*-
"""SPEC-06 — correcoes de lancamento (validacao 2026-06-22). Trava os 5 fixes contra
regressao. STDLIB-PURA (a CI roda sem requirements): nao importa openpyxl/xlrd; quando
o relatorio precisa de openpyxl ele cai no CSV-fallback, e o teste aceita os dois.

  #1 pasta grava relatorio por conta (todo formato) + conciliar/validar multiformato
  #2 lote de remessa explicita exige soma EXATA (nao tolera centavos)
  #3 razao .xlsx corrompida NAO derruba a pasta inteira (degrada por conta)
  #4 resumo do posicao mascara o numero de conta + nome de arquivo
  #5 flags --col-ident/--col-contraparte/--col-cpfcnpj/--col-lote existem e mapeiam

Rodar:  python tests/test_spec06_lancamento.py
"""
import glob
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts"))
import conciliar                       # noqa: E402
from reconcile import match_banco      # noqa: E402
from posicao import varrer_pasta, consolidar_extratos  # noqa: E402
from sheets_push import montar_linhas_agregadas        # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _w(path, content, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if binary else "w"
    kw = {} if binary else {"encoding": "utf-8"}
    with open(path, mode, **kw) as f:
        f.write(content)
    return path


def _ofx(linhas, acctid="9", saldo="0.00"):
    corpo = "\n".join(f"<STMTTRN><DTPOSTED>{d}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
                      for i, (d, v, m) in enumerate(linhas, 1))
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
            f"<BANKACCTFROM><BANKID>0341<ACCTID>{acctid}<ACCTTYPE>CHECKING</BANKACCTFROM>"
            f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
            f"<LEDGERBAL><BALAMT>{saldo}<DTASOF>20260531</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")


_H = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _razao(linhas):
    # linhas: (data, valor, contraparte)
    return _H + "\n" + "\n".join(f"{d};{v};;;{c};;;" for d, v, c in linhas) + "\n"


def _csv_extrato(linhas):
    # extrato tabular CSV (lado banco): Data;Historico;Valor
    return "Data;Historico;Valor\n" + "\n".join(f"{d};{m};{v}" for d, v, m in linhas) + "\n"


def _run(argv):
    """Roda conciliar.main(argv), captura stdout, devolve (rc, stdout). NUNCA deve lancar."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = conciliar.main(argv)
        except SystemExit as e:
            rc = e.code
    return (rc if rc is not None else 0), buf.getvalue()


def _load(out):
    rp = os.path.join(out, "resumo.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            return json.load(f)
    return None


def _tem_relatorio(pasta_conta):
    return bool(glob.glob(os.path.join(pasta_conta, "conciliacao.xlsx"))
                or glob.glob(os.path.join(pasta_conta, "conciliacao_por_status.csv")))


# ---------------------------------------------------------------------------
# #1 pasta grava relatorio por conta (OFX e CSV) + conciliar/validar multiformato
# ---------------------------------------------------------------------------

@caso("#1 pasta grava conciliacao.* em CADA conta (OFX e CSV)")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "Itau", "extrato.ofx"), _ofx([("20260102", "-100.00", "FORNEC A")]))
    _w(os.path.join(base, "Itau", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORNEC A")]))
    _w(os.path.join(base, "Bradesco", "extrato.csv"), _csv_extrato([("05/05/2026", "-640,00", "ALUGUEL")]))
    _w(os.path.join(base, "Bradesco", "razao.csv"), _razao([("05/05/2026", "-640,00", "ALUGUEL")]))
    rc, _out = _run(["pasta", "--pasta", base, "--out", os.path.join(base, "res")])
    assert rc == 0, rc
    assert _tem_relatorio(os.path.join(base, "Itau")), "Itau sem relatorio"
    assert _tem_relatorio(os.path.join(base, "Bradesco")), "Bradesco (CSV) sem relatorio"


@caso("#1 re-run NAO reingere o relatorio como extrato (sem conta fantasma/2x)")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "Itau", "extrato.ofx"), _ofx([("20260102", "-100.00", "FORNEC A")]))
    _w(os.path.join(base, "Itau", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORNEC A")]))
    out = os.path.join(base, "res")
    _run(["pasta", "--pasta", base, "--out", out])      # 1a rodada grava o relatorio
    rc, _o = _run(["pasta", "--pasta", base, "--out", out])  # 2a rodada
    res = _load(out)
    assert rc == 0, rc
    assert res["resumo"]["contas"] == 1, res["resumo"]
    # o extrato escolhido continua sendo o ofx, nao o relatorio
    assert res["contas"][0]["fonte"] == "ofx", res["contas"][0]


@caso("#1 validar em extrato CSV NAO diz 'OFX invalido' (multiformato)")
def _():
    d = tempfile.mkdtemp(prefix="s06_")
    ext = _w(os.path.join(d, "extrato.csv"), _csv_extrato([("02/01/2026", "-100,00", "FORNEC A")]))
    raz = _w(os.path.join(d, "razao.csv"), _razao([("02/01/2026", "-100,00", "FORNEC A")]))
    rc, out = _run(["validar", "--extrato", ext, "--razao", raz])
    assert "OFX" not in out, out          # mensagem enganosa some
    assert rc == 0, (rc, out)             # CSV valido aprova


# ---------------------------------------------------------------------------
# #2 lote de remessa explicita = soma EXATA
# ---------------------------------------------------------------------------

@caso("#2 lote explicito com diferenca de centavos NAO vira CONCILIADO_LOTE")
def _():
    D = date(2026, 1, 20)
    ext = [{"data": D, "valor": Decimal("-10.00"), "doc": None, "descricao": "SISPAG",
            "contraparte": "SISPAG", "cpf_cnpj": None, "identificador": None}]
    raz = [{"data": D, "valor": Decimal("-6.00"), "doc": None, "identificador": None,
            "contraparte": "A", "cpf_cnpj": None, "descricao": "A", "lote": "R1"},
           {"data": D, "valor": Decimal("-4.05"), "doc": None, "identificador": None,
            "contraparte": "B", "cpf_cnpj": None, "descricao": "B", "lote": "R1"}]
    c = match_banco(ext, raz)
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 0, c.contagem
    assert c.contagem.get("PENDENTE_EXTRATO", 0) == 1, c.contagem


@caso("#2 regressao: lote explicito com soma EXATA continua CONCILIADO_LOTE")
def _():
    D = date(2026, 1, 20)
    ext = [{"data": D, "valor": Decimal("-10.00"), "doc": None, "descricao": "SISPAG",
            "contraparte": "SISPAG", "cpf_cnpj": None, "identificador": None}]
    raz = [{"data": D, "valor": Decimal("-6.00"), "doc": None, "identificador": None,
            "contraparte": "A", "cpf_cnpj": None, "descricao": "A", "lote": "R1"},
           {"data": D, "valor": Decimal("-4.00"), "doc": None, "identificador": None,
            "contraparte": "B", "cpf_cnpj": None, "descricao": "B", "lote": "R1"}]
    c = match_banco(ext, raz)
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 1, c.contagem


# ---------------------------------------------------------------------------
# #3 razao .xlsx corrompida NAO derruba a pasta inteira
# ---------------------------------------------------------------------------

@caso("#3 razao .xlsx corrompida: conta boa concilia, run nao crasha")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "ContaBoa", "extrato.ofx"), _ofx([("20260102", "-100.00", "A")]))
    _w(os.path.join(base, "ContaBoa", "razao.csv"), _razao([("02/01/2026", "-100,00", "A")]))
    _w(os.path.join(base, "ContaRuim", "extrato.ofx"), _ofx([("20260103", "-50.00", "B")]))
    _w(os.path.join(base, "ContaRuim", "razao.xlsx"), b"isto nao e um xlsx de verdade", binary=True)
    out = os.path.join(base, "res")
    rc, txt = _run(["pasta", "--pasta", base, "--out", out])   # nao pode lancar
    res = _load(out)
    assert rc == 0, (rc, txt)
    nomes_conc = [c["conta"] for c in res["contas"] if c.get("tem_razao") and not c["precisa_acao"]]
    assert "ContaBoa" in nomes_conc, res["contas"]


# ---------------------------------------------------------------------------
# #4 resumo do posicao mascara numero de conta + arquivo
# ---------------------------------------------------------------------------

@caso("#4 posicao: resumo nao expoe o numero de conta cru nem o nome de arquivo")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "extrato_cliente_secreto.ofx"), _ofx([("20260102", "-100.00", "A")], acctid="12345-6", saldo="900.00"))
    out = os.path.join(base, "res")
    rc, _t = _run(["posicao", "--pasta", base, "--out", out])
    res = _load(out)
    assert rc == 0, rc
    blob = json.dumps(res, ensure_ascii=False)
    assert "12345-6" not in blob, "numero de conta cru vazou no resumo do posicao"
    assert "extrato_cliente_secreto" not in blob, "nome de arquivo vazou no resumo do posicao"
    # banco e saldo (saldos e totais) continuam OK
    assert res["contas"][0]["banco"] == "0341", res["contas"][0]


# ---------------------------------------------------------------------------
# #5 flags --col-* documentadas existem
# ---------------------------------------------------------------------------

@caso("#5 --col-contraparte e aceito e mapeia a coluna")
def _():
    d = tempfile.mkdtemp(prefix="s06_")
    ext = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")]))
    raz = _w(os.path.join(d, "r.csv"), "Data;Valor;Favorecido\n02/01/2026;-100,00;FORN A\n")
    rc, out = _run(["validar", "--extrato", ext, "--razao", raz, "--col-contraparte", "Favorecido"])
    assert "unrecognized arguments" not in out, out
    assert rc == 0, (rc, out)
    assert "Favorecido" in out, out      # contraparte detectada e reportada nos metadados


# ---------------------------------------------------------------------------
# achados do Codex pre-PR (SPEC-06): Sheet tambem mascara; skip do relatorio e nome exato
# ---------------------------------------------------------------------------

@caso("#4 Sheet (--sheet): linhas mascaram a conta e NAO trazem nome de arquivo")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "cliente_secreto.ofx"),
       _ofx([("20260102", "-100.00", "A")], acctid="12345-6", saldo="900.00"))
    cons = consolidar_extratos(varrer_pasta(base))
    blob = "\n".join("|".join(str(x) for x in row) for row in montar_linhas_agregadas(cons))
    assert "12345-6" not in blob, blob          # numero de conta cru nao vai p/ o Google
    assert "cliente_secreto" not in blob, blob  # nome de arquivo nao vai p/ o Google


@caso("#1 extrato chamado 'conciliacao_bancaria.csv' (export do ERP) NAO e descartado")
def _():
    base = tempfile.mkdtemp(prefix="s06_")
    _w(os.path.join(base, "Acme", "conciliacao_bancaria.csv"),
       _csv_extrato([("02/01/2026", "-100,00", "FORN A")]))
    _w(os.path.join(base, "Acme", "razao.csv"), _razao([("02/01/2026", "-100,00", "FORN A")]))
    out = os.path.join(base, "res")
    rc, _o = _run(["pasta", "--pasta", base, "--out", out])
    res = _load(out)
    assert rc == 0, rc
    assert res["resumo"]["contas"] == 1, res["resumo"]   # nao foi confundido com o relatorio gerado


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
    print(f"==> SPEC-06 OK: {len(casos)} correcoes de lancamento travadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
