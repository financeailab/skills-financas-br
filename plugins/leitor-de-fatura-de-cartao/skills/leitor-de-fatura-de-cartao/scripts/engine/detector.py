# -*- coding: utf-8 -*-
"""Detector de layout: decide qual parser de emissor aplicar a uma fatura PDF.

Recebe `paginas` (list[dict] com chave "texto" por pagina, ja extraida via
pdfplumber `page.extract_text()`) e devolve "itau" | "bradesco" | "generico"
(fallback best-effort quando nenhuma assinatura bate).

Chaves por ESTILO estrutural (nao por nome literal de banco real — v1 nao tem
corpus real, ver SPEC-00 §3): "tipo-Itau" = cabecalho "Fatura Cartao Corporativo"
(texto corrido, multi-portador); "tipo-Bradesco" = cabecalho "Demonstrativo de
Cartao Corporativo" (tabela posicional por coluna).
"""
from __future__ import annotations

import re

from normalize import _sem_acento

_RE_ITAU = re.compile(r"FATURA CARTAO CORPORATIVO")
_RE_BRADESCO = re.compile(r"DEMONSTRATIVO DE CARTAO CORPORATIVO")


def detectar(paginas: list) -> str:
    """Devolve "itau" | "bradesco" | "generico". Best-effort: nunca lanca excecao."""
    texto = " ".join((p.get("texto") or "") for p in paginas)
    norm = _sem_acento(texto).upper()

    if _RE_ITAU.search(norm):
        return "itau"
    if _RE_BRADESCO.search(norm):
        return "bradesco"
    return "generico"
