from engine.parsers.xml_nfe import parse_nfe
from tests.test_itens_nfe import XML_2_ITENS


def test_parser_nfe_popula_agregados():
    nf = parse_nfe(XML_2_ITENS)
    assert nf.qtd_itens.valor == 2
    assert nf.cfops_distintos.valor == "1102, 5102"
    assert nf.tem_desconto_item.valor is True
    assert nf.ncm_predominante.valor == "73181500"
    assert "Parafuso M6" in nf.descricao_resumida.valor
    # totais existentes seguem intactos
    assert nf.total_nota.valor is not None
