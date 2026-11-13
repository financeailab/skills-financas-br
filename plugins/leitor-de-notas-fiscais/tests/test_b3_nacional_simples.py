from engine.dispatch import processar
from engine.parsers.xml_nacional import parse_nfse_nacional
from tests.fixtures_xml_sinteticas import NFSE_NACIONAL_SIMPLES, NFSE_NACIONAL_NAO_OPTANTE


def test_nacional_simples_marca_flag_e_vira_ALTA():
    nf = parse_nfse_nacional(NFSE_NACIONAL_SIMPLES)
    assert nf.simples_nacional is True
    assert processar(NFSE_NACIONAL_SIMPLES)["banda"] == "ALTA"


def test_nacional_nao_optante_nao_marca_simples():  # guarda
    nf = parse_nfse_nacional(NFSE_NACIONAL_NAO_OPTANTE)
    assert nf.simples_nacional is False
