# -*- coding: utf-8 -*-
"""Categoriza a descricao de um lancamento realizado num balde fixo (SPEC-00 §3):
dicionario BR editavel (`dicionario-categorias.csv`, CSV `categoria,keyword`),
sem chute nenhum quando nao bate.

Precedencia (SPEC-00 §3): contas-proprias > keyword mais longa > primeira na
ordem da tabela. Cada lancamento sai com `regra_aplicada` (auditavel: da pra
ver POR QUE aquele lancamento caiu naquela categoria).
"""
from __future__ import annotations

import csv
import os

from normalize import _sem_acento

CATEGORIA_TRANSFERENCIAS = "Transferências Internas"
CATEGORIA_NAO_CLASSIFICADO = "Não classificado"

_DICIONARIO_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "dicionario-categorias.csv"))


def caminho_dicionario_default() -> str:
    return _DICIONARIO_DEFAULT


def carregar_dicionario(caminho: str | None = None) -> list[tuple[str, str]]:
    """Le o CSV `categoria,keyword`, preservando a ordem das linhas (define a
    ordem de tabela usada no desempate de `categorizar`). `caminho=None` usa o
    dicionario padrao ao lado do motor (`dicionario-categorias.csv`)."""
    caminho = caminho or _DICIONARIO_DEFAULT
    pares: list[tuple[str, str]] = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            categoria = (linha.get("categoria") or "").strip()
            keyword = (linha.get("keyword") or "").strip()
            if categoria and keyword:
                pares.append((categoria, _normaliza(keyword)))
    return pares


def _normaliza(texto) -> str:
    return _sem_acento(str(texto or "")).upper()


def categorizar(descricao: str, dicionario: list[tuple[str, str]],
                contas_proprias=None) -> tuple[str, str]:
    """Categoriza uma descricao. Retorna `(categoria, regra_aplicada)`.

    - camada 1 (contas-proprias): se a descricao contiver um identificador de
      conta propria, e SEMPRE Transferencias Internas, mesmo que uma keyword de
      outra categoria (ex.: "PIX ENVIADO") tambem bata.
    - camada 2 (keyword): entre as keywords que aparecem na descricao, vence a
      mais longa; empate (mesmo tamanho) vence quem aparece primeiro na ordem
      do dicionario (ordem de tabela, SPEC-00 §3).
    - sem match nenhum: "Não classificado", regra "sem-match" (nunca chuta).
    """
    desc_norm = _normaliza(descricao)

    if contas_proprias:
        for ident in contas_proprias:
            if ident and _normaliza(ident) in desc_norm:
                return CATEGORIA_TRANSFERENCIAS, f"conta-propria:{ident}"

    melhor = None  # (indice, categoria, keyword)
    for idx, (categoria, keyword) in enumerate(dicionario):
        if not keyword or keyword not in desc_norm:
            continue
        if melhor is None or len(keyword) > len(melhor[2]):
            melhor = (idx, categoria, keyword)
    if melhor is not None:
        _idx, categoria, keyword = melhor
        return categoria, f"keyword:{categoria}:{keyword}"

    return CATEGORIA_NAO_CLASSIFICADO, "sem-match"
