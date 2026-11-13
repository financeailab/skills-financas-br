"""Exporter XLSX (planilha de trabalho do analista), ao lado do carga.csv.

3 abas (Carga / Conferir / Resumo), identidade da marca (esmeralda), status colorido,
moeda/data NATIVAS do Excel (valores crus Decimal/ISO + number_format -> Excel ordena e soma).
O CSV nao muda; este modulo so adiciona uma saida.

Fonte unica do que e data/decimal: `_DATAS` e `_DECIMAIS` de engine.export.csv_generico.
"""
from __future__ import annotations

import datetime as _dt
import io
from decimal import Decimal

import openpyxl
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from engine.export.csv_generico import _DATAS, _DECIMAIS

COLUNAS_XLSX = (
    "arquivo_origem", "fornecedor_nome", "fornecedor_cnpj", "tipo_documento",
    "data_emissao", "vencimento", "valor_total", "valor_liquido", "ret_federal_total",
    "natureza_operacao", "cancelada", "status", "confianca_nota", "motivos",
)
TITULOS = {
    "arquivo_origem": "Arquivo", "fornecedor_nome": "Fornecedor", "fornecedor_cnpj": "CNPJ",
    "tipo_documento": "Tipo", "data_emissao": "Emissao", "vencimento": "Vencimento",
    "valor_total": "Valor total", "valor_liquido": "Valor liquido", "ret_federal_total": "Ret. federal",
    "natureza_operacao": "Natureza", "cancelada": "Cancelada", "status": "Status",
    "confianca_nota": "Confianca", "motivos": "Motivos",
}

# Marca (design-system/MASTER.md). ARGB de 8 chars: alfa "FF" + RGB.
_ESMERALDA = "FF047857"
_BRANCO = "FFFFFFFF"
_WASH = "FFE7F6EF"
_AMBAR = "FFFEF3C7"
_AMBAR_TXT = "FF92400E"
_VERMELHO = "FFFEE2E2"
_INK = "FF1A1A18"
_LARGURA = {"fornecedor_nome": 32, "motivos": 52, "arquivo_origem": 26, "fornecedor_cnpj": 18,
            "valor_total": 14, "valor_liquido": 14, "ret_federal_total": 13, "natureza_operacao": 22}


def _data(v):
    """ISO -> datetime.date (Excel ordena). Texto fora do padrao volta como str."""
    if not v:
        return None
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return str(v)


def _num(v):
    """Decimal/int/float -> float (Excel soma). Vazio -> None. Resto volta como veio."""
    return float(v) if isinstance(v, (Decimal, int, float)) else (None if v in (None, "") else v)


def _aba_tabela(ws, linhas):
    # cabecalho
    for j, col in enumerate(COLUNAS_XLSX, 1):
        c = ws.cell(row=1, column=j, value=TITULOS[col])
        c.fill = PatternFill("solid", fgColor=_ESMERALDA)
        c.font = Font(bold=True, color=_BRANCO)
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = _LARGURA.get(col, 15)
    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"
    # linhas
    for i, ln in enumerate(linhas, 2):
        for j, col in enumerate(COLUNAS_XLSX, 1):
            v = ln.get(col)
            if col in _DATAS:
                cell = ws.cell(row=i, column=j, value=_data(v))
                cell.number_format = "DD/MM/YYYY"
            elif col == "confianca_nota":
                cell = ws.cell(row=i, column=j, value=_num(v))
                cell.number_format = "0%"
            elif col in _DECIMAIS:
                cell = ws.cell(row=i, column=j, value=_num(v))
                cell.number_format = "R$ #,##0.00"
            else:
                cell = ws.cell(row=i, column=j, value="" if v is None else str(v))
            if isinstance(cell.value, str):
                cell.data_type = "s"  # texto do arquivo nunca vira formula (D17 da Conciliacao)
            if col == "status":
                fill = _WASH if v == "auto-aprovada" else _AMBAR
                cell.fill = PatternFill("solid", fgColor=fill)
                if v != "auto-aprovada":
                    cell.font = Font(color=_AMBAR_TXT)
                cell.alignment = Alignment(horizontal="center")
            if col == "cancelada" and str(v).lower() == "sim":
                cell.fill = PatternFill("solid", fgColor=_VERMELHO)
                cell.font = Font(bold=True)
            if col == "motivos":
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    n = len(linhas) + 1
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS_XLSX))}{n}"
    # escala de cor na confianca (vermelho -> amarelo -> verde)
    cc = get_column_letter(COLUNAS_XLSX.index("confianca_nota") + 1)
    if linhas:
        ws.conditional_formatting.add(f"{cc}2:{cc}{n}", ColorScaleRule(
            start_type="num", start_value=0, start_color="FFF87171",
            mid_type="num", mid_value=0.7, mid_color="FFFCD34D",
            end_type="num", end_value=1, end_color="FF34D399"))


def exportar_xlsx(linhas: list[dict], resumo: dict) -> bytes:
    """linhas (grao da carga) + resumo -> bytes de um .xlsx branded com 3 abas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Carga"
    _aba_tabela(ws, linhas)

    conferir = [l for l in linhas if l.get("status") != "auto-aprovada"]
    _aba_tabela(wb.create_sheet("Conferir"), conferir)

    rs = wb.create_sheet("Resumo")
    rs["A1"] = "Resumo da carga"
    rs["A1"].font = Font(bold=True, size=14, color=_ESMERALDA)
    dados = [("Total de notas", resumo.get("total", 0)),
             ("Auto-aprovadas", resumo.get("auto_aprovadas", 0)),
             ("Conferir", resumo.get("conferir", 0)),
             ("Falhou", resumo.get("falhou", 0)),
             ("Recebidas", resumo.get("recebidas", 0)),
             ("Fora do limite", resumo.get("fora_do_limite", 0)),
             ("Repetidas", resumo.get("repetidas", 0))]
    for k, (rotulo, val) in enumerate(dados, 3):
        rs.cell(row=k, column=1, value=rotulo).font = Font(bold=True)
        rs.cell(row=k, column=2, value=val)
    r = 3 + len(dados) + 1
    rs.cell(row=r, column=1, value="Por tipo/familia").font = Font(bold=True)
    # lote XML guarda a quebra em por_familia; lote PDF em por_tipo. Le os dois (fallback).
    quebra = resumo.get("por_tipo") or resumo.get("por_familia") or {}
    for k, (tp, val) in enumerate(sorted(quebra.items()), r + 1):
        rs.cell(row=k, column=1, value=tp)
        rs.cell(row=k, column=2, value=val)
    rs.column_dimensions["A"].width = 22

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
