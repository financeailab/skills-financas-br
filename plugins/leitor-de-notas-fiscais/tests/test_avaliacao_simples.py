from decimal import Decimal
from engine.avaliacao import avaliar_nfse
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def test_simples_sem_iss_nao_penaliza_e_explica():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("2500.00")),
                     valor_liquido=_c(Decimal("2500.00")), iss_aliquota=_c(Decimal("5.00")),
                     simples_nacional=True)
    r = avaliar_nfse(nf)
    assert any("simples nacional" in m.lower() for m in r["motivos"])
    assert r["banda"] == "ALTA"          # CNPJ valido + liquido fecha -> auto-aprova


def test_nao_simples_sem_iss_continua_conferir():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("2500.00")))
    r = avaliar_nfse(nf)
    assert r["banda"] != "ALTA"          # ISS ausente sem ser Simples = suspeito
