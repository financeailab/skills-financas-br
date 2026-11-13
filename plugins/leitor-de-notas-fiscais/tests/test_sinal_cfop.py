from engine.sinais import sinal_cfop_direcao


def test_misto_direcao_dispara():
    m = sinal_cfop_direcao("1102, 5102")  # entrada (1) + saida (5)
    assert m is not None
    assert "direções diferentes" in m


def test_so_saida_nao_dispara():
    assert sinal_cfop_direcao("5101, 6101") is None  # ambos saida (5/6)


def test_so_entrada_nao_dispara():
    assert sinal_cfop_direcao("1102, 2102") is None  # ambos entrada (1/2)


def test_cfop_unico_nao_dispara():
    assert sinal_cfop_direcao("5101") is None


def test_vazio_ou_none_nao_dispara():
    assert sinal_cfop_direcao(None) is None
    assert sinal_cfop_direcao("") is None


from engine.avaliacao import avaliar_nfe
from engine.parsers.xml_nfe import parse_nfe

_HEAD = ('<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe900">'
         '<ide><nNF>900</nNF><serie>1</serie><dhEmi>2026-03-10T08:00:00-03:00</dhEmi></ide>'
         '<emit><CNPJ>11222333000181</CNPJ><xNome>FORNECEDOR LTDA</xNome></emit>'
         '<total><ICMSTot><vProd>300.00</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg>'
         '<vOutro>0.00</vOutro><vDesc>0.00</vDesc><vNF>300.00</vNF></ICMSTot></total>')


def _xml(cfop_a: str, cfop_b: str) -> str:
    return (_HEAD +
            f'<det nItem="1"><prod><cProd>A</cProd><xProd>Item A</xProd>'
            f'<NCM>11111111</NCM><CFOP>{cfop_a}</CFOP><vProd>100.00</vProd></prod></det>'
            f'<det nItem="2"><prod><cProd>B</cProd><xProd>Item B</xProd>'
            f'<NCM>11111111</NCM><CFOP>{cfop_b}</CFOP><vProd>200.00</vProd></prod></det>'
            '</infNFe></NFe>')


XML_MISTO = _xml("1102", "5102")          # entrada + saida -> sinal
XML_MESMA_DIRECAO = _xml("5101", "6101")  # ambos saida -> sem sinal


def test_avaliar_nfe_misto_seta_forcar_conferir_sem_mexer_na_banda():
    rel = avaliar_nfe(parse_nfe(XML_MISTO))
    assert rel["forcar_conferir"] is True
    assert any("direções diferentes" in m for m in rel["motivos"])
    assert rel["banda"] == "ALTA"          # financeiro intacto (total fecha, CNPJ ok)


def test_avaliar_nfe_mesma_direcao_nao_sinaliza():
    rel = avaliar_nfe(parse_nfe(XML_MESMA_DIRECAO))
    assert not rel.get("forcar_conferir")
    assert not any("direções diferentes" in m for m in rel["motivos"])
    assert rel["banda"] == "ALTA"          # mesma banda do caso misto -> sinal nao contamina score


from engine.export.linha import montar_linha


def test_carga_cfop_misto_vira_conferir_com_motivo():
    nf = parse_nfe(XML_MISTO)
    linha = montar_linha(nf, avaliar_nfe(nf), "nfe_mista.xml")
    assert linha["cfops_distintos"] == "1102, 5102"
    assert linha["status"] == "conferir"
    assert "direções diferentes" in linha["motivos"]


def test_carga_cfop_mesma_direcao_segue_auto_aprovada():
    nf = parse_nfe(XML_MESMA_DIRECAO)
    linha = montar_linha(nf, avaliar_nfe(nf), "nfe_saidas.xml")
    assert linha["cfops_distintos"] == "5101, 6101"
    assert linha["status"] == "auto-aprovada"
    assert "direções diferentes" not in linha["motivos"]
