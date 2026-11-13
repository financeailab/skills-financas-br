from decimal import Decimal

from engine.parsers.xml_nacional import parse_nfse_nacional

XML_RETIDO_TOMADOR = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
  <infNFSe Id="NFS50550308000000000000000000000000000000000123">
    <nNFSe>123</nNFSe>
    <emit><CNPJ>11222333000181</CNPJ><xNome>Fornecedor X</xNome></emit>
    <valores>
      <vServ>10000.00</vServ><vBC>10000.00</vBC><pAliqAplic>5.00</pAliqAplic>
      <vISSQN>500.00</vISSQN><tpRetISSQN>2</tpRetISSQN>
      <cLocIncid>3550308</cLocIncid>
      <vRetIRRF>150.00</vRetIRRF><vRetCSLL>465.00</vRetCSLL>
      <vTotTribFed>1115.00</vTotTribFed>
      <vLiq>8885.00</vLiq>
    </valores>
    <cTribNac>010501</cTribNac><xDescServ>Publicidade</xDescServ>
    <dhEmi>2026-03-15T10:00:00-03:00</dhEmi>
  </infNFSe>
</NFSe>"""


def test_nacional_extrai_tipo_retencao_tomador():
    nf = parse_nfse_nacional(XML_RETIDO_TOMADOR)
    assert nf.iss_tipo_retencao.valor == "retido_tomador"
    assert nf.iss_retido.valor == "true"  # compat mantida


def test_nacional_extrai_municipio_incidencia_e_total_federal():
    nf = parse_nfse_nacional(XML_RETIDO_TOMADOR)
    assert nf.iss_municipio_incidencia.valor == "3550308"
    assert nf.ret_federal_total.valor == Decimal("1115.00")
