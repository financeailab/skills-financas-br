# -*- coding: utf-8 -*-
"""Testes do emissor XLSX (emit_xlsx.py) — abre com openpyxl e confere celulas chave."""
from datetime import date
from decimal import Decimal

from modelo import OK, Encargo, FaturaParsed, Lancamento
from emit_xlsx import emit


def _fatura():
    return FaturaParsed(
        emissor="itau",
        portadores=["CARLOS EDUARDO LIMA"],
        vencimento=date(2026, 2, 10),
        lancamentos=[
            Lancamento(date(2026, 1, 5), "Supermercado Bom Preco", Decimal("358.40"),
                       portador="CARLOS EDUARDO LIMA"),
            Lancamento(date(2026, 1, 12), "Hotel Barcelona Espanha", Decimal("892.15"),
                       portador="CARLOS EDUARDO LIMA", moeda="EUR", internacional=True),
        ],
        encargos=[Encargo("IOF", Decimal("53.53"))],
        total_fatura=Decimal("1304.08"),
        veredicto=OK,
    )


def test_emit_xlsx_gera_arquivo_valido(tmp_path):
    path = str(tmp_path / "fatura.xlsx")
    emit(_fatura(), path)

    import openpyxl
    wb = openpyxl.load_workbook(path)
    assert "Fatura" in wb.sheetnames


def test_emit_xlsx_tabela_tem_as_colunas_certas(tmp_path):
    path = str(tmp_path / "fatura.xlsx")
    emit(_fatura(), path)

    import openpyxl
    wb = openpyxl.load_workbook(path)
    ws = wb["Fatura"]
    textos = {c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)}
    assert "Estabelecimento" in textos
    assert "Supermercado Bom Preco" in textos
    assert "Hotel Barcelona Espanha" in textos


def test_emit_xlsx_mostra_total_calculado_e_impresso(tmp_path):
    path = str(tmp_path / "fatura.xlsx")
    emit(_fatura(), path)

    import openpyxl
    wb = openpyxl.load_workbook(path)
    ws = wb["Fatura"]
    valores = [c.value for row in ws.iter_rows() for c in row]
    assert 1304.08 in valores  # total calculado E total impresso batem (fixture fechada)


def test_emit_xlsx_sem_lancamentos_nao_quebra(tmp_path):
    path = str(tmp_path / "fatura_vazia.xlsx")
    fatura_vazia = FaturaParsed(emissor="generico")
    emit(fatura_vazia, path)  # nao deve lancar excecao

    import openpyxl
    wb = openpyxl.load_workbook(path)
    assert "Fatura" in wb.sheetnames
