from engine.export.linha import montar_linha
from engine.export.csv_generico import COLUNAS
from engine.parsers.xml_nfe import parse_nfe
from engine.model import Campo, Confianca, Fonte, NFSeServico
from tests.test_itens_nfe import XML_2_ITENS


def _rel():
    return {"score_documento": 0.95, "banda": "ALTA", "file_key": "k", "motivos": []}


def test_linha_nfe_traz_agregados():
    linha = montar_linha(parse_nfe(XML_2_ITENS), _rel(), "nota.xml")
    assert linha["qtd_itens"] == 2
    assert linha["cfops_distintos"] == "1102, 5102"
    assert linha["tem_desconto_item"] == "Sim"
    assert linha["ncm_predominante"] == "73181500"
    assert "Parafuso M6" in linha["descricao_resumida"]


def test_linha_nfse_deixa_agregados_vazios():
    nf = NFSeServico(emitente_cnpj=Campo(valor="11222333000181", confianca=Confianca(score=1.0, fonte=Fonte.XML)))
    linha = montar_linha(nf, _rel(), "s.xml")
    assert linha["qtd_itens"] is None
    assert linha["tem_desconto_item"] is None


def test_colunas_agregadas_no_csv():
    for col in ("qtd_itens", "cfops_distintos", "tem_desconto_item", "ncm_predominante", "descricao_resumida"):
        assert col in COLUNAS
