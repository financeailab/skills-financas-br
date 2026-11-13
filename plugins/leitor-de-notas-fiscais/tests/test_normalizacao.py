from decimal import Decimal

from engine.normalizacao import normalizar_aliquota, iss_e_retido
from engine.normalizacao import retido_nacional


def test_aliquota_fracao_vira_percentual():
    assert normalizar_aliquota(Decimal("0.05")) == Decimal("5.00")
    assert normalizar_aliquota(Decimal("0.02")) == Decimal("2.00")


def test_aliquota_percentual_inalterada():
    assert normalizar_aliquota(Decimal("5.00")) == Decimal("5.00")
    assert normalizar_aliquota(Decimal("2")) == Decimal("2")
    assert normalizar_aliquota(Decimal("1.00")) == Decimal("1.00")     # borda exata passa inalterada
    assert normalizar_aliquota(Decimal("0.999")) == Decimal("99.900")  # maior fracao multiplicada


def test_aliquota_none():
    assert normalizar_aliquota(None) is None


def test_iss_retido_tokens():
    assert iss_e_retido("1") is True
    assert iss_e_retido("true") is True
    assert iss_e_retido("Sim") is True
    assert iss_e_retido("2") is False
    assert iss_e_retido("false") is False
    assert iss_e_retido("N") is False
    assert iss_e_retido(None) is False
    assert iss_e_retido("S") is True
    assert iss_e_retido("T") is True
    assert iss_e_retido(" 1 ") is True   # whitespace e tolerado (strip)


def test_retido_nacional_tabela():
    assert retido_nacional("2") is True    # Retido pelo Tomador
    assert retido_nacional("3") is True    # Retido pelo Intermediario
    assert retido_nacional("1") is False   # Nao retido
    assert retido_nacional(None) is False
