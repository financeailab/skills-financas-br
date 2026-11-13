from engine.fiscal.lc116 import subitem_lc116, obriga_retencao_tomador, SUBITENS_RETENCAO_OBRIGATORIA


def test_normaliza_subitem_de_varios_formatos():
    assert subitem_lc116("0702") == "7.02"
    assert subitem_lc116("07.02") == "7.02"
    assert subitem_lc116("7.02") == "7.02"
    assert subitem_lc116("1102") == "11.02"


def test_subitem_irreconhecivel_vira_none():
    assert subitem_lc116(None) is None
    assert subitem_lc116("x") is None


def test_obriga_retencao_para_subitens_do_paragrafo_2():
    assert obriga_retencao_tomador("0702") is True   # construcao civil
    assert obriga_retencao_tomador("1102") is True   # vigilancia
    assert obriga_retencao_tomador("1705") is True   # cessao de mao de obra
    assert obriga_retencao_tomador("0101") is False  # analise de sistemas (nao obriga)
    assert obriga_retencao_tomador(None) is False


def test_lista_paragrafo_2_tem_os_subitens_chave():
    for s in ("7.02", "11.02", "17.05", "7.10"):
        assert s in SUBITENS_RETENCAO_OBRIGATORIA


def test_codigo_nacional_de_6_digitos_usa_item_e_subitem():
    # cTribNac = item + subitem + desdobro: so os 4 primeiros mapeiam a LC116 (o teste antigo e anterior ao formato nacional)
    assert subitem_lc116("170510") == "17.05"
    assert subitem_lc116("070201") == "7.02"
    assert obriga_retencao_tomador("070201") is True


def test_outros_tamanhos_nao_adivinham():
    assert subitem_lc116("17051") is None     # 5 digitos
    assert subitem_lc116("1705101") is None   # 7 ou mais
    assert subitem_lc116("17051010") is None


def test_nfse_nacional_070201_nao_retida_dispara_o_alerta_de_retencao():
    """Achado 3 do Gate 2: o alerta de retencao obrigatoria nunca disparava na NFS-e nacional (cTribNac de 6 digitos)."""
    from engine.batch import processar_lote
    from engine.model import TomadorReferencia
    xml = (
        '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS' + "5" * 50 + '"><nNFSe>1</nNFSe>'
        "<cLocIncid>3550308</cLocIncid><emit><CNPJ>11222333000181</CNPJ><xNome>P</xNome></emit>"
        "<valores><vISSQN>50.00</vISSQN><vBC>1000.00</vBC><pAliqAplic>5.00</pAliqAplic><vLiq>1000.00</vLiq></valores>"
        "<DPS><infDPS><toma><CNPJ>11444777000161</CNPJ></toma><serv><cServ><cTribNac>070201</cTribNac>"
        "<xDescServ>x</xDescServ></cServ></serv><valores><vServPrest><vServ>1000.00</vServ></vServPrest>"
        "<trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun></trib></valores></infDPS></DPS>"
        "</infNFSe></NFSe>"
    )
    ref = TomadorReferencia(cnpj="11444777000161", municipio_ibge="3550308")
    ln = processar_lote([("n.xml", xml)], tomador_ref=ref)["linhas"][0]
    assert ln["alerta_retencao"] == "Sim" and ln["status"] == "conferir"
