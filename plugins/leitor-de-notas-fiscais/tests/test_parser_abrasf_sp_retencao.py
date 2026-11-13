from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.parsers.xml_sp import parse_nfse_sp

XML_ABRASF = """<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse><InfNfse><Numero>77</Numero>
    <ValorServicos>1000.00</ValorServicos><ValorIss>50.00</ValorIss>
    <Aliquota>5.00</Aliquota><IssRetido>1</IssRetido>
    <PrestadorServico><IdentificacaoPrestador><Cnpj>11222333000181</Cnpj></IdentificacaoPrestador>
      <RazaoSocial>Fornecedor Y</RazaoSocial></PrestadorServico>
  </InfNfse></Nfse>
</CompNfse>"""

XML_SP = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.prefeitura.sp.gov.br/nfe">
  <NumeroNFe>88</NumeroNFe><ValorServicos>2000.00</ValorServicos>
  <AliquotaServicos>5.00</AliquotaServicos><ValorISS>100.00</ValorISS>
  <ISSRetido>false</ISSRetido>
  <CNPJ>11222333000181</CNPJ><RazaoSocialPrestador>Fornecedor Z</RazaoSocialPrestador>
</NFe>"""


def test_abrasf_retido_vira_retido_tomador():
    nf = parse_nfse_abrasf(XML_ABRASF)
    assert nf.iss_tipo_retencao.valor == "retido_tomador"


def test_sp_nao_retido_vira_nao_retido():
    nf = parse_nfse_sp(XML_SP)
    assert nf.iss_tipo_retencao.valor == "nao_retido"
