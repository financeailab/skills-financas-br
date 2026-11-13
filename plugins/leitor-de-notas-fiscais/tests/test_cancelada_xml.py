"""Captura de cancelamento direto do XML NF-e (achado Codex P2).

cStat 101/151 (cancelamento homologado) ou tpEvento 110111 (evento de cancelamento)
-> nota CANCELADA + forcar_conferir. cStat 100 (autorizado) -> normal (sem falso-positivo).
"""

from engine.dispatch import processar
from engine.parsers.xml_nfe import parse_nfe
from tests.fixtures_status_natureza import NFE_VENDA

# NF-e VENDA normal carimbada com protocolo de CANCELAMENTO homologado (cStat 101)
NFE_CANCELADA_CSTAT = NFE_VENDA.replace(
    "</infNFe></NFe>",
    "</infNFe>"
    "<protNFe><infProt><cStat>101</cStat><xMotivo>Cancelamento de NF-e homologado</xMotivo>"
    "</infProt></protNFe></NFe>",
)

# NF-e com REQUISICAO de evento de cancelamento (tpEvento 110111) SEM status homologado.
# Pode estar rejeitada/nao-homologada -> NAO deve marcar a nota como cancelada (guard).
NFE_EVENTO_NAO_HOMOLOGADO = NFE_VENDA.replace(
    "</infNFe></NFe>",
    "</infNFe><evento><infEvento><tpEvento>110111</tpEvento></infEvento></evento></NFe>",
)


def test_nfe_xml_cstat_101_vira_cancelada_e_conferir():
    nf = parse_nfe(NFE_CANCELADA_CSTAT)
    assert nf.cancelada is True
    rel = processar(NFE_CANCELADA_CSTAT)
    assert rel.get("forcar_conferir") is True
    assert any("cancelad" in m.lower() for m in rel["motivos"])


def test_tpevento_sozinho_sem_cstat_homologado_nao_cancela():
    # so a REQUISICAO do evento (sem cStat 101/151 homologado) NAO marca cancelada (anti falso-positivo)
    nf = parse_nfe(NFE_EVENTO_NAO_HOMOLOGADO)
    assert nf.cancelada is False
    assert processar(NFE_EVENTO_NAO_HOMOLOGADO).get("forcar_conferir") is False


def test_nfe_xml_normal_cstat_100_nao_cancelada():
    # NF-e VENDA com protocolo de AUTORIZACAO (cStat 100) -> NAO e cancelamento
    nfe_autorizada = NFE_VENDA.replace(
        "</infNFe></NFe>",
        "</infNFe><protNFe><infProt><cStat>100</cStat></infProt></protNFe></NFe>",
    )
    nf = parse_nfe(nfe_autorizada)
    assert nf.cancelada is False
    rel = processar(nfe_autorizada)
    assert not any("cancelad" in m.lower() for m in rel["motivos"])


def test_nfe_xml_sem_protocolo_nao_cancelada():
    # fixture base (sem protNFe) continua nao-cancelada
    nf = parse_nfe(NFE_VENDA)
    assert nf.cancelada is False


def test_cancelada_xml_com_namespace_prefixado():
    from engine.dispatch import processar

    # NF-e cancelada com PREFIXO de namespace (nfe:) -> deve detectar cStat 101
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<nfe:nfeProc xmlns:nfe="http://www.portalfiscal.inf.br/nfe">
 <nfe:NFe><nfe:infNFe Id="NFe35250611222333000181550010000000011000000017">
  <nfe:emit><nfe:CNPJ>11222333000181</nfe:CNPJ></nfe:emit>
  <nfe:total><nfe:ICMSTot><nfe:vProd>100.00</nfe:vProd><nfe:vNF>100.00</nfe:vNF></nfe:ICMSTot></nfe:total>
 </nfe:infNFe></nfe:NFe>
 <nfe:protNFe><nfe:infProt><nfe:cStat>101</nfe:cStat></nfe:infProt></nfe:protNFe>
</nfe:nfeProc>'''
    out = processar(xml)
    assert out["forcar_conferir"] is True   # cancelada detectada apesar do prefixo


def test_evento_cancelamento_homologado_110111_mais_135_cancela():
    # evento de cancelamento HOMOLOGADO (tpEvento 110111 + cStat 135 no mesmo bloco) -> cancelada
    xml = NFE_VENDA.replace(
        "</infNFe></NFe>",
        "</infNFe><procEventoNFe><evento><infEvento><tpEvento>110111</tpEvento></infEvento></evento>"
        "<retEvento><infEvento><tpEvento>110111</tpEvento><cStat>135</cStat></infEvento></retEvento>"
        "</procEventoNFe></NFe>",
    )
    nf = parse_nfe(xml)
    assert nf.cancelada is True
    assert processar(xml).get("forcar_conferir") is True


def test_cce_110110_mais_135_nao_cancela():
    # carta-de-correcao homologada (tpEvento 110110 + cStat 135) NAO e cancelamento
    xml = NFE_VENDA.replace(
        "</infNFe></NFe>",
        "</infNFe><procEventoNFe><retEvento><infEvento><tpEvento>110110</tpEvento>"
        "<cStat>135</cStat></infEvento></retEvento></procEventoNFe></NFe>",
    )
    assert parse_nfe(xml).cancelada is False
    assert processar(xml).get("forcar_conferir") is False


def test_cancelada_cstat_homologado_entre_multiplos_protocolos():
    # envelope com varios cStat (ex.: 135 de um evento + 101 do cancelamento homologado):
    # iterar TODOS evita perder o 101 que nao e o 1o (imune a prefixo de namespace tambem)
    xml = NFE_VENDA.replace(
        "</infNFe></NFe>",
        "</infNFe>"
        "<procEventoNFe><retEvento><infEvento><cStat>135</cStat></infEvento></retEvento></procEventoNFe>"
        "<protNFe><infProt><cStat>101</cStat></infProt></protNFe></NFe>",
    )
    nf = parse_nfe(xml)
    assert nf.cancelada is True
    assert processar(xml).get("forcar_conferir") is True
