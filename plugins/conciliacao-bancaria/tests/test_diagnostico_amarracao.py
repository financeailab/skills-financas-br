# -*- coding: utf-8 -*-
"""Diagnostico do residuo da amarracao (o "por que nao fechou").

Quando a amarracao de saldo NAO fecha, o motor nao pode so dizer "residuo X".
Tem de apontar a causa provavel + a acao, usando SO numeros ja expostos no resumo
(residuo, saldos, categorias) -> seguro p/ a IA (nenhuma linha bruta vaza).

Duas causas que cobrem o grosso do dia-a-dia:
  - SALDO informado do razao errado (causa nº1) -> diz o saldo implicito pelos lancamentos.
  - Uma PENDENCIA isolada cujo valor explica o residuo -> aponta a categoria p/ conferir.

Rodar:  python tests/test_diagnostico_amarracao.py
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
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from reconcile import match_banco, resumo_privado          # noqa: E402
import conciliar                                            # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _raz(d, v, nome=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "identificador": None,
            "contraparte": nome, "cpf_cnpj": None, "descricao": nome, "lote": None}


def _ext(d, v, desc=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "descricao": desc,
            "contraparte": desc, "cpf_cnpj": None, "identificador": None}


D = date(2026, 5, 4)


@caso("amarracao FECHA -> diagnostico ausente (None)")
def _():
    c = match_banco([_ext(D, "-100.00", "FORNEC")], [_raz(D, "-100.00", "FORNEC")],
                    saldo_extrato_final=Decimal("100.00"), saldo_razao_final=Decimal("100.00"))
    assert c.integridade_ok is True, c.amarracao
    assert c.amarracao.get("diagnostico") is None, c.amarracao.get("diagnostico")


@caso("NAO fecha sem pendencia -> causa=saldo + saldo implicito correto")
def _():
    # tudo concilia; o saldo do razao informado (200) nao bate com o extrato (50).
    c = match_banco([_ext(D, "-100.00", "FORNEC")], [_raz(D, "-100.00", "FORNEC")],
                    saldo_extrato_final=Decimal("50.00"), saldo_razao_final=Decimal("200.00"))
    diag = c.amarracao["diagnostico"]
    assert diag["causa_provavel"] == "saldo", diag
    assert diag["residuo"] == "-150.00", diag
    assert diag["saldo_razao_informado"] == "200.00", diag
    # pelos lancamentos, o saldo do razao deveria ser 200 + (-150) = 50
    assert diag["saldo_razao_implicito"] == "50.00", diag


@caso("residuo bate com PENDENTE_RAZAO -> causa=pendencia + categoria")
def _():
    # -7 no razao sem contrapartida no banco; saldos batem fora dela -> residuo == -7
    c = match_banco([_ext(D, "-100.00", "FORNEC")],
                    [_raz(D, "-100.00", "FORNEC"), _raz(D, "-7.00", "FANTASMA")],
                    saldo_extrato_final=Decimal("100.00"), saldo_razao_final=Decimal("100.00"))
    diag = c.amarracao["diagnostico"]
    assert diag["residuo"] == "-7.00", diag
    assert diag["causa_provavel"] == "pendencia", diag
    assert diag["pendencias_que_explicam"]["qtd"] == 1, diag
    assert "EM_TRANSITO" in diag["pendencias_que_explicam"]["categorias"], diag


@caso("residuo bate com PENDENTE_EXTRATO (valor == -residuo) -> causa=pendencia")
def _():
    # tarifa -9,90 no banco, ainda nao no razao; saldos batem fora dela -> residuo == 9,90
    c = match_banco([_ext(D, "-100.00", "FORNEC"), _ext(D, "-9.90", "TARIFA PACOTE")],
                    [_raz(D, "-100.00", "FORNEC")],
                    saldo_extrato_final=Decimal("150.00"), saldo_razao_final=Decimal("150.00"))
    diag = c.amarracao["diagnostico"]
    assert diag["residuo"] == "9.90", diag
    assert diag["causa_provavel"] == "pendencia", diag
    assert "TARIFA_IOF" in diag["pendencias_que_explicam"]["categorias"], diag


@caso("diagnostico nao vaza descricao bruta (so numeros e categorias)")
def _():
    c = match_banco([_ext(D, "-100.00", "PIX MARIA SILVA")],
                    [_raz(D, "-100.00", "PIX MARIA SILVA"), _raz(D, "-7.00", "FORNEC ACME LTDA")],
                    saldo_extrato_final=Decimal("100.00"), saldo_razao_final=Decimal("100.00"))
    blob = json.dumps(c.amarracao["diagnostico"], ensure_ascii=False).upper()
    assert "ACME" not in blob and "MARIA" not in blob and "SILVA" not in blob, blob


@caso("diagnostico vai no resumo_privado (sobe p/ a IA)")
def _():
    c = match_banco([_ext(D, "-100.00", "FORNEC")], [_raz(D, "-100.00", "FORNEC")],
                    saldo_extrato_final=Decimal("50.00"), saldo_razao_final=Decimal("200.00"))
    r = resumo_privado(c)
    assert r["amarracao"]["diagnostico"]["causa_provavel"] == "saldo", r["amarracao"]


# ---------------- CLI: o stdout que a analista/IA le ----------------
def _ofx_str(linhas, saldo):
    corpo = "\n".join(f"<STMTTRN><DTPOSTED>{d}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
                      for i, (d, v, m) in enumerate(linhas, 1))
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
            "<BANKACCTFROM><BANKID>0341<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTFROM>"
            f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
            f"<LEDGERBAL><BALAMT>{saldo}<DTASOF>20260531</LEDGERBAL></STMTRS></STMTTRNRS>"
            "</BANKMSGSRSV1></OFX>")


def _cli_naofecha():
    """Roda o CLI numa conciliacao que NAO fecha (saldo errado) e devolve (rc, stdout)."""
    d = tempfile.mkdtemp(prefix="diag_")
    with open(os.path.join(d, "e.ofx"), "w", encoding="utf-8") as f:
        f.write(_ofx_str([("20260502", "-100.00", "FORNEC")], "50.00"))
    with open(os.path.join(d, "r.csv"), "w", encoding="utf-8") as f:
        f.write("Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote\n"
                "02/05/2026;-100,00;;;FORNEC;;;\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = conciliar.main(["conciliar", "--extrato", os.path.join(d, "e.ofx"),
                                 "--razao", os.path.join(d, "r.csv"), "--saldo-razao", "200,00",
                                 "--out", os.path.join(d, "out")])
        except SystemExit as e:
            rc = e.code
    return (rc if rc is not None else 0), buf.getvalue()


@caso("CLI: amarracao nao fecha -> exit 3 (inalterado)")
def _():
    rc, _out = _cli_naofecha()
    assert rc == 3, rc


@caso("CLI: stdout traz a causa provavel e o saldo implicito")
def _():
    _rc, out = _cli_naofecha()
    low = out.lower()
    assert "causa" in low, out
    assert "saldo" in low, out
    # pelos lancamentos, o saldo do razao deveria ser 200 + (-150) = 50,00
    assert "50.00" in out or "50,00" in out, out


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
    print(f"==> DIAGNOSTICO DA AMARRACAO OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
