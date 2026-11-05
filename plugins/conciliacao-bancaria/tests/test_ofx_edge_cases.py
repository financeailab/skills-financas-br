# -*- coding: utf-8 -*-
"""Edge cases de parsing OFX — snippets sinteticos que reproduzem quirks REAIS de bancos BR.

Cada caso vem de bug report documentado (ver REFERENCIAS.md). Travam o comportamento
do parser de forma deterministica, sem depender dos arquivos baixados.

Rodar:  python tests/test_ofx_edge_cases.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine"))

from ingest_ofx import parse_ofx_text     # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


# 1) Santander/ofxparse#83: virgula decimal MISTURADA com ponto no mesmo arquivo;
#    fuso a meia-noite [-3:GMT] NAO pode deslocar o dia; OTHER + sinal do TRNAMT; '&' cru; NAME sem MEMO.
SGML_MIX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
ENCODING:USASCII
CHARSET:1252

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL
<BANKACCTFROM><BANKID>033<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20150706000000[-3:GMT]
<TRNAMT>-200,00
<FITID>A1
<MEMO>PAGAMENTO BOLETO
</STMTTRN>
<STMTTRN>
<TRNTYPE>OTHER
<DTPOSTED>20150707
<TRNAMT>-12.80
<FITID>A2
<NAME>TARIFA C&A
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>1.234,56<DTASOF>20150731000000[-3:GMT]</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""


@caso("virgula+ponto no mesmo arquivo, fuso, OTHER, '&', NAME-only")
def _():
    e = parse_ofx_text(SGML_MIX)
    assert len(e.transacoes) == 2, f"txns={len(e.transacoes)}"
    t0, t1 = e.transacoes
    assert t0["valor"] == Decimal("-200.00"), t0["valor"]            # virgula
    assert t0["data"] == date(2015, 7, 6), t0["data"]                # [-3:GMT] meia-noite NAO vira 07-05
    assert t1["valor"] == Decimal("-12.80"), t1["valor"]             # ponto, no mesmo arquivo
    assert t1["tipo"] == "OTHER" and t1["valor"] < 0                 # sinal vem do TRNAMT, nao do tipo
    assert "C&A" in t1["descricao"], t1["descricao"]                 # '&' cru sobrevive
    assert e.saldo_final == Decimal("1234.56"), e.saldo_final        # BALAMT com virgula
    assert e.data_saldo == date(2015, 7, 31)


# 2) Banco do Brasil/HomeBank#1895478: ate 19 linhas em branco ANTES do header.
@caso("19 linhas em branco antes do header (BB)")
def _():
    txt = ("\n" * 19) + SGML_MIX
    e = parse_ofx_text(txt)
    assert len(e.transacoes) == 2, f"txns={len(e.transacoes)}"


# 3) ofxtools#130: <BANKTRANLIST/> auto-fechado (extrato sem transacoes) — nao e erro.
@caso("BANKTRANLIST vazio auto-fechado = 0 txns, sem crash")
def _():
    txt = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKTRANLIST/>
<LEDGERBAL><BALAMT>0,00<DTASOF>20240131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    e = parse_ofx_text(txt)
    assert e.transacoes == [], f"esperava 0 txns, veio {len(e.transacoes)}"
    assert e.saldo_final == Decimal("0.00")


# 4) Quirk BB: "Saldo do dia"/"Saldo Anterior" injetados como STMTTRN (sem FITID) — descartar.
@caso("marcadores de saldo (BB) filtrados")
def _():
    txt = """OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240102<TRNAMT>1000,00<FITID><MEMO>Saldo do dia</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240102<TRNAMT>500,00<FITID>R1<MEMO>TED RECEBIDA</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    e = parse_ofx_text(txt)
    assert len(e.transacoes) == 1, f"txns={len(e.transacoes)}"
    assert e.marcadores_saldo == 1, e.marcadores_saldo
    assert e.transacoes[0]["descricao"] == "TED RECEBIDA"


# 5) OFX 2.x (XML): header em PI, tags fechadas, fuso com fracao de segundo.
XML_2X = """<?xml version="1.0" encoding="UTF-8"?>
<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE"?>
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL</CURDEF>
<BANKACCTFROM><BANKID>001</BANKID><ACCTID>9</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>XFER</TRNTYPE><DTPOSTED>20240301120000.000[-3:BRT]</DTPOSTED><TRNAMT>-99.90</TRNAMT><FITID>X1</FITID><MEMO>PIX TESTE</MEMO></STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>500.00</BALAMT><DTASOF>20240331</DTASOF></LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


@caso("OFX 2.x XML: fracao de segundo, tags fechadas")
def _():
    e = parse_ofx_text(XML_2X)
    assert len(e.transacoes) == 1, f"txns={len(e.transacoes)}"
    t = e.transacoes[0]
    assert e.moeda == "BRL"
    assert t["valor"] == Decimal("-99.90"), t["valor"]
    assert t["data"] == date(2024, 3, 1), t["data"]
    assert t["descricao"] == "PIX TESTE", t["descricao"]
    assert e.saldo_final == Decimal("500.00")


@caso("valor ilegivel: BALAMT N/D ou com 29 digitos vira saldo None; TRNAMT com 29 digitos descarta so a linha")
def _():
    base = ("<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>341<ACCTID>1<ACCTTYPE>CHECKING"
            "</BANKACCTFROM><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261101<TRNAMT>{amt}<FITID>1<MEMO>TARIFA"
            "</STMTTRN><STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261102<TRNAMT>50.00<FITID>2<MEMO>PIX</STMTTRN>"
            "</BANKTRANLIST><LEDGERBAL><BALAMT>{bal}<DTASOF>20261102</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
    grande = "9" * 29 + ".00"
    for bal in ("N/D", grande):
        e = parse_ofx_text(base.format(amt="-10.00", bal=bal))
        assert e.saldo_final is None and len(e.transacoes) == 2, (bal[:4], e.saldo_final, len(e.transacoes))
    e = parse_ofx_text(base.format(amt=grande, bal="40.00"))
    assert (len(e.transacoes), e.txns_corrompidas, e.saldo_final) == (1, 1, Decimal("40.00")), \
        (len(e.transacoes), e.txns_corrompidas, e.saldo_final)


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn()
            print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}")
            print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}")
            print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas))
        return 1
    print(f"==> EDGE CASES OK: {len(casos)} quirks reais de OFX tratados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
