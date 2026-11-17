# -*- coding: utf-8 -*-
"""Emissor XLSX (planilha de prestacao de contas) a partir de um FaturaParsed.

Segue a paleta da marca (design-system/MASTER.md, mesmo padrao do
`conversor-extrato/scripts/engine/emit_xlsx.py`): cabecalho esmeralda,
internacional em ambar, veredicto colorido. Mostra os DOIS totais (calculado
vs impresso) lado a lado no bloco de metadados — honestidade brutal: o
operador ve de cara se e onde a prova de completude bateu.
"""
from __future__ import annotations

from decimal import Decimal

from emit_csv import _texto
from modelo import BAIXA_CONFIANCA, OK, TOTAL_NAO_FECHA, FaturaParsed

# Marca (design-system/MASTER.md); mesmas cores dos irmaos (conversor-extrato/inteligencia-boleto).
_ESMERALDA = "FF047857"
_BRANCO = "FFFFFFFF"
_WASH_AMBAR = "FFFEF3C7"     # internacional (fundo)
_TXT_AMBAR = "FF92400E"      # internacional (texto)
_WASH_VERMELHO = "FFFEE2E2"  # veredicto reprovado
_TXT_VERMELHO = "FFB91C1C"
_WASH_VERDE = "FFE7F6EF"     # veredicto OK

_FORMATO_CONTABIL = "#,##0.00"
_COLUNAS_TABELA = ["Data", "Portador", "Estabelecimento", "Parcela", "Valor", "Moeda"]


def emit(fatura: FaturaParsed, path: str) -> None:
    """FaturaParsed -> arquivo .xlsx branded em `path` (aba unica "Fatura")."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Fatura"

    linha = 1

    def _linha_meta(rotulo: str, valor) -> None:
        nonlocal linha
        ws.cell(row=linha, column=1, value=rotulo).font = Font(bold=True)
        ws.cell(row=linha, column=2, value=valor if valor is not None else "")
        linha += 1

    _linha_meta("Emissor", fatura.emissor or "")
    _linha_meta("Portadores", _texto(", ".join(fatura.portadores)) if fatura.portadores else "")
    _linha_meta("Vencimento", fatura.vencimento.strftime("%d/%m/%Y") if fatura.vencimento else "")
    _linha_meta("Total calculado", float(fatura.total_calculado))
    _linha_meta(
        "Total impresso na fatura",
        float(fatura.total_fatura) if fatura.total_fatura is not None else "(nao encontrado)",
    )
    veredicto_cell_row = linha
    _linha_meta("Veredicto", fatura.veredicto)
    if fatura.aviso:
        _linha_meta("Aviso", fatura.aviso)

    cor_veredicto = {
        OK: _WASH_VERDE,
        TOTAL_NAO_FECHA: _WASH_VERMELHO,
        BAIXA_CONFIANCA: _WASH_AMBAR,
    }.get(fatura.veredicto)
    if cor_veredicto:
        ws.cell(row=veredicto_cell_row, column=2).fill = PatternFill("solid", fgColor=cor_veredicto)

    linha += 1  # linha em branco antes da tabela
    linha_cabecalho_tabela = linha

    for j, titulo in enumerate(_COLUNAS_TABELA, 1):
        c = ws.cell(row=linha_cabecalho_tabela, column=j, value=titulo)
        c.fill = PatternFill("solid", fgColor=_ESMERALDA)
        c.font = Font(bold=True, color=_BRANCO)
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[linha_cabecalho_tabela].height = 20
    ws.freeze_panes = f"A{linha_cabecalho_tabela + 1}"

    largura = {"A": 12, "B": 22, "C": 34, "D": 10, "E": 14, "F": 8}
    for col, w in largura.items():
        ws.column_dimensions[col].width = w

    linha_dados_inicio = linha_cabecalho_tabela + 1
    linha = linha_dados_inicio
    total = Decimal("0.00")
    for lanc in fatura.lancamentos:
        total += lanc.valor
        ws.cell(row=linha, column=1, value=lanc.data)
        ws.cell(row=linha, column=1).number_format = "DD/MM/YYYY"
        ws.cell(row=linha, column=2, value=_texto(lanc.portador or ""))
        ws.cell(row=linha, column=3, value=_texto(lanc.estabelecimento or ""))
        ws.cell(row=linha, column=4, value=lanc.parcela or "")

        cell_valor = ws.cell(row=linha, column=5, value=float(lanc.valor))
        cell_valor.number_format = _FORMATO_CONTABIL

        ws.cell(row=linha, column=6, value=lanc.moeda)

        if lanc.internacional:
            for j in (5, 6):
                cel = ws.cell(row=linha, column=j)
                cel.fill = PatternFill("solid", fgColor=_WASH_AMBAR)
                cel.font = Font(color=_TXT_AMBAR)

        linha += 1

    for enc in fatura.encargos:
        total += enc.valor
        ws.cell(row=linha, column=3, value=f"Encargo: {enc.rotulo}").font = Font(italic=True)
        cell_valor = ws.cell(row=linha, column=5, value=float(enc.valor))
        cell_valor.number_format = _FORMATO_CONTABIL
        linha += 1

    linha_total = linha
    ws.cell(row=linha_total, column=3, value="Total").font = Font(bold=True)
    cell_total = ws.cell(row=linha_total, column=5, value=float(total))
    cell_total.number_format = _FORMATO_CONTABIL
    cell_total.font = Font(bold=True)

    n_ultima_coluna = get_column_letter(len(_COLUNAS_TABELA))
    if linha > linha_dados_inicio:
        ws.auto_filter.ref = f"A{linha_cabecalho_tabela}:{n_ultima_coluna}{linha - 1}"

    wb.save(path)
