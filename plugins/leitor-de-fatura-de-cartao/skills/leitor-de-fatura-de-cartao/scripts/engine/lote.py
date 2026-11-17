# -*- coding: utf-8 -*-
"""Modo lote (SPEC-00 §8): consolida ate `LIMITE_LOTE` faturas de uma pasta num
unico CSV/XLSX + resumo agregado + lista de excecoes.

Dedupe por hash sha256 do CONTEUDO do arquivo (nao do nome): o mesmo PDF
processado 2x na mesma pasta (nome repetido ou copia identica) nao duplica
lancamento no consolidado nem entra 2x na contagem do resumo.

Honestidade brutal: o CSV/XLSX consolidado inclui os lancamentos de TODA fatura
processada, mesmo as com veredicto != OK (a coluna `veredicto_fatura` sinaliza
a confiabilidade de cada linha; nunca escondemos dado extraido atras de um
veredicto agregado bonito)."""
from __future__ import annotations

import hashlib
import pathlib
from collections import Counter

from bancos import bradesco, generico, itau
from detector import detectar
from emit_csv import _escapar_csv, _texto
from modelo import LAYOUT_DESCONHECIDO, OK, FaturaParsed
from prova_total import validar as validar_total

LIMITE_LOTE = 12

_PARSERS = {"itau": itau.parse, "bradesco": bradesco.parse, "generico": generico.parse}

_CABECALHO_CONSOLIDADO = ";".join(
    ["arquivo", "veredicto_fatura", "data", "portador", "estabelecimento", "parcela", "valor", "moeda", "internacional"]
)


def _hash_arquivo(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extrair_paginas(pdf_path) -> list:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]


def processar_arquivo(pdf_path, emissor: str = "auto") -> FaturaParsed:
    """PDF -> FaturaParsed. Antifragil de ponta a ponta (achado Codex pre-PR: so a
    extracao era protegida; excecao de deteccao/parse/prova derrubava o lote inteiro
    com stacktrace). Qualquer falha vira uma fatura vazia sinalizada (mesmo
    comportamento do caminho single-file em ler_fatura.ler): um arquivo ruim nunca
    impede os demais do lote."""
    try:
        paginas = _extrair_paginas(pdf_path)
    except Exception as e:  # noqa: BLE001 — nunca propaga stacktrace cru no lote
        fatura = FaturaParsed()
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = f"nao consegui ler o PDF ({type(e).__name__})"
        return fatura

    try:
        nome = detectar(paginas) if emissor == "auto" else emissor
        parse = _PARSERS.get(nome, generico.parse)
        fatura = parse(paginas)
        validar_total(fatura)
        return fatura
    except Exception as e:  # noqa: BLE001 — falha interna do pipeline: sinaliza, nao derruba
        fatura = FaturaParsed()
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = f"erro ao ler a fatura ({type(e).__name__})"
        return fatura


def processar_pasta(pasta, limite: int = LIMITE_LOTE):
    """Varre `pasta` (PDFs, ordem alfabetica), devolve (processadas, duplicatas, excedentes).

    processadas = list[(Path, FaturaParsed)] — ate `limite`, 1a ocorrencia de cada hash.
    duplicatas  = list[Path] — mesmo hash de um arquivo ja processado (nao duplica).
    excedentes  = list[Path] — alem do limite (nao processados; o operador divide o lote).
    """
    arquivos = sorted(p for p in pathlib.Path(pasta).glob("*.pdf"))
    vistos: set[str] = set()
    processadas: list = []
    duplicatas: list = []
    excedentes: list = []

    for p in arquivos:
        try:
            h = _hash_arquivo(p)
        except OSError as e:  # sem permissao ou removido no meio da varredura: vira excecao do lote, nao derruba
            if len(processadas) >= limite:
                excedentes.append(p)
                continue
            fatura = FaturaParsed()
            fatura.veredicto = LAYOUT_DESCONHECIDO
            fatura.aviso = f"nao consegui ler o arquivo ({type(e).__name__})"
            processadas.append((p, fatura))
            continue
        if h in vistos:
            duplicatas.append(p)
            continue
        if len(processadas) >= limite:
            excedentes.append(p)
            continue
        vistos.add(h)
        processadas.append((p, processar_arquivo(p)))

    return processadas, duplicatas, excedentes


def resumo_agregado(processadas, duplicatas, excedentes) -> dict:
    """Contagens agregadas (nunca lancamento a lancamento) p/ stdout — fosso de privacidade."""
    por_ver = Counter(fatura.veredicto for _, fatura in processadas)
    return {
        "total_arquivos": len(processadas) + len(duplicatas) + len(excedentes),
        "processadas": len(processadas),
        "duplicatas": len(duplicatas),
        "excedentes": len(excedentes),
        "por_veredicto": dict(por_ver),
    }


def listar_excecoes(processadas):
    """[(nome_arquivo, veredicto, aviso), ...] das faturas que NAO fecharam em OK."""
    return [
        (p.name, fatura.veredicto, fatura.aviso)
        for p, fatura in processadas
        if fatura.veredicto != OK
    ]


def exportar_csv_consolidado(processadas, path) -> None:
    """1 CSV com os lancamentos e os encargos de TODA fatura processada (BOM UTF-8, `;`-separado)."""
    linhas = [_CABECALHO_CONSOLIDADO]
    for p, fatura in processadas:
        for lanc in fatura.lancamentos:
            linhas.append(";".join([
                _escapar_csv(_texto(p.name)),
                fatura.veredicto,
                lanc.data.strftime("%Y-%m-%d"),
                _escapar_csv(_texto(lanc.portador or "")),
                _escapar_csv(_texto(lanc.estabelecimento or "")),
                lanc.parcela or "",
                f"{lanc.valor:.2f}",
                lanc.moeda,
                "sim" if lanc.internacional else "nao",
            ]))
        for enc in fatura.encargos:  # o encargo entra na prova do veredicto: sem ele a soma do consolidado nao fecha (Gate 2)
            linhas.append(";".join([
                _escapar_csv(_texto(p.name)), fatura.veredicto, "", "",
                _escapar_csv(f"Encargo: {enc.rotulo}"), "", f"{enc.valor:.2f}", "BRL", "nao",
            ]))
    texto = "\r\n".join(linhas) + "\r\n"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("﻿" + texto)


def exportar_xlsx_consolidado(processadas, resumo: dict, path) -> None:
    """1 XLSX branded (abas "Lancamentos" + "Resumo") com os mesmos dados do CSV consolidado."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    _ESMERALDA = "FF047857"
    _BRANCO = "FFFFFFFF"

    wb = Workbook()
    ws = wb.active
    ws.title = "Lancamentos"
    colunas = ["Arquivo", "Veredicto", "Data", "Portador", "Estabelecimento", "Parcela", "Valor", "Moeda"]
    for j, titulo in enumerate(colunas, 1):
        c = ws.cell(row=1, column=j, value=titulo)
        c.fill = PatternFill("solid", fgColor=_ESMERALDA)
        c.font = Font(bold=True, color=_BRANCO)
    ws.freeze_panes = "A2"

    linha = 2
    for p, fatura in processadas:
        for lanc in fatura.lancamentos:
            ws.cell(row=linha, column=1, value=_texto(p.name))
            ws.cell(row=linha, column=2, value=fatura.veredicto)
            cell_data = ws.cell(row=linha, column=3, value=lanc.data)
            cell_data.number_format = "DD/MM/YYYY"
            ws.cell(row=linha, column=4, value=_texto(lanc.portador or ""))
            ws.cell(row=linha, column=5, value=_texto(lanc.estabelecimento or ""))
            ws.cell(row=linha, column=6, value=lanc.parcela or "")
            cell_valor = ws.cell(row=linha, column=7, value=float(lanc.valor))
            cell_valor.number_format = "#,##0.00"
            ws.cell(row=linha, column=8, value=lanc.moeda)
            linha += 1
        for enc in fatura.encargos:
            ws.cell(row=linha, column=1, value=_texto(p.name))
            ws.cell(row=linha, column=2, value=fatura.veredicto)
            ws.cell(row=linha, column=5, value=f"Encargo: {enc.rotulo}")
            cell_valor = ws.cell(row=linha, column=7, value=float(enc.valor))
            cell_valor.number_format = "#,##0.00"
            ws.cell(row=linha, column=8, value="BRL")
            linha += 1

    for col, w in zip("ABCDEFGH", [22, 16, 12, 22, 34, 10, 14, 8]):
        ws.column_dimensions[col].width = w
    if linha > 2:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}{linha - 1}"

    ws2 = wb.create_sheet("Resumo")
    ws2["A1"] = "Resumo do lote"
    ws2["A1"].font = Font(bold=True, size=14, color=_ESMERALDA)
    ws2.cell(row=3, column=1, value="Total de arquivos").font = Font(bold=True)
    ws2.cell(row=3, column=2, value=resumo["total_arquivos"])
    ws2.cell(row=4, column=1, value="Processadas").font = Font(bold=True)
    ws2.cell(row=4, column=2, value=resumo["processadas"])
    ws2.cell(row=5, column=1, value="Duplicatas (hash repetido)").font = Font(bold=True)
    ws2.cell(row=5, column=2, value=resumo["duplicatas"])
    ws2.cell(row=6, column=1, value="Excedentes (alem do limite)").font = Font(bold=True)
    ws2.cell(row=6, column=2, value=resumo["excedentes"])
    ws2.cell(row=8, column=1, value="Por veredicto").font = Font(bold=True)
    for k, (ver, val) in enumerate(sorted(resumo["por_veredicto"].items()), 9):
        ws2.cell(row=k, column=1, value=ver)
        ws2.cell(row=k, column=2, value=val)
    ws2.column_dimensions["A"].width = 28

    wb.save(path)
