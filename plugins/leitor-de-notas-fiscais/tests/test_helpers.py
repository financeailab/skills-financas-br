from decimal import Decimal

from engine.parsers._helpers import dec


def test_dec_converte_valido():
    assert dec("1234.56") == Decimal("1234.56")


def test_dec_none_vira_none():
    assert dec(None) is None


def test_dec_malformado_vira_none():
    assert dec("abc") is None
    assert dec("") is None
