from decimal import Decimal

from engine.avaliacao import avaliar_nfse
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def test_simples_com_iss_zero_e_aliquota_nao_falha():
    # Guarulhos: base 73500 x 2,78% mas ISS oficial = 0 (DAS). Nao pode acusar erro.
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("73500.00")),
                     valor_liquido=_c(Decimal("73500.00")), iss_base=_c(Decimal("73500.00")),
                     iss_aliquota=_c(Decimal("2.78")), iss_valor=_c(Decimal("0.00")),
                     simples_nacional=True)
    r = avaliar_nfse(nf)
    assert r["banda"] == "ALTA"                                  # auto-aprova
    assert not any("iss nao fecha" in m.lower() for m in r["motivos"])   # sem falso-erro
    assert any("simples" in m.lower() for m in r["motivos"])


def test_nao_simples_com_iss_errado_continua_falhando():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("1000.00")),
                     iss_base=_c(Decimal("1000.00")), iss_aliquota=_c(Decimal("5.00")),
                     iss_valor=_c(Decimal("0.00")))   # fora do Simples: 50 != 0 = erro real
    r = avaliar_nfse(nf)
    assert r["banda"] != "ALTA"
    assert any("iss nao fecha" in m.lower() for m in r["motivos"])
