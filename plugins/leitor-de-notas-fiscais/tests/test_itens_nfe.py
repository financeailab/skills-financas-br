import xml.etree.ElementTree as ET

from engine.parsers.itens_nfe import agregar_itens

XML_2_ITENS = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe>
  <det nItem="1"><prod><cProd>A</cProd><xProd>Parafuso M6</xProd>
    <NCM>73181500</NCM><CFOP>1102</CFOP><vProd>100.00</vProd><vDesc>10.00</vDesc></prod></det>
  <det nItem="2"><prod><cProd>B</cProd><xProd>Porca M6</xProd>
    <NCM>73181500</NCM><CFOP>5102</CFOP><vProd>50.00</vProd></prod></det>
  <total><ICMSTot><vNF>140.00</vNF></ICMSTot></total>
</infNFe></NFe>"""

XML_SEM_ITENS = """<?xml version="1.0"?><NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe>
  <total><ICMSTot><vNF>0.00</vNF></ICMSTot></total></infNFe></NFe>"""


def _root(s):
    return ET.fromstring(s)


def test_agrega_dois_itens():
    a = agregar_itens(_root(XML_2_ITENS))
    assert a["qtd_itens"] == 2
    assert a["cfops_distintos"] == "1102, 5102"          # unicos, ordenados, ", "-joined
    assert a["tem_desconto_item"] is True                 # item 1 tem vDesc 10
    assert a["ncm_predominante"] == "73181500"            # repete nos 2 itens
    assert "Parafuso M6" in a["descricao_resumida"]
    assert "Porca M6" in a["descricao_resumida"]


def test_cfop_unico_e_sem_desconto():
    xml = XML_2_ITENS.replace("<CFOP>5102</CFOP>", "<CFOP>1102</CFOP>").replace("<vDesc>10.00</vDesc>", "")
    a = agregar_itens(_root(xml))
    assert a["cfops_distintos"] == "1102"                 # colapsa duplicados
    assert a["tem_desconto_item"] is False


def test_descricao_resumida_trunca_em_80():
    a = agregar_itens(_root(XML_2_ITENS.replace("Parafuso M6", "X" * 120)))
    assert len(a["descricao_resumida"]) <= 80
    assert a["descricao_resumida"].endswith("...")


def test_sem_itens_degrada_gracioso():
    a = agregar_itens(_root(XML_SEM_ITENS))
    assert a["qtd_itens"] == 0
    assert a["cfops_distintos"] is None
    assert a["tem_desconto_item"] is False
    assert a["ncm_predominante"] is None
    assert a["descricao_resumida"] is None
