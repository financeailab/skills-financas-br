from __future__ import annotations

from engine.model import Fonte

LIMIAR_ALTA = 0.85
LIMIAR_MEDIA = 0.6


def score_campo(
    fonte: Fonte,
    alias_exato: bool = False,
    invariante_ok: bool | None = None,
    dv_ok: bool | None = None,
) -> float:
    """Score 0-1 deterministico (nao e estimativa do modelo)."""
    if fonte == Fonte.XML:
        base = 1.0
    elif fonte == Fonte.PDF and alias_exato:
        base = 0.9
    elif fonte == Fonte.PDF:
        base = 0.7
    elif fonte == Fonte.INVARIANTE:
        base = 0.4
    else:
        base = 0.5
    if invariante_ok is False:
        base = min(base, 0.3)
    if dv_ok is False:
        base = min(base, 0.3)
    return round(base, 2)


def banda(score: float) -> str:
    if score >= LIMIAR_ALTA:
        return "ALTA"
    if score >= LIMIAR_MEDIA:
        return "MEDIA"
    return "BAIXA"


def score_documento(scores_criticos: list[float]) -> float:
    """Agregacao: o pior campo financeiro critico domina."""
    return min(scores_criticos) if scores_criticos else 0.0
