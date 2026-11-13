from engine.router import classificar, Familia
from engine.dispatch import parsear

RPS = """<?xml version="1.0"?><Rps xmlns="http://www.abrasf.org.br/nfse.xsd"><InfRps>
  <IdentificacaoRps><Numero>55</Numero></IdentificacaoRps>
  <Servico><Valores><ValorServicos>800.00</ValorServicos><ValorIss>40.00</ValorIss></Valores>
    <Aliquota>5.00</Aliquota></Servico>
  <Prestador><Cnpj>11222333000181</Cnpj></Prestador>
</InfRps></Rps>"""


def test_rps_classifica_como_abrasf():
    assert classificar(RPS) == Familia.NFSE_ABRASF


def test_rps_parseia_para_nfse():
    fam, modelo = parsear(RPS)
    assert fam == Familia.NFSE_ABRASF
    assert modelo is not None
    assert modelo.valor_servicos.valor is not None
