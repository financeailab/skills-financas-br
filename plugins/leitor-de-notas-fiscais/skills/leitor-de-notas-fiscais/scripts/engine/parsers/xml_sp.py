from __future__ import annotations

from engine.model import NFSeServico
from engine.normalizacao import iss_e_retido, normalizar_aliquota, tipo_retencao_de_booleano
from engine.parsers._helpers import campo_xml, dec, find_text_em_grupo
from engine.parsers._safe_xml import parse as parse_xml_seguro
from engine.parsers.aliases import (
    ALIASES_SP,
    ALVOS_TOMADOR_CNPJ,
    ALVOS_TOMADOR_MUNICIPIO,
    GRUPOS_TOMADOR,
    resolver_alias,
)


def parse_nfse_sp(xml_str: str) -> NFSeServico:
    """Parser da Nota Fiscal Paulistana (SP próprio) via camada de alias + normalização de alíquota."""
    root = parse_xml_seguro(xml_str)

    def txt(campo_canonico: str) -> str | None:
        valor, _usado = resolver_alias(root, ALIASES_SP.get(campo_canonico, []))
        return valor

    retido = iss_e_retido(txt("iss_retido"))

    _dest = find_text_em_grupo(root, GRUPOS_TOMADOR, ALVOS_TOMADOR_CNPJ)
    _mun_tom = find_text_em_grupo(root, GRUPOS_TOMADOR, ALVOS_TOMADOR_MUNICIPIO)

    return NFSeServico(
        destinatario_doc=campo_xml(_dest) if _dest else None,
        municipio_tomador=campo_xml(_mun_tom) if _mun_tom else None,
        numero=campo_xml(txt("numero")),
        codigo_verificacao=campo_xml(txt("codigo_verificacao")),
        data_emissao=campo_xml(txt("data_emissao")),
        emitente_cnpj=campo_xml(txt("emitente_cnpj")),
        emitente_nome=campo_xml(txt("emitente_nome")),
        codigo_servico=campo_xml(txt("codigo_servico")),
        discriminacao=campo_xml(txt("discriminacao")),
        iss_retido=campo_xml("true" if retido else "false"),
        iss_tipo_retencao=campo_xml(tipo_retencao_de_booleano(retido)),
        valor_servicos=campo_xml(dec(txt("valor_servicos"))),
        iss_base=campo_xml(dec(txt("iss_base"))),
        iss_aliquota=campo_xml(normalizar_aliquota(dec(txt("iss_aliquota")))),
        iss_valor=campo_xml(dec(txt("iss_valor"))),
        valor_liquido=campo_xml(dec(txt("valor_liquido"))),
    )
