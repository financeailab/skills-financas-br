# -*- coding: utf-8 -*-
"""Ingestao de tabelas (CSV / XLSX) -> lista de dicts (linhas cruas, colunas originais).

Usado para a RAZAO contabil / ERP (lado contabil da conciliacao bancaria).

Detecta encoding e separador sozinho. Nao interpreta semantica aqui — quem da
sentido as colunas (qual e data, valor, doc) e a estrategia de matching.
"""
from __future__ import annotations

import csv
import io
import os

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB — PRD-SAN-07 S-06 (anti-OOM em arquivo gigante)


def _checar_tamanho(caminho: str) -> None:
    """Recusa arquivo acima de 100 MB ANTES de carregar o conteudo em memoria."""
    tam = os.path.getsize(caminho)
    if tam > MAX_FILE_SIZE:
        raise ValueError(
            f"arquivo recusado: {os.path.basename(caminho)} tem {tam // (1024 * 1024)} MB "
            f"(limite: {MAX_FILE_SIZE // (1024 * 1024)} MB); exporte um recorte menor")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def read_csv(caminho: str) -> list[dict]:
    _checar_tamanho(caminho)
    raw = open(caminho, "rb").read()
    txt = _decode(raw)
    primeira = txt.splitlines()[0] if txt else ""
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    linhas = list(csv.DictReader(io.StringIO(txt), delimiter=sep))
    # normaliza chaves (tira espacos)
    return [{(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in linhas]


def read_xlsx(caminho: str, aba: str | None = None) -> list[dict]:
    _checar_tamanho(caminho)  # antes do import: recusa nao depende de openpyxl instalado
    import openpyxl  # dependencia opcional; so carrega se precisar de xlsx
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb[aba] if aba else wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    try:
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
    except StopIteration:
        return []
    out = []
    for r in rows:
        if r is None or all(c is None for c in r):
            continue
        out.append({header[i]: (str(r[i]).strip() if isinstance(r[i], str) else r[i])
                    for i in range(min(len(header), len(r)))})
    return out


def read_tabular(caminho: str, aba: str | None = None) -> list[dict]:
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return read_xlsx(caminho, aba)
    return read_csv(caminho)
