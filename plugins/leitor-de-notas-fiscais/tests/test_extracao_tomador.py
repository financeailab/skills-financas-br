from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.parsers.xml_sp import parse_nfse_sp

NACIONAL = """<?xml version="1.0"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="X">
  <nNFSe>1</nNFSe>
  <prest><CNPJ>11111111000111</CNPJ><enderNac><cMun>3304557</cMun></enderNac></prest>
  <toma><CNPJ>22222222000122</CNPJ><enderNac><cMun>3550308</cMun></enderNac></toma>
  <vServ>100.00</vServ>
</infNFSe></NFSe>"""

ABRASF = """<?xml version="1.0"?><CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><Nfse><InfNfse>
  <Numero>1</Numero>
  <PrestadorServico><IdentificacaoPrestador><Cnpj>11111111000111</Cnpj></IdentificacaoPrestador></PrestadorServico>
  <TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>22222222000122</Cnpj></CpfCnpj></IdentificacaoTomador>
    <Endereco><CodigoMunicipio>3550308</CodigoMunicipio></Endereco></TomadorServico>
</InfNfse></Nfse></CompNfse>"""

SP = """<?xml version="1.0"?><NFe xmlns="http://www.prefeitura.sp.gov.br/nfe">
  <NumeroNFe>1</NumeroNFe><CNPJ>11111111000111</CNPJ>
  <CPFCNPJTomador><CNPJ>22222222000122</CNPJ></CPFCNPJTomador><CidadeTomador>3550308</CidadeTomador>
</NFe>"""


def test_nacional_tomador_path_aware():
    nf = parse_nfse_nacional(NACIONAL)
    assert nf.destinatario_doc.valor == "22222222000122"   # tomador, NAO o prestador
    assert nf.municipio_tomador.valor == "3550308"


def test_abrasf_tomador_path_aware():
    nf = parse_nfse_abrasf(ABRASF)
    assert nf.destinatario_doc.valor == "22222222000122"
    assert nf.municipio_tomador.valor == "3550308"


def test_sp_tomador_path_aware():
    nf = parse_nfse_sp(SP)
    assert nf.destinatario_doc.valor == "22222222000122"
    assert nf.municipio_tomador.valor == "3550308"
