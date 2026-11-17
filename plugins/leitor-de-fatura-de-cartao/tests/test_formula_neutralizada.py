# -*- coding: utf-8 -*-
"""Texto do PDF que o Excel leria como formula sai com apostrofo (CSV e XLSX, unico e lote);
valor, data e texto vazio ficam como estao."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest

import conftest  # noqa: F401  (sys.path dos dois layouts)
import emit_csv
import emit_xlsx
import lote
from modelo import FaturaParsed, Lancamento

GATILHOS = ['=HYPERLINK("x")', "+1", "-1", "@x", "\tx"]


def _fatura(texto, portador=None):
    f = FaturaParsed(emissor="itau", veredicto="OK")
    f.lancamentos = [Lancamento(data=date(2026, 1, 5), estabelecimento=texto, valor=Decimal("-64.90"),
                                portador=texto if portador is None else portador)]
    return f


def _linhas_csv(texto):
    return list(csv.reader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))


@pytest.mark.parametrize("t", GATILHOS)
def test_csv_unico(t):
    lin = _linhas_csv(emit_csv.emit(_fatura(t)))[1]
    assert lin[1].startswith("'") and lin[2].startswith("'")
    assert lin[4] == "-64.90"


@pytest.mark.parametrize("t", GATILHOS)
def test_xlsx_unico(t, tmp_path):
    import openpyxl
    p = tmp_path / "u.xlsx"
    f = _fatura(t)
    f.portadores = [t]
    emit_xlsx.emit(f, str(p))
    ws = openpyxl.load_workbook(p).active
    celulas = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and t in c.value]
    assert len(celulas) == 3  # portadores (cabecalho), portador, estabelecimento
    for c in celulas:
        assert c.data_type == "s" and c.value.startswith("'")
    assert any(isinstance(c.value, float) and c.value == -64.90 for row in ws.iter_rows() for c in row)


@pytest.mark.parametrize("t", GATILHOS)
def test_consolidado(t, tmp_path):
    import openpyxl
    arq = tmp_path / "=arq.pdf"  # nome de arquivo tambem entra
    arq.write_bytes(b"x")
    proc = [(arq, _fatura(t))]
    lote.exportar_csv_consolidado(proc, tmp_path / "c.csv")
    lin = _linhas_csv(open(tmp_path / "c.csv", encoding="utf-8", newline="").read())[1]
    assert lin[0].startswith("'") and lin[3].startswith("'") and lin[4].startswith("'")
    assert lin[6] == "-64.90"
    lote.exportar_xlsx_consolidado(proc, lote.resumo_agregado(proc, [], []), str(tmp_path / "c.xlsx"))
    ws = openpyxl.load_workbook(tmp_path / "c.xlsx")["Lancamentos"]
    for col in (1, 4, 5):
        c = ws.cell(row=2, column=col)
        assert c.data_type == "s" and c.value.startswith("'")
    assert ws.cell(row=2, column=7).value == -64.90


def test_vazio_e_normal_nao_ganham_apostrofo():
    lin = _linhas_csv(emit_csv.emit(_fatura("", portador="")))[1]
    assert lin[1] == "" and lin[2] == ""
    lin = _linhas_csv(emit_csv.emit(_fatura("Loja Normal")))[1]
    assert lin[1] == "Loja Normal"
