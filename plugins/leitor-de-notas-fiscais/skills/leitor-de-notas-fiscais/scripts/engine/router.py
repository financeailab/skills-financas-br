from __future__ import annotations

import xml.etree.ElementTree as ET
from enum import Enum

from engine.parsers._helpers import _local
from engine.parsers._safe_xml import parse as parse_xml_seguro


class Familia(str, Enum):
    NFSE_NACIONAL = "nfse_nacional"
    NFSE_ABRASF = "nfse_abrasf"
    NFSE_SP = "nfse_sp"
    NFE = "nfe"
    DESCONHECIDO = "desconhecido"


def classificar(xml_str: str) -> Familia:
    """Classifica o XML por namespace (prioritário) e, na ausência dele, por tags-âncora."""
    try:
        root = parse_xml_seguro(xml_str)
    except ET.ParseError:  # invalido OU rejeitado por seguranca (XXE/DTD, SAN-07 S-01)
        return Familia.DESCONHECIDO

    # Namespace do elemento raiz (não percorre filhos). Tem prioridade sobre tags-âncora,
    # para que uma tag-filha homônima (ex.: infNFSe dentro de doc ABRASF) não cause falso-positivo.
    ns = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    if "sped.fazenda.gov.br/nfse" in ns:
        return Familia.NFSE_NACIONAL
    if "prefeitura.sp.gov.br" in ns:
        return Familia.NFSE_SP
    if "portalfiscal.inf.br/nfe" in ns:
        return Familia.NFE
    if "abrasf" in ns:
        return Familia.NFSE_ABRASF

    # Sem namespace conhecido na raiz: recai sobre tags-âncora (envelopes/lotes sem ns na raiz).
    locais = {_local(el.tag) for el in root.iter()}
    if "infNFSe" in locais:
        return Familia.NFSE_NACIONAL
    if "ChaveNFe" in locais:
        return Familia.NFSE_SP
    if "infNFe" in locais:
        return Familia.NFE
    if "InfNfse" in locais or "CompNfse" in locais:
        return Familia.NFSE_ABRASF
    if "InfRps" in locais or "Rps" in locais:
        return Familia.NFSE_ABRASF   # RPS = pre-NFS-e, mesmo parser ABRASF
    return Familia.DESCONHECIDO
