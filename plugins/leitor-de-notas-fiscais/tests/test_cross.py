from decimal import Decimal

from engine.cross import cruzar_nfse
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _x(v, fonte=Fonte.XML, score=1.0):
    return Campo(valor=v, confianca=Confianca(score=score, fonte=fonte))


def _nf(servicos, iss):
    return NFSeServico(
        emitente_cnpj=_x("11222333000181"),
        valor_servicos=_x(Decimal(servicos)), iss_valor=_x(Decimal(iss)),
        valor_liquido=_x(Decimal("950.00")),
    )


def test_cruzar_convergente():
    r = cruzar_nfse(_nf("1000.00", "50.00"), _nf("1000.00", "50.00"))
    assert r["ok"] is True and r["divergencias"] == []


def test_cruzar_divergente():
    r = cruzar_nfse(_nf("1000.00", "50.00"), _nf("1000.00", "0.00"))
    assert r["ok"] is False
    assert any(d["campo"] == "iss_valor" for d in r["divergencias"])
    assert any("divergem" in m for m in r["motivos"])
