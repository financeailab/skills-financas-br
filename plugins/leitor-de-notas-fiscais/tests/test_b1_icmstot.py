from engine.dispatch import processar
from engine.parsers.xml_nfe import parse_nfe
from tests.fixtures_xml_sinteticas import NFE_MULTI_ITEM_SIMPLES, NFE_ITEM_UNICO


def test_total_produtos_vem_do_icmstot_nao_do_1o_item():
    nf = parse_nfe(NFE_MULTI_ITEM_SIMPLES)
    assert nf.total_produtos.valor == __import__("decimal").Decimal("300.00")  # ICMSTot, nao 100 (item1)


def test_nfe_multi_item_sem_ipi_fecha_e_vira_ALTA():
    rel = processar(NFE_MULTI_ITEM_SIMPLES)
    assert rel["banda"] == "ALTA", rel["motivos"]


def test_nfe_item_unico_continua_ALTA():  # regressao
    assert processar(NFE_ITEM_UNICO)["banda"] == "ALTA"
