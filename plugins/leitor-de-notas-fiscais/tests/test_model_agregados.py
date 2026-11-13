from engine.model import Campo, Confianca, Fonte, NFeProduto


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_nfe_carrega_agregados_de_itens():
    nf = NFeProduto(
        qtd_itens=_c(3),
        cfops_distintos=_c("1102, 5102"),
        tem_desconto_item=_c(True),
        ncm_predominante=_c("84713012"),
        descricao_resumida=_c("Parafuso; Porca; Arruela"),
    )
    assert nf.qtd_itens.valor == 3
    assert nf.cfops_distintos.valor == "1102, 5102"
    assert nf.tem_desconto_item.valor is True
    assert nf.ncm_predominante.valor == "84713012"
    assert nf.descricao_resumida.valor == "Parafuso; Porca; Arruela"


def test_agregados_opcionais():
    nf = NFeProduto()
    assert nf.qtd_itens is None
    assert nf.cfops_distintos is None
    assert nf.tem_desconto_item is None
