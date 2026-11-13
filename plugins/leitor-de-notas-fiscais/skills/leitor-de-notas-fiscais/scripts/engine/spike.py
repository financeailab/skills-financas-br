from __future__ import annotations

from engine.avaliacao import avaliar_nfe, avaliar_nfse
from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.parsers.xml_nfe import parse_nfe


def processar_nfse(xml_str: str) -> dict:
    return avaliar_nfse(parse_nfse_nacional(xml_str))


def processar_nfe(xml_str: str) -> dict:
    return avaliar_nfe(parse_nfe(xml_str))
