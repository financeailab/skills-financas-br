from engine.dispatch import processar
from tests.fixtures_xml_sinteticas import NFE_SEM_ICMSTOT


def test_nfe_sem_icmstot_vai_pra_BAIXA():
    rel = processar(NFE_SEM_ICMSTOT)
    assert rel["banda"] == "BAIXA", rel
    assert any("total" in m.lower() for m in rel["motivos"])
