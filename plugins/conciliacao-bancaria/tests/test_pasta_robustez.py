# -*- coding: utf-8 -*-
"""Robustez do comando `pasta` (SPEC-05): a pasta-mae e um CONTAINER de subpastas de conta.
Arquivo solto na raiz, pasta de saida antiga, __pycache__ e pastas ocultas NAO viram
"conta fantasma". Uso indevido (sem subpasta) -> orientacao clara, nao erro mudo.

Rodar:  python tests/test_pasta_robustez.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts", "engine"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import conciliar   # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _ofx(linhas):
    corpo = "\n".join(f"<STMTTRN><DTPOSTED>{d}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
                      for i, (d, v, m) in enumerate(linhas, 1))
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
            "<BANKACCTFROM><BANKID>0341<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTFROM>"
            f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
            "<LEDGERBAL><BALAMT>0.00<DTASOF>20260531</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")


_H = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _razao(linhas):
    return _H + "\n" + "\n".join(f"{d};{v};;;{c};;;" for d, v, c in linhas) + "\n"


def _conta(base, nome, ofx_linhas, raz_linhas):
    _w(os.path.join(base, nome, "extrato.ofx"), _ofx(ofx_linhas))
    _w(os.path.join(base, nome, "razao.csv"), _razao(raz_linhas))


def _run_pasta(base, out=None):
    """Roda 'pasta', captura stdout, devolve (rc, resumo_dict|None, stdout)."""
    out = out or os.path.join(tempfile.mkdtemp(prefix="out_"), "res")
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


def _nomes(res):
    return [c["conta"] for c in (res["contas"] if res else [])]


CONTA_OK = ([("20260102", "-100.00", "FORNEC A")], [("02/01/2026", "-100,00", "FORNEC A")])


@caso("arquivo solto na raiz NAO vira conta fantasma (1 conta)")
def _():
    base = tempfile.mkdtemp(prefix="rob_")
    _conta(base, "Itau", *CONTA_OK)
    _w(os.path.join(base, "LEIA-ME.txt"), "instrucoes")
    _w(os.path.join(base, "notas.pdf"), "%PDF-1.4 fake")
    rc, res, _out = _run_pasta(base)
    assert rc == 0, rc
    assert res["resumo"]["contas"] == 1, res["resumo"]
    assert "." not in _nomes(res), _nomes(res)


@caso("pasta de saida antiga (resultado-pasta) e ignorada (1 conta)")
def _():
    base = tempfile.mkdtemp(prefix="rob_")
    _conta(base, "Itau", *CONTA_OK)
    _w(os.path.join(base, "resultado-pasta", "resumo.json"), '{"resumo":{}}')
    _w(os.path.join(base, "resultado-pasta", "conciliacao.csv"), "a;b\n1;2\n")
    rc, res, _out = _run_pasta(base)
    assert res["resumo"]["contas"] == 1, (res["resumo"], _nomes(res))


@caso("__pycache__ e pasta oculta sao ignorados (1 conta)")
def _():
    base = tempfile.mkdtemp(prefix="rob_")
    _conta(base, "Itau", *CONTA_OK)
    _w(os.path.join(base, "__pycache__", "x.pyc"), "junk")
    _w(os.path.join(base, ".git", "config"), "[core]")
    _w(os.path.join(base, "_rascunho", "extrato.ofx"), _ofx([("20260102", "-9.00", "X")]))
    rc, res, _out = _run_pasta(base)
    assert res["resumo"]["contas"] == 1, (res["resumo"], _nomes(res))


@caso("so arquivos soltos na raiz (sem subpasta) -> 0 contas, exit 0, orientacao")
def _():
    base = tempfile.mkdtemp(prefix="rob_")
    _w(os.path.join(base, "extrato.ofx"), _ofx(CONTA_OK[0]))
    _w(os.path.join(base, "razao.csv"), _razao(CONTA_OK[1]))
    rc, res, out = _run_pasta(base)
    assert rc == 0, rc
    assert res["resumo"]["contas"] == 0, res["resumo"]
    assert "subpasta" in out.lower() and "conciliar" in out.lower(), out


@caso("regressao: 2 subpastas validas -> 2 contas conciliadas")
def _():
    base = tempfile.mkdtemp(prefix="rob_")
    _conta(base, "Itau", *CONTA_OK)
    _conta(base, "Bradesco", [("20260103", "-50.00", "FORNEC B")], [("03/01/2026", "-50,00", "FORNEC B")])
    rc, res, _out = _run_pasta(base)
    assert res["resumo"]["contas"] == 2, res["resumo"]
    assert res["resumo"]["conciliadas"] == 2, res["resumo"]


def main():
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> ROBUSTEZ DA PASTA OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
