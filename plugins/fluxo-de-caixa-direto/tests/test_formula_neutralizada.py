# -*- coding: utf-8 -*-
"""Texto do extrato ou do ERP que o Excel leria como formula sai com apostrofo no CSV e como
texto no XLSX; numero e data nao mudam (padrao da casa, capturador-de-notas/motor/engine/base.py)."""
import csv
from datetime import date
from decimal import Decimal

import pytest

from categorizador import carregar_dicionario
from dfc import montar
from export_xlsx import exportar_csv, exportar_xlsx
from ingest_erp import ler_titulos
from ingest_ofx import ingest_extratos

openpyxl = pytest.importorskip("openpyxl")

HYPER = '=HYPERLINK("http://x","clique")'
OFX = f"""OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>123</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><DTPOSTED>20260701<TRNAMT>-150.00<FITID>1<MEMO>{HYPER}</STMTTRN>
<STMTTRN><DTPOSTED>20260702<TRNAMT>80.00<FITID>2<MEMO>@MENCAO</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>1000.00<DTASOF>20260719</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def _resultado(tmp_path):
    p = tmp_path / "a.ofx"
    p.write_text(OFX, encoding="utf-8")
    pagar = tmp_path / "pagar.csv"
    with open(pagar, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fornecedor", "documento", "vencimento", "valor", "status"])
        w.writerow(["+1", "-1", "10/08/2026", "200,00", "@x"])
        w.writerow(["@SOMA", "NF-1", "10/07/2026", "50,00", "aberto"])  # vencido: vira alerta
    res = ingest_extratos([str(p)])
    titulos = ler_titulos(str(pagar), perfil="generico", tipo="pagar")
    return montar(res.lancamentos, titulos, res.contas, date(2026, 7, 20), 13, carregar_dicionario())


def _todas_celulas_csv(pasta):
    out = []
    for nome in ("lancamentos", "titulos_em_aberto", "alertas", "realizado", "resumo"):
        with open(pasta / f"{nome}.csv", encoding="utf-8-sig", newline="") as f:
            out += [c for linha in csv.reader(f, delimiter=";") for c in linha]
    return out


def test_csv_neutraliza_texto_e_deixa_numero(tmp_path):
    exportar_csv(_resultado(tmp_path), date(2026, 7, 20), str(tmp_path / "csv"))
    celulas = _todas_celulas_csv(tmp_path / "csv")
    assert "'" + HYPER in celulas
    for v in ("+1", "-1", "@x", "@SOMA", "@MENCAO"):
        assert "'" + v in celulas and v not in celulas
    assert "-150.00" in celulas  # valor negativo segue numero
    assert not [c for c in celulas if c[:1] in ("=", "+", "@", "\t", "\r")]


def test_xlsx_grava_texto_e_nao_formula(tmp_path):
    destino = tmp_path / "f.xlsx"
    exportar_xlsx(_resultado(tmp_path), date(2026, 7, 20), str(destino))
    wb = openpyxl.load_workbook(str(destino))
    formulas = [c.coordinate for ws in wb for linha in ws.iter_rows() for c in linha if c.data_type == "f"]
    assert formulas == []
    lanc = wb["Lançamentos"]
    descricoes = {lanc.cell(row=i, column=3).value: lanc.cell(row=i, column=3).data_type
                  for i in range(2, lanc.max_row + 1)}
    assert descricoes["'" + HYPER] == "s"
    valores = [lanc.cell(row=i, column=4).value for i in range(2, lanc.max_row + 1)]
    assert -150.0 in valores
    tit = wb["Títulos em aberto"]
    textos = {tit.cell(row=i, column=j).value for i in range(2, tit.max_row + 1) for j in (2, 3, 6)}
    assert {"'+1", "'-1", "'@x", "'@SOMA"} <= textos


def test_texto_vazio_nao_ganha_apostrofo():
    from export_xlsx import _texto
    assert _texto("") == ""
    assert _texto(None) is None
    assert _texto(Decimal("-1.00")) == Decimal("-1.00")
    assert _texto("ACME") == "ACME"
    assert _texto("\tx") == "'\tx"  # o parser apara o tab, mas o exportador cobre
