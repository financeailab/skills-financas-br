from __future__ import annotations

from engine.confidence import score_campo
from engine.model import (
    Campo, Confianca, Fonte, NFeProduto, NFSeServico, CAMPOS_DECIMAIS,
)
from engine.normalizacao import normalizar_decimal_br

_DECIMAIS = CAMPOS_DECIMAIS   # fonte unica (introspeccao do model)


def _campo_pdf(nome: str, item: dict | None) -> Campo | None:
    if item is None:
        return None
    valor = item.get("valor")
    if valor is None or valor == "":
        return None
    if nome in _DECIMAIS:
        convertido = normalizar_decimal_br(valor)
        if convertido is None:
            # texto nao-vazio que nao converteu = valor que DEVERIA existir e nao some em silencio
            return Campo(valor=None, confianca=Confianca(
                score=0.2, fonte=Fonte.INFERIDO, motivo=f"valor decimal ilegivel: '{valor}'"))
        valor = convertido
    base = score_campo(fonte=Fonte.PDF, alias_exato=bool(item.get("rotulo_exato")))
    return Campo(valor=valor, confianca=Confianca(score=base, fonte=Fonte.PDF))


def _campos(extracao: dict) -> dict:
    return {nome: c for nome, item in extracao.items() if (c := _campo_pdf(nome, item)) is not None}


# Metas booleanas (irmas de `campos`): separadas do _campos e convertidas p/ bool.
_METAS_BOOL = ("simples_nacional", "cancelada")


def _meta_bool(extracao: dict, nome: str) -> bool:
    """Le uma meta booleana do topo da extracao (aceita dict {valor:...} ou escalar)."""
    m = extracao.get(nome)
    v = m.get("valor") if isinstance(m, dict) else m
    return str(v).strip().lower() in ("true", "1", "sim", "s") if v is not None else False


def montar_nfse_de_extracao(extracao: dict) -> NFSeServico:
    """Constrói NFSeServico a partir do dict de extração do Claude (fonte=pdf, confiança alias-aware).

    `simples_nacional` e `cancelada` sao metas booleanas (como `tipo_documento`): separadas
    do _campos e convertidas.
    """
    simples = _meta_bool(extracao, "simples_nacional")
    cancelada = _meta_bool(extracao, "cancelada")
    campos = _campos({k: v2 for k, v2 in extracao.items() if k not in _METAS_BOOL})
    return NFSeServico(simples_nacional=simples, cancelada=cancelada, **campos)


def montar_nfe_de_extracao(extracao: dict) -> NFeProduto:
    """`cancelada` e meta booleana (carimbo na nota), separada do _campos e convertida."""
    cancelada = _meta_bool(extracao, "cancelada")
    campos = _campos({k: v2 for k, v2 in extracao.items() if k not in _METAS_BOOL})
    return NFeProduto(cancelada=cancelada, **campos)
