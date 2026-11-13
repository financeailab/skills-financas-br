from decimal import Decimal
from engine.normalizacao import normalizar_decimal_br as n


def test_formato_br():
    assert n("1.234,56") == Decimal("1234.56")
    assert n("1234,56") == Decimal("1234.56")
    assert n("R$ 1.000,00") == Decimal("1000.00")
    assert n("*24,83") == Decimal("24.83")          # * de rodape (Osasco)
    assert n("1.234.567,89") == Decimal("1234567.89")


def test_formato_us_ponto_decimal():
    assert n("13305.60") == Decimal("13305.60")     # DALOP/FITMAX (fatura)
    assert n("1000.00") == Decimal("1000.00")
    assert n("5.00") == Decimal("5.00")             # aliquota como o prompt emite
    assert n("100") == Decimal("100")


def test_us_com_milhar():
    assert n("1,234.56") == Decimal("1234.56")      # ponto decimal, virgula milhar


def test_sem_numero_vira_none():
    assert n(None) is None
    assert n("") is None
    assert n("ISENTO") is None
    assert n("-") is None
    assert n("R$") is None
