from engine.dispatch import processar
from engine.parsers.xml_nacional import parse_nfse_nacional
from tests.fixtures_xml_sinteticas import NFSE_NACIONAL_IMUNE, NFSE_NACIONAL_TRIBUTAVEL_SEM_ISS


def test_imune_nao_penaliza_e_vira_ALTA():
    nf = parse_nfse_nacional(NFSE_NACIONAL_IMUNE)
    assert nf.iss_nao_exigivel is True
    assert processar(NFSE_NACIONAL_IMUNE)["banda"] == "ALTA"


def test_tributavel_sem_iss_continua_BAIXA():  # guarda: tribISSQN=1 sem ISS = suspeito de verdade
    nf = parse_nfse_nacional(NFSE_NACIONAL_TRIBUTAVEL_SEM_ISS)
    assert nf.iss_nao_exigivel is False
    assert processar(NFSE_NACIONAL_TRIBUTAVEL_SEM_ISS)["banda"] == "BAIXA"
