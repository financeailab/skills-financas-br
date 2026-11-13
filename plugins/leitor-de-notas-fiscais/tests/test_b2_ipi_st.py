from decimal import Decimal

from engine.dispatch import processar
from engine.invariants import invariante_total_nfe
from engine.parsers.xml_nfe import parse_nfe
from tests.fixtures_xml_sinteticas import NFE_MULTI_ITEM_IPI_ST


def test_total_com_ipi_e_st_fecha_e_vira_ALTA():
    rel = processar(NFE_MULTI_ITEM_IPI_ST)  # 300+10+5+2-7+30+20 = 360 = vNF
    assert rel["banda"] == "ALTA", rel["motivos"]


def test_parser_extrai_ipi_e_st():
    nf = parse_nfe(NFE_MULTI_ITEM_IPI_ST)
    assert nf.ipi_total.valor == Decimal("30.00")
    assert nf.icmsst_total.valor == Decimal("20.00")


def test_invariante_inclui_ipi_st():
    z = Decimal("0")
    r = invariante_total_nfe(Decimal("300"), Decimal("10"), Decimal("5"), Decimal("2"),
                             Decimal("7"), Decimal("360"), ipi=Decimal("30"), icmsst=Decimal("20"))
    assert r.ok
