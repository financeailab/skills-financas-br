# -*- coding: utf-8 -*-
"""Emissor CSV a partir de um FaturaParsed.

Formato: `data;portador;estabelecimento;parcela;valor;moeda;internacional`,
separador ';' (padrao BR, evita colidir com virgula decimal), encoding UTF-8
com BOM (Excel BR abre acentuado sem precisar "importar dados"). Colunas de
dinheiro em texto puro (ponto decimal + sinal), sem formatacao nativa; quem
quer isso usa o XLSX.
"""
from __future__ import annotations

from modelo import FaturaParsed

_SEP = ";"
_CABECALHO = _SEP.join(
    ["data", "portador", "estabelecimento", "parcela", "valor", "moeda", "internacional"]
)


_GATILHOS_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _texto(v):
    """Texto que o Excel leria como formula ganha apostrofo (padrao da casa).
    Numero, data e Decimal passam iguais."""
    if isinstance(v, str) and v[:1] in _GATILHOS_FORMULA:
        return "'" + v
    return v


def _escapar_csv(campo: str) -> str:
    """Escape minimo estilo CSV: aspas duplas em volta se o campo tiver o separador,
    aspas ou quebra de linha; aspas internas viram par duplo (regra RFC 4180)."""
    if _SEP in campo or '"' in campo or "\n" in campo or "\r" in campo:
        return '"' + campo.replace('"', '""') + '"'
    return campo


def emit(fatura: FaturaParsed) -> str:
    """FaturaParsed -> texto CSV completo (com BOM), pronto para escrever em disco."""
    linhas = [_CABECALHO]
    for lanc in fatura.lancamentos:
        linhas.append(_SEP.join([
            lanc.data.strftime("%Y-%m-%d"),
            _escapar_csv(_texto(lanc.portador or "")),
            _escapar_csv(_texto(lanc.estabelecimento or "")),
            lanc.parcela or "",
            f"{lanc.valor:.2f}",
            lanc.moeda,
            "sim" if lanc.internacional else "nao",
        ]))
    for enc in fatura.encargos:
        linhas.append(_SEP.join([
            "", "", _escapar_csv(f"Encargo: {enc.rotulo}"), "", f"{enc.valor:.2f}", "BRL", "nao",
        ]))

    texto = "\r\n".join(linhas) + "\r\n"
    return "﻿" + texto
