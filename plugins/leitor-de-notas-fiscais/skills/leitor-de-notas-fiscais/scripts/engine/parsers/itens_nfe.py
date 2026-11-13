from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal

from engine.parsers._helpers import _local, dec


def _texto_em(el: ET.Element, nome_local: str) -> str | None:
    """1o texto nao-vazio cujo local-name == nome_local, DENTRO de el (path-aware)."""
    for filho in el.iter():
        if _local(filho.tag) == nome_local and filho.text and filho.text.strip():
            return filho.text.strip()
    return None


def _resumir(descricoes: list[str], limite: int = 80) -> str:
    texto = "; ".join(descricoes)
    if len(texto) <= limite:
        return texto
    return texto[: limite - 3].rstrip() + "..."


def agregar_itens(root: ET.Element) -> dict:
    """Deriva agregados-sinal dos <det> da NF-e (grao continua = titulo, nao item)."""
    dets = [el for el in root.iter() if _local(el.tag) == "det"]
    cfops: list[str] = []
    ncms: list[str] = []
    descricoes: list[str] = []
    tem_desconto = False
    for det in dets:
        cfop = _texto_em(det, "CFOP")
        if cfop:
            cfops.append(cfop)
        ncm = _texto_em(det, "NCM")
        if ncm:
            ncms.append(ncm)
        xprod = _texto_em(det, "xProd")
        if xprod:
            descricoes.append(xprod)
        vdesc = dec(_texto_em(det, "vDesc"))
        if vdesc is not None and vdesc > Decimal("0"):
            tem_desconto = True
    return {
        "qtd_itens": len(dets),
        "cfops_distintos": ", ".join(sorted(set(cfops))) if cfops else None,
        "tem_desconto_item": tem_desconto,
        "ncm_predominante": Counter(ncms).most_common(1)[0][0] if ncms else None,
        "descricao_resumida": _resumir(descricoes) if descricoes else None,
    }
