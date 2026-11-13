# -*- coding: utf-8 -*-
"""V6: texto da nota que comeca com = + - @ nao vira formula no CSV (apostrofo) nem no XLSX (tipo texto)."""
from __future__ import annotations

import csv
import io
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from engine.batch import processar_lote
from engine.export.csv_generico import exportar_csv
from engine.export.xlsx import exportar_xlsx

NACIONAL = (Path(__file__).parent / "fixtures" / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")
PAYLOADS = ['=HYPERLINK("http://x","y")', "+1", "-1", "@x"]


def _xml(payload: str) -> str:
    base = NACIONAL.replace("<pAliqAplic>5.00</pAliqAplic>", "<pAliqAplic>3.00</pAliqAplic>")  # vira excecao
    import re
    base = re.sub(r"<xNome>[^<]*</xNome>", lambda m: f"<xNome>{payload.replace('&', '&amp;')}</xNome>", base, count=1)
    return re.sub(r"<dhEmi>[^<]*</dhEmi>", lambda m: f"<dhEmi>{payload}</dhEmi>", base, count=1)


def _celulas(csv_texto: str) -> dict[str, str]:
    linhas = list(csv.reader(io.StringIO(csv_texto), delimiter=";"))
    assert len(linhas) == 2
    return dict(zip(linhas[0], linhas[1]))


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("perfil,col_nome,col_data", [
    ("generico", "fornecedor_nome", "data_emissao"),
    ("omie", "Razão Social", None),
    ("contaazul", "Descrição", "Data de competência"),
])
def test_carga_csv_dos_3_perfis(payload, perfil, col_nome, col_data):
    r = processar_lote([("n.xml", _xml(payload))], perfil)
    assert r["linhas"], "a nota deveria ter sido lida"
    cel = _celulas(r["csv"])
    assert cel[col_nome] == "'" + payload
    if col_data:
        assert cel[col_data] == "'" + payload


@pytest.mark.parametrize("payload", PAYLOADS)
def test_excecoes_csv(payload):
    r = processar_lote([(payload, _xml("ok"))])
    assert r["excecoes"]
    txt = exportar_csv(r["excecoes"], colunas=("arquivo_origem", "chave_arquivo", "confianca_nota", "motivo"))
    assert _celulas_primeira(txt)["arquivo_origem"] == "'" + payload


def _celulas_primeira(txt):
    linhas = list(csv.reader(io.StringIO(txt), delimiter=";"))
    return dict(zip(linhas[0], linhas[1]))


@pytest.mark.parametrize("payload", PAYLOADS)
def test_xlsx_celula_de_texto_nunca_e_formula(payload):
    r = processar_lote([(payload, _xml(payload))])
    wb = openpyxl.load_workbook(io.BytesIO(exportar_xlsx(r["linhas"], r["resumo"])))
    ws = wb["Carga"]
    cab = {c.value: c.column for c in ws[1]}
    for titulo in ("Arquivo", "Fornecedor", "Emissao"):
        cel = ws.cell(row=2, column=cab[titulo])
        assert cel.value == payload and cel.data_type == "s", titulo


def test_decimais_texto_vazio_e_data_iso_ficam_iguais():
    ln = {"valor_total": Decimal("-10.50"), "ret_irrf": Decimal("0.00"), "iss_valor": None,
          "data_emissao": "2026-03-15T10:00:00-03:00", "fornecedor_nome": "", "vencimento": None,
          "motivos": "ISS nao fecha: x"}
    cel = _celulas(exportar_csv([ln], colunas=("valor_total", "ret_irrf", "iss_valor", "data_emissao",
                                               "fornecedor_nome", "vencimento", "motivos")))
    assert cel == {"valor_total": "-10,50", "ret_irrf": "0,00", "iss_valor": "", "data_emissao": "15/03/2026",
                   "fornecedor_nome": "", "vencimento": "", "motivos": "ISS nao fecha: x"}
    ws = openpyxl.load_workbook(io.BytesIO(exportar_xlsx([ln], {})))["Carga"]
    cab = {c.value: c.column for c in ws[1]}
    assert ws.cell(row=2, column=cab["Valor total"]).value == -10.5
    assert ws.cell(row=2, column=cab["Valor total"]).data_type == "n"
