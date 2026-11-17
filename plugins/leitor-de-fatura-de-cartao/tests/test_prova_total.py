# -*- coding: utf-8 -*-
"""Testes de prova_total (SPEC-00 §7): completude Σlancamentos+encargos==total_fatura."""
from datetime import date
from decimal import Decimal

from modelo import BAIXA_CONFIANCA, LAYOUT_DESCONHECIDO, OK, TOTAL_NAO_FECHA, Encargo, FaturaParsed, Lancamento
from prova_total import validar


def _fatura_fechada():
    return FaturaParsed(
        emissor="itau",
        vencimento=date(2026, 2, 10),
        portadores=["FULANO DE TAL"],
        lancamentos=[
            Lancamento(date(2026, 1, 5), "Loja A", Decimal("100.00"), portador="FULANO DE TAL"),
            Lancamento(date(2026, 1, 8), "Loja B", Decimal("50.00"), portador="FULANO DE TAL"),
        ],
        encargos=[Encargo("IOF", Decimal("10.00"))],
        total_fatura=Decimal("160.00"),
    )


def test_total_fecha_ok():
    fatura = _fatura_fechada()
    resultado = validar(fatura)
    assert resultado is fatura  # muta e devolve o MESMO objeto
    assert resultado.veredicto == OK
    assert resultado.aviso == ""


def test_lancamento_suprimido_quebra_e_reprova():
    """Remove um lancamento mas mantem o total_fatura ORIGINAL (como se um
    lancamento tivesse sumido do parse) -> deve reprovar com TOTAL NAO FECHA."""
    fatura = _fatura_fechada()
    del fatura.lancamentos[0]  # tira "Loja A" (100.00); total_fatura continua 160.00

    resultado = validar(fatura)

    assert resultado.veredicto == TOTAL_NAO_FECHA
    assert "nao fecha" in resultado.aviso
    assert resultado.aviso != ""


def test_sem_total_impresso_nao_aprova_fica_baixa_confianca():
    fatura = FaturaParsed(
        emissor="generico",
        lancamentos=[Lancamento(date(2026, 1, 6), "Restaurante X", Decimal("89.90"))],
        total_fatura=None,
    )

    resultado = validar(fatura)

    assert resultado.veredicto == BAIXA_CONFIANCA
    assert resultado.aviso != ""


def test_sem_lancamento_nem_encargo_vira_layout_desconhecido():
    fatura = FaturaParsed(emissor="generico", lancamentos=[], encargos=[], total_fatura=None)

    resultado = validar(fatura)

    assert resultado.veredicto == LAYOUT_DESCONHECIDO


def test_layout_desconhecido_travado_nao_e_sobrescrito():
    fatura = FaturaParsed(emissor="itau", veredicto=LAYOUT_DESCONHECIDO, aviso="cabecalho ausente")
    fatura.total_fatura = Decimal("100.00")  # mesmo com total presente, nao reavalia

    resultado = validar(fatura)

    assert resultado.veredicto == LAYOUT_DESCONHECIDO
    assert resultado.aviso == "cabecalho ausente"


def test_encargos_entram_na_soma():
    fatura = FaturaParsed(
        emissor="itau",
        lancamentos=[Lancamento(date(2026, 1, 5), "Loja A", Decimal("100.00"))],
        encargos=[Encargo("IOF", Decimal("15.80")), Encargo("Anuidade", Decimal("25.00"))],
        total_fatura=Decimal("140.80"),
    )

    resultado = validar(fatura)

    assert resultado.veredicto == OK
