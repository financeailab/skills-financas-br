from engine.model import Campo, Confianca, Fonte, NFSeServico, NFeProduto


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def test_nfse_tem_vencimento_e_simples():
    nf = NFSeServico(vencimento=_c("2026-05-30"), simples_nacional=True)
    assert nf.vencimento.valor == "2026-05-30"
    assert nf.simples_nacional is True


def test_nfe_tem_vencimento():
    assert NFeProduto(vencimento=_c("2026-04-02")).vencimento.valor == "2026-04-02"


def test_defaults():
    assert NFSeServico().vencimento is None
    assert NFSeServico().simples_nacional is False
    assert NFeProduto().vencimento is None
