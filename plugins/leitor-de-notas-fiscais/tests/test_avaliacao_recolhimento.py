from decimal import Decimal

from engine.avaliacao import avaliar_nfse
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v, fonte=Fonte.XML, score=1.0):
    return Campo(valor=v, confianca=Confianca(score=score, fonte=fonte))


def _nfse(tipo):
    return NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("10000.00")),
        iss_base=_c(Decimal("10000.00")),
        iss_aliquota=_c(Decimal("5.00")),
        iss_valor=_c(Decimal("500.00")),
        iss_retido=_c("true" if tipo != "nao_retido" else "false"),
        iss_tipo_retencao=_c(tipo),
    )


def test_flag_recolhimento_verdadeira_para_retido_tomador():
    r = avaliar_nfse(_nfse("retido_tomador"))
    assert r["iss_obrigacao_recolhimento_tomador"] is True
    assert any("recolher" in m.lower() for m in r["motivos"])


def test_flag_falsa_para_intermediario_e_nao_retido():
    assert avaliar_nfse(_nfse("retido_intermediario"))["iss_obrigacao_recolhimento_tomador"] is False
    assert avaliar_nfse(_nfse("nao_retido"))["iss_obrigacao_recolhimento_tomador"] is False
