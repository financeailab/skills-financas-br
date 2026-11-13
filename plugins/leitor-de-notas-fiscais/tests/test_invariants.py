from decimal import Decimal

from engine.invariants import (
    invariante_iss,
    invariante_liquido_nfse,
    invariante_total_nfe,
    Resultado,
)


def test_iss_fecha():
    r = invariante_iss(base=Decimal("1000.00"), aliquota=Decimal("5.00"), valor=Decimal("50.00"))
    assert r.ok is True


def test_iss_nao_fecha():
    r = invariante_iss(base=Decimal("1000.00"), aliquota=Decimal("5.00"), valor=Decimal("49.00"))
    assert r.ok is False
    assert "ISS" in r.motivo


def test_iss_tolerancia_centavos():
    # 1000 * 4.99% = 49.90; diff = 1 centavo, dentro da tolerancia de 2 centavos
    r = invariante_iss(base=Decimal("1000.00"), aliquota=Decimal("4.99"), valor=Decimal("49.91"))
    assert r.ok is True


def test_liquido_nfse_fecha():
    r = invariante_liquido_nfse(
        servicos=Decimal("1000.00"), deducoes=Decimal("0.00"), retencoes=Decimal("50.00"),
        liquido=Decimal("950.00"),
    )
    assert r.ok is True


def test_total_nfe_fecha():
    r = invariante_total_nfe(
        produtos=Decimal("200.00"), frete=Decimal("0"), seguro=Decimal("0"),
        outras=Decimal("0"), desconto=Decimal("0"), total=Decimal("200.00"),
    )
    assert r.ok is True


def test_liquido_nfse_nao_fecha():
    r = invariante_liquido_nfse(
        servicos=Decimal("1000.00"), deducoes=Decimal("0.00"), retencoes=Decimal("50.00"),
        liquido=Decimal("900.00"),
    )
    assert r.ok is False
    assert "Liquido" in r.motivo


def test_total_nfe_nao_fecha():
    r = invariante_total_nfe(
        produtos=Decimal("200.00"), frete=Decimal("0"), seguro=Decimal("0"),
        outras=Decimal("0"), desconto=Decimal("0"), total=Decimal("180.00"),
    )
    assert r.ok is False
    assert "Total" in r.motivo
