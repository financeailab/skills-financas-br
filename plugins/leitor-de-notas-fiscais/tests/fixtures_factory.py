"""Gerador de NFS-e de teste (nacional/ABRASF/SP) parametrizado, p/ validacao em lote (>=20/ponto)."""
from __future__ import annotations


def nfse_nacional(*, inc, dest, tipo_ret="1", cod="0101", prest_cnpj="11111111000111",
                  serv="1000.00", aliq="5.00", iss="50.00") -> str:
    return f"""<?xml version="1.0"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="X">
  <nNFSe>1</nNFSe><cTribNac>{cod}</cTribNac>
  <prest><CNPJ>{prest_cnpj}</CNPJ></prest>
  <toma><CNPJ>{dest}</CNPJ></toma>
  <vServ>{serv}</vServ><vBC>{serv}</vBC><pAliqAplic>{aliq}</pAliqAplic><vISSQN>{iss}</vISSQN>
  <tpRetISSQN>{tipo_ret}</tpRetISSQN><cLocIncid>{inc}</cLocIncid>
</infNFSe></NFSe>"""


def nfse_abrasf(*, dest, mun_tom, retido="2", cod="0101", prest_cnpj="11111111000111",
                serv="1000.00", iss="50.00") -> str:
    # ABRASF IssRetido: 1=SIM, 2=NAO
    iss_ret = "1" if retido == "1" else "2"
    return f"""<?xml version="1.0"?><CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><Nfse><InfNfse>
  <Numero>1</Numero><ItemListaServico>{cod}</ItemListaServico>
  <PrestadorServico><IdentificacaoPrestador><Cnpj>{prest_cnpj}</Cnpj></IdentificacaoPrestador></PrestadorServico>
  <TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>{dest}</Cnpj></CpfCnpj></IdentificacaoTomador>
    <Endereco><CodigoMunicipio>{mun_tom}</CodigoMunicipio></Endereco></TomadorServico>
  <ValorServicos>{serv}</ValorServicos><ValorIss>{iss}</ValorIss><IssRetido>{iss_ret}</IssRetido>
</InfNfse></Nfse></CompNfse>"""


def nfse_sp(*, dest, mun_tom, retido="true", cod="0101", prest_cnpj="11111111000111",
            serv="1000.00", iss="50.00") -> str:
    return f"""<?xml version="1.0"?><NFe xmlns="http://www.prefeitura.sp.gov.br/nfe">
  <NumeroNFe>1</NumeroNFe><CodigoServico>{cod}</CodigoServico><CNPJ>{prest_cnpj}</CNPJ>
  <CPFCNPJTomador><CNPJ>{dest}</CNPJ></CPFCNPJTomador><CidadeTomador>{mun_tom}</CidadeTomador>
  <ValorServicos>{serv}</ValorServicos><ValorISS>{iss}</ValorISS><ISSRetido>{retido}</ISSRetido>
</NFe>"""


# Listas p/ varrer >=20 combos por ponto.
NOSSO_CNPJ = "22222222000122"
NOSSO_MUN = "3550308"
OUTRO_MUN = "3304557"
OUTRO_CNPJ = "99999999000199"
COD_OBRIGA = ("0702", "1102", "1705", "0710")      # LC116 §2
COD_NAO_OBRIGA = ("0101", "0105", "0205", "0301")  # nao §2
