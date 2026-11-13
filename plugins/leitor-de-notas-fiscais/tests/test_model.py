import pytest
from decimal import Decimal
from pydantic import ValidationError

from engine.model import Campo, Confianca, Fonte, NFSeServico, NFeProduto


def test_campo_carrega_valor_e_confianca():
    c = Campo(valor="1000.00", confianca=Confianca(score=1.0, fonte=Fonte.XML))
    assert c.valor == "1000.00"
    assert c.confianca.score == 1.0
    assert c.confianca.fonte == Fonte.XML
    assert c.confianca.motivo is None


def test_score_fora_de_0_1_falha():
    with pytest.raises(ValidationError):
        Confianca(score=1.5, fonte=Fonte.XML)


def _campo(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_nfse_servico_minima():
    nf = NFSeServico(
        chave_acesso=_campo("3" * 50),
        emitente_cnpj=_campo("11222333000181"),
        valor_servicos=_campo(Decimal("1000.00")),
        iss_base=_campo(Decimal("1000.00")),
        iss_aliquota=_campo(Decimal("5.00")),
        iss_valor=_campo(Decimal("50.00")),
        valor_liquido=_campo(Decimal("950.00")),
    )
    assert nf.modelo == "NFSe"
    assert nf.valor_servicos.valor == Decimal("1000.00")
    # transicao-ready: grupos IBS/CBS existem e sao opcionais (None por padrao)
    assert nf.ibs_valor is None
    assert nf.cbs_valor is None


def test_nfe_produto_minima():
    nf = NFeProduto(
        chave_acesso=_campo("9" * 44),
        emitente_cnpj=_campo("11222333000181"),
        total_produtos=_campo(Decimal("200.00")),
        total_nota=_campo(Decimal("200.00")),
    )
    assert nf.modelo == "NFe"
    assert nf.total_nota.valor == Decimal("200.00")
