# -*- coding: utf-8 -*-
"""Exportadores da saida do DFC: XLSX multi-abas colorido (SPEC-00 §7), CSV (1
por aba, mesmo conteudo) e JSON (tudo numa estrutura). Paleta esmeralda /
ambar / vermelho, mesmo padrao visual dos motores irmaos (validador-reembolso,
inteligencia-boleto, conciliacao-bancaria).

As 5 abas, nesta ordem: Resumo, Realizado, Lançamentos, Títulos em aberto,
Alertas.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import date
from decimal import Decimal

ZERO = Decimal("0.00")

FRASE_HONESTIDADE = "Projeção assume título pago no vencimento. Não é conciliação nem garantia."

NOMES_ABAS = ["Resumo", "Realizado", "Lançamentos", "Títulos em aberto", "Alertas"]

ORDEM_CATEGORIAS_PADRAO = [
    "Recebimentos", "Fornecedores", "Impostos/Tributos", "Folha & Benefícios",
    "Aluguel/Ocupação", "Tarifas Bancárias", "Aplicações/Resgates",
    "Transferências Internas", "Fatura de Cartão", "Não classificado",
]

# paleta on-brand (Finance AI Lab, light-first esmeralda); ARGB p/ openpyxl.
_ESMERALDA = "FF047857"
_BRANCO = "FFFFFFFF"
_INK = "FF1A1A18"
_MUT = "FF6B6A64"
_FILL = {"verde": "FFE7F6EF", "ambar": "FFFDE8C8", "vermelho": "FFF8D7DA"}
_TXT = {"verde": "FF047857", "ambar": "FF8A5A00", "vermelho": "FF9B1C23"}
_BRL_FMT = 'R$ #,##0.00;[Red]-R$ #,##0.00'

_ALERTA_GRAVE = {"SEMANA_NEGATIVA", "ATRASADO_EM_ABERTO"}


_GATILHOS_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _texto(v):
    """Texto que o Excel leria como formula ganha apostrofo (padrao da casa,
    capturador-de-notas/motor/engine/base.py). Numero, data e Decimal passam iguais."""
    if isinstance(v, str) and v[:1] in _GATILHOS_FORMULA:
        return "'" + v
    return v


class XlsxIndisponivel(RuntimeError):
    """openpyxl nao esta instalado."""


def _ordenar_categorias(categorias_presentes) -> list[str]:
    ordem = {c: i for i, c in enumerate(ORDEM_CATEGORIAS_PADRAO)}
    return sorted(categorias_presentes, key=lambda c: (ordem.get(c, len(ORDEM_CATEGORIAS_PADRAO)), c))


# --- preparo de dados (puro, compartilhado por XLSX/CSV) ---

def linhas_semanas(resultado) -> tuple[list[str], list[list]]:
    headers = ["Semana", "Entradas", "Saídas", "Saldo"]
    rows = [[s["semana"], s["entradas"], s["saidas"], s["saldo"]] for s in resultado.semanas]
    return headers, rows


def linhas_realizado(resultado) -> tuple[list[str], list[list]]:
    meses = sorted({mes for _cat, mes in resultado.realizado_categoria_mes})
    categorias = _ordenar_categorias({cat for cat, _mes in resultado.realizado_categoria_mes})
    headers = ["Categoria"] + meses + ["Total"]
    rows = []
    for cat in categorias:
        valores = [resultado.realizado_categoria_mes.get((cat, mes), ZERO) for mes in meses]
        rows.append([cat] + valores + [sum(valores, ZERO)])
    return headers, rows


def linhas_lancamentos(resultado) -> tuple[list[str], list[list]]:
    headers = ["Data", "Conta", "Descrição", "Valor", "Categoria", "Regra aplicada"]
    ordenados = sorted(resultado.lancamentos, key=lambda l: (l["data"], l["conta_id"]))
    rows = [[l["data"], l["conta_id"], l["descricao"], l["valor"], l["categoria"], l["regra_aplicada"]]
            for l in ordenados]
    return headers, rows


def linhas_titulos(resultado) -> tuple[list[str], list[list]]:
    headers = ["Tipo", "Contraparte", "Documento", "Vencimento", "Valor", "Status", "Semana", "Atrasado"]
    ordenados = sorted(resultado.titulos_em_aberto, key=lambda t: (t["vencimento"], t["tipo"]))
    rows = [[t["tipo"], t.get("contraparte", ""), t.get("documento", ""), t["vencimento"], t["valor"],
             t.get("status_raw", ""), t["semana"], "Sim" if t["atrasado"] else "Não"]
            for t in ordenados]
    return headers, rows


def linhas_alertas(resultado) -> tuple[list[str], list[list]]:
    headers = ["Tipo", "Detalhe"]
    rows = [[a["tipo"], a["detalhe"]] for a in resultado.alertas]
    return headers, rows


# --- XLSX ---

def montar_workbook(resultado, data_base):
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise XlsxIndisponivel("openpyxl não instalado") from e

    wb = Workbook()
    _aba_resumo(wb.active, resultado, data_base)
    _aba_realizado(wb.create_sheet(NOMES_ABAS[1]), resultado)
    _aba_lancamentos(wb.create_sheet(NOMES_ABAS[2]), resultado)
    _aba_titulos(wb.create_sheet(NOMES_ABAS[3]), resultado)
    _aba_alertas(wb.create_sheet(NOMES_ABAS[4]), resultado)
    return wb


def _cabecalho(ws, headers, cor=_ESMERALDA):
    from openpyxl.styles import Font, PatternFill, Alignment
    for j, texto in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=texto)
        c.fill = PatternFill("solid", fgColor=cor)
        c.font = Font(bold=True, color=_BRANCO)
        c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"


def _aba_resumo(ws, resultado, data_base):
    from openpyxl.styles import Font, PatternFill, Alignment

    ws.title = NOMES_ABAS[0]
    ws.sheet_view.showGridLines = False
    for col, wid in (("A", 14), ("B", 16), ("C", 16), ("D", 16)):
        ws.column_dimensions[col].width = wid

    ws["A1"] = "Fluxo de Caixa Direto"
    ws["A1"].font = Font(bold=True, size=16, color=_INK)
    ws["A2"] = f"Data-base: {data_base.isoformat()}"
    ws["A2"].font = Font(size=10, color=_MUT)
    ws["A3"] = "Saldo atual"
    ws["A3"].font = Font(bold=True, size=10, color=_MUT)
    ws["B3"] = float(resultado.saldo_inicial)
    ws["B3"].number_format = _BRL_FMT
    ws["B3"].font = Font(bold=True, size=13, color=_ESMERALDA)

    linha_header = 5
    for j, texto in enumerate(["Semana", "Entradas", "Saídas", "Saldo"], start=1):
        c = ws.cell(row=linha_header, column=j, value=texto)
        c.fill = PatternFill("solid", fgColor=_ESMERALDA)
        c.font = Font(bold=True, color=_BRANCO)
        c.alignment = Alignment(indent=1)

    linha = linha_header + 1
    for s in resultado.semanas:
        ws.cell(row=linha, column=1, value=s["semana"])
        for col, chave in ((2, "entradas"), (3, "saidas"), (4, "saldo")):
            cell = ws.cell(row=linha, column=col, value=float(s[chave]))
            cell.number_format = _BRL_FMT
            if chave == "saldo" and s[chave] < 0:
                cell.fill = PatternFill("solid", fgColor=_FILL["vermelho"])
                cell.font = Font(color=_TXT["vermelho"], bold=True)
        linha += 1

    linha += 1
    ws.cell(row=linha, column=1, value=f"Alertas: {len(resultado.alertas)} (ver aba Alertas)").font = \
        Font(italic=True, size=10, color=_MUT)
    linha += 2
    ws.cell(row=linha, column=1, value=FRASE_HONESTIDADE).font = Font(italic=True, size=8, color=_MUT)


def _aba_realizado(ws, resultado):
    from openpyxl.styles import Font, PatternFill

    headers, rows = linhas_realizado(resultado)
    _cabecalho(ws, headers)
    ws.column_dimensions["A"].width = 26
    for i, row in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=_texto(row[0]))
        for j, valor in enumerate(row[1:], start=2):
            cell = ws.cell(row=i, column=j, value=float(valor))
            cell.number_format = _BRL_FMT
            if valor > 0:
                cell.fill = PatternFill("solid", fgColor=_FILL["verde"])
            elif valor < 0:
                cell.fill = PatternFill("solid", fgColor=_FILL["vermelho"])


def _aba_lancamentos(ws, resultado):
    headers, rows = linhas_lancamentos(resultado)
    _cabecalho(ws, headers)
    larguras = {1: 13, 2: 14, 3: 42, 4: 15, 5: 22, 6: 34}
    from openpyxl.utils import get_column_letter
    for col, wid in larguras.items():
        ws.column_dimensions[get_column_letter(col)].width = wid
    for i, row in enumerate(rows, start=2):
        for j, valor in enumerate(row, start=1):
            cell = ws.cell(row=i, column=j, value=(float(valor) if j == 4 else _texto(valor)))
            if j == 4:
                cell.number_format = _BRL_FMT


def _aba_titulos(ws, resultado):
    from openpyxl.styles import PatternFill, Font

    headers, rows = linhas_titulos(resultado)
    _cabecalho(ws, headers)
    from openpyxl.utils import get_column_letter
    for col, wid in {1: 12, 2: 26, 3: 16, 4: 14, 5: 14, 6: 16, 7: 10, 8: 10}.items():
        ws.column_dimensions[get_column_letter(col)].width = wid
    for i, row in enumerate(rows, start=2):
        for j, valor in enumerate(row, start=1):
            cell = ws.cell(row=i, column=j, value=(float(valor) if j == 5 else _texto(valor)))
            if j == 5:
                cell.number_format = _BRL_FMT
        if row[-1] == "Sim":  # atrasado
            for j in range(1, len(headers) + 1):
                ws.cell(row=i, column=j).fill = PatternFill("solid", fgColor=_FILL["ambar"])
            ws.cell(row=i, column=len(headers)).font = Font(bold=True, color=_TXT["ambar"])


def _aba_alertas(ws, resultado):
    from openpyxl.styles import PatternFill, Alignment

    headers, rows = linhas_alertas(resultado)
    _cabecalho(ws, headers)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 80
    for i, row in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=_texto(row[0]))
        cell_detalhe = ws.cell(row=i, column=2, value=_texto(row[1]))
        cor = "vermelho" if row[0] in _ALERTA_GRAVE else "ambar"
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor=_FILL[cor])
        cell_detalhe.alignment = Alignment(wrap_text=True)


def exportar_xlsx(resultado, data_base, caminho: str) -> str:
    wb = montar_workbook(resultado, data_base)
    pasta = os.path.dirname(os.path.abspath(caminho))
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    wb.save(caminho)
    return caminho


# --- CSV (1 por aba, mesmo conteudo) ---

def _grava_csv(caminho, headers, rows):
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(headers)
        for row in rows:
            w.writerow(["" if v is None else _texto(v) for v in row])


def exportar_csv(resultado, data_base, pasta: str) -> list[str]:
    os.makedirs(pasta, exist_ok=True)
    mapa = {
        "resumo": linhas_semanas(resultado),
        "realizado": linhas_realizado(resultado),
        "lancamentos": linhas_lancamentos(resultado),
        "titulos_em_aberto": linhas_titulos(resultado),
        "alertas": linhas_alertas(resultado),
    }
    caminhos = []
    for nome, (headers, rows) in mapa.items():
        caminho = os.path.join(pasta, f"{nome}.csv")
        _grava_csv(caminho, headers, rows)
        caminhos.append(caminho)
    return caminhos


# --- JSON (tudo numa estrutura) ---

def _json_default(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"tipo nao serializavel: {type(o)!r}")


def montar_estrutura_json(resultado, data_base) -> dict:
    return {
        "data_base": data_base.isoformat(),
        "saldo_inicial": resultado.saldo_inicial,
        "semanas": resultado.semanas,
        "realizado_categoria_mes": [
            {"categoria": cat, "mes": mes, "valor": valor}
            for (cat, mes), valor in resultado.realizado_categoria_mes.items()
        ],
        "lancamentos": resultado.lancamentos,
        "titulos_em_aberto": resultado.titulos_em_aberto,
        "alertas": resultado.alertas,
        "honestidade": FRASE_HONESTIDADE,
    }


def exportar_json(resultado, data_base, caminho: str) -> str:
    pasta = os.path.dirname(os.path.abspath(caminho))
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(montar_estrutura_json(resultado, data_base), f,
                   ensure_ascii=False, indent=2, default=_json_default)
    return caminho
