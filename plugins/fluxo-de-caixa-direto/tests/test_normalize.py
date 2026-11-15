# -*- coding: utf-8 -*-
"""normalize.py vendorado: confere que a copia se comporta igual ao hero
(conversor-extrato/conciliacao-bancaria) nos casos que o motor de fluxo de caixa
realmente exercita (valor BR/OFX, data BR/ISO/OFX, parenteses contabil)."""
from decimal import Decimal

import pytest

from normalize import parse_valor, parse_data, norm_doc


def test_parse_valor_br_virgula_decimal():
    assert parse_valor("1.234,56", origem="br") == Decimal("1234.56")


def test_parse_valor_br_negativo_com_sinal():
    assert parse_valor("-150,00", origem="br") == Decimal("-150.00")


def test_parse_valor_br_parenteses_contabil_e_negativo():
    assert parse_valor("(1.234,56)", origem="br") == Decimal("-1234.56")


def test_parse_valor_ofx_ponto_e_sempre_decimal():
    assert parse_valor("1234.56", origem="ofx") == Decimal("1234.56")
    assert parse_valor("-50.00", origem="ofx") == Decimal("-50.00")


def test_parse_valor_vazio_levanta_erro():
    with pytest.raises(ValueError):
        parse_valor("", origem="br")


def test_parse_valor_nao_numerico_levanta_erro():
    with pytest.raises(ValueError):
        parse_valor("abacate", origem="br")


def test_parse_data_br_barra():
    assert str(parse_data("15/03/2026")) == "2026-03-15"


def test_parse_data_iso():
    assert str(parse_data("2026-03-15")) == "2026-03-15"


def test_parse_data_ofx_com_hora_e_timezone():
    assert str(parse_data("20260315120000[-3:GMT]")) == "2026-03-15"


def test_parse_data_vazia_levanta_erro():
    with pytest.raises(ValueError):
        parse_data("")


def test_norm_doc_ultima_sequencia_sem_zeros_a_esquerda():
    assert norm_doc("Doc 000123") == "123"
    assert norm_doc("PIX RECEBIDO") is None
