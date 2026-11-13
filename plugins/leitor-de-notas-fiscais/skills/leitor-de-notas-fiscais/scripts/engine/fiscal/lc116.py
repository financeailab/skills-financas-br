from __future__ import annotations

import re

# Subitens da LC116/2003 cuja tomada por pessoa juridica obriga a retencao do ISS pelo tomador
# (art. 6 §2, II). Fonte: pesquisa 2026-06-05 (§22.1 do SPEC).
SUBITENS_RETENCAO_OBRIGATORIA = {
    "3.05", "7.02", "7.04", "7.05", "7.09", "7.10", "7.12",
    "7.14", "7.15", "7.16", "7.17", "7.19", "11.02", "17.05", "17.10",
}

_NAO_DIGITO = re.compile(r"\D")


def subitem_lc116(codigo: str | None) -> str | None:
    """Normaliza um codigo de servico (ItemListaServico ABRASF/SP) para o subitem LC116 'G.II'.
    Best-effort: aceita '0702', '07.02', '7.02', '1102' e o nacional de 6 digitos ('070201'). Retorna None se nao der p/ mapear."""
    if not codigo:
        return None
    d = _NAO_DIGITO.sub("", codigo)
    if len(d) == 6:  # cTribNac nacional (item + subitem + desdobro): so os 4 primeiros mapeiam a LC116
        d = d[:4]
    if len(d) < 3 or len(d) > 4:
        return None
    d4 = d.zfill(4)
    grupo = str(int(d4[:2]))   # '07' -> '7'
    item = d4[2:4]
    return f"{grupo}.{item}"


def obriga_retencao_tomador(codigo: str | None) -> bool:
    """True se o subitem do servico esta na lista que obriga retencao pelo tomador (LC116 §2)."""
    s = subitem_lc116(codigo)
    return s in SUBITENS_RETENCAO_OBRIGATORIA if s else False
