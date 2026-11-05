# -*- coding: utf-8 -*-
"""Trava as correcoes da REVIEW adversarial (2026-06-03) — pra ninguem regredir.

Cobre: parse_valor milhar BR (erro 1000x), guard multi-conta, tolerancia exige
afinidade (nao casar errado), STMTTRN sem fechamento, CDATA/<BR/> no MEMO, E2E,
e razao com linha ruim nao derruba o run.

Rodar:  python tests/test_review_fixes.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from normalize import parse_valor                       # noqa: E402
from ingest_ofx import parse_ofx_text                   # noqa: E402
from reconcile import match_banco                       # noqa: E402
import conciliar                                        # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _ofx(corpo_tranlist, extra_stmtrs=""):
    return f"""OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>001<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
{corpo_tranlist}
</BANKTRANLIST></STMTRS></STMTTRNRS>{extra_stmtrs}</BANKMSGSRSV1></OFX>"""


@caso("parse_valor: milhar BR (1.234 -> 1234), nao 1,23")
def _():
    assert parse_valor("1.234", origem="br") == Decimal("1234.00"), parse_valor("1.234", origem="br")
    assert parse_valor("12.500", origem="br") == Decimal("12500.00")
    assert parse_valor("1.234.567", origem="br") == Decimal("1234567.00")
    assert parse_valor("1.234,56", origem="br") == Decimal("1234.56")   # ponto milhar + virgula decimal
    assert parse_valor("1.5", origem="br") == Decimal("1.50")           # 1 digito apos ponto = decimal
    # OFX: ponto e SEMPRE decimal (nunca milhar)
    assert parse_valor("1234.56", origem="ofx") == Decimal("1234.56")
    assert parse_valor("1.234", origem="ofx") == Decimal("1.23")


@caso("guard multi-conta: 2 contas no arquivo -> n_contas==2")
def _():
    duas = _ofx("<STMTTRN><DTPOSTED>20260102<TRNAMT>10.00<FITID>1<MEMO>A</STMTTRN>",
                extra_stmtrs="<STMTTRNRS><STMTRS><CURDEF>BRL"
                "<BANKACCTFROM><BANKID>001<ACCTID>8<ACCTTYPE>SAVINGS</BANKACCTFROM>"
                "<BANKTRANLIST><STMTTRN><DTPOSTED>20260103<TRNAMT>20.00<FITID>2<MEMO>B</STMTTRN>"
                "</BANKTRANLIST></STMTRS></STMTTRNRS>")
    e = parse_ofx_text(duas)
    assert e.n_contas == 2, e.n_contas


@caso("tolerancia EXIGE afinidade: par sem sinal nao casa (fica pendente)")
def _():
    d = date(2026, 1, 10)
    ext = [{"data": d, "valor": Decimal("-8.40"), "doc": None, "descricao": "TARIFA AVULSA",
            "contraparte": "TARIFA AVULSA", "cpf_cnpj": None, "identificador": None}]
    raz = [{"data": d, "valor": Decimal("-8.35"), "doc": None, "descricao": "DESPESA ESCRITORIO",
            "contraparte": "DESPESA ESCRITORIO", "cpf_cnpj": None, "identificador": None}]
    c = match_banco(ext, raz)
    st = {l.lado: l.status for l in c.lancamentos}
    assert st.get("EXTRATO") == "PENDENTE_EXTRATO", st     # NAO virou conciliado-com-diferenca
    assert st.get("RAZAO") == "PENDENTE_RAZAO", st


@caso("STMTTRN sem tag de fechamento ainda parseia as transacoes")
def _():
    sem_fecho = _ofx(
        "<STMTTRN><DTPOSTED>20260102<TRNAMT>-50,00<FITID>A1<MEMO>UM\n"
        "<STMTTRN><DTPOSTED>20260103<TRNAMT>-60,00<FITID>A2<MEMO>DOIS")
    e = parse_ofx_text(sem_fecho)
    assert len(e.transacoes) == 2, len(e.transacoes)
    assert e.transacoes[0]["valor"] == Decimal("-50.00")


@caso("CDATA e <BR/> no MEMO nao mutilam descricao/CNPJ")
def _():
    cd = _ofx("<STMTTRN><DTPOSTED>20260102<TRNAMT>100.00<FITID>C1"
              "<MEMO><![CDATA[PIX & CIA 12.345.678/0001-90]]></STMTTRN>")
    e = parse_ofx_text(cd)
    t = e.transacoes[0]
    assert "CIA" in t["descricao"], t["descricao"]
    assert t["cpf_cnpj"] == "12345678000190", t["cpf_cnpj"]

    br = _ofx("<STMTTRN><DTPOSTED>20260102<TRNAMT>100.00<FITID>C2"
              "<MEMO>PIX RECEBIDO<BR/>JOAO 111.444.777-35</STMTTRN>")
    e2 = parse_ofx_text(br)
    t2 = e2.transacoes[0]
    assert "JOAO" in t2["descricao"], t2["descricao"]
    assert t2["cpf_cnpj"] == "11144477735", t2["cpf_cnpj"]


@caso("E2E do Pix no MEMO popula identificador")
def _():
    e2e = "E12345678202601021200abcde123456"  # E + ISPB(8) + data(12) + 11 = 32 chars
    ofx = _ofx(f"<STMTTRN><DTPOSTED>20260102<TRNAMT>500.00<FITID>P1<MEMO>PIX {e2e} FULANO</STMTTRN>")
    e = parse_ofx_text(ofx)
    assert e.transacoes[0]["identificador"] == e2e, e.transacoes[0]["identificador"]


@caso("razao com linha ruim NAO derruba o run (erro contabilizado)")
def _():
    linhas = [
        {"Data": "02/01/2026", "Valor": "1.500,00", "Documento": "1", "Historico": "ok"},
        {"Data": "", "Valor": "", "Documento": "", "Historico": "Subtotal"},   # linha de rodape ruim
        {"Data": "03/01/2026", "Valor": "-850,00", "Documento": "2", "Historico": "ok2"},
    ]
    cols = conciliar._detecta_colunas(list(linhas[0].keys()), {})
    registros, erros = conciliar._razao_canonico(linhas, cols)
    assert len(registros) == 2, len(registros)     # 2 boas
    assert len(erros) == 1, erros                  # 1 ruim, sem crash
    assert "linha 3" in erros[0], erros            # linha 3 = a do meio (header=1, dados de 2)


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
    print(f"==> REVIEW FIXES OK: {len(casos)} correcoes travadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
