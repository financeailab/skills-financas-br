# -*- coding: utf-8 -*-
"""Ingestao multi-formato do LADO BANCO (antifragil). Nucleo tabular: o time de
tesouraria manda extrato em QUALQUER formato; o motor extrai a lista canonica de
transacoes (mesma do OFX) ou degrada com status claro, sem nunca quebrar.

Shapes reais cobertos (anonimizados aqui): Santander (valor com sinal, ponto),
Bradesco (CREDITO/DEBITO separados + data em branco = repete + SALDO ANTERIOR),
ABC (valor com sinal + Operacao), Caixa (serial Excel + valor SEM sinal -> sinal pelo
delta de saldo), header com lixo em cima (Itau/MercadoPago).

Rodar:  python tests/test_ingest_extrato.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
sys.path.insert(0, ENGINE)

from ingest_extrato import ingest_tabular_rows, excel_serial_to_date   # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _by_date_val(txns):
    return sorted((t["data"], t["valor"]) for t in txns)


@caso("tabular Santander: valor com sinal e ponto decimal, header na linha 2")
def _():
    rows = [
        ["AGENCIA", "0114", "CONTA", "130069645"],
        ["", "", "", "", ""],
        ["Data", "Histórico", "Documento", "Valor (R$)", "Saldo (R$)"],
        ["30/04/2026", "RESGATE APLICACAO TESTE", "", "2815.7", "0.0"],
        ["30/04/2026", "PIX ENVIADO TESTE", "", "-218904.35", "-2815.7"],
    ]
    r = ingest_tabular_rows(rows)
    assert r["status"] == "OK", r
    assert len(r["transacoes"]) == 2, r["transacoes"]
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 4, 30), Decimal("-218904.35")), (date(2026, 4, 30), Decimal("2815.70"))]


@caso("tabular Bradesco: CREDITO/DEBITO separados + data em branco repete + SALDO ANTERIOR skip")
def _():
    rows = [
        ["", "Agência:3114  Conta:706707-0"],
        ["", "DEMONSTRATIVO MENSAL - CONTA CORRENTE"],
        [],
        ["DATA", "HISTÓRICO", "DOCTO", "CRÉDITO", "DÉBITO", "SALDO"],
        ["31/12/25", "SALDO ANTERIOR", "", "", "", "1,00"],
        ["02/01/26", "CREDITO CARTAO ADQUIRENTE", "353801", "1.842,30", "", ""],
        ["", "CREDITO DEBITO ADQUIRENTE", "353801", "1.138,20", "", ""],
        ["05/01/26", "PAGTO FORNEC", "999", "", "850,00", ""],
    ]
    r = ingest_tabular_rows(rows)
    assert len(r["transacoes"]) == 3, r["transacoes"]
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 1, 2), Decimal("1138.20")),
        (date(2026, 1, 2), Decimal("1842.30")),
        (date(2026, 1, 5), Decimal("-850.00")),
    ]
    # data em branco herdou 02/01; SALDO ANTERIOR nao virou transacao
    assert all(t["data"] != date(2025, 12, 31) for t in r["transacoes"]), r["transacoes"]


@caso("tabular ABC: valor ja com sinal (coluna Operacao ignorada), SALDO ANTERIOR skip")
def _():
    rows = [
        ["Data", "Qtde. registros", "Histórico", "Operação", "Valor (R$)", "Saldo diário (R$)"],
        ["02/01/2026", "-", "SALDO ANTERIOR", "-", "-", "0,00"],
        ["02/01/2026", "1", "AMORTIZACAO CONTRATO", "Débito (-)", "-6.219,34", "-"],
        ["02/01/2026", "1", "RESG.APLICACAO", "Crédito (+)", "6.219,34", "0,00"],
    ]
    r = ingest_tabular_rows(rows)
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 1, 2), Decimal("-6219.34")), (date(2026, 1, 2), Decimal("6219.34"))], r["transacoes"]


@caso("tabular Caixa: valor SEM sinal -> sinal inferido pelo delta de saldo")
def _():
    rows = [
        ["Data", "Histórico", "Documento", "Valor Lançamento", "Saldo"],
        ["", "SALDO ANTERIOR", "", "", "34074,28"],
        ["02/01/2026", "PIX RECEBIDO", "051039", "2400000,00", "2434074,28"],
        ["02/01/2026", "PAG FORNEC", "451688", "2430000,00", "4074,28"],
    ]
    r = ingest_tabular_rows(rows)
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 1, 2), Decimal("-2430000.00")),   # saldo 2434074,28 -> 4074,28
        (date(2026, 1, 2), Decimal("2400000.00")),    # saldo 34074,28 -> 2434074,28
    ], r["transacoes"]


@caso("excel_serial_to_date converte serial do Excel (sistema 1900)")
def _():
    assert excel_serial_to_date(45658) == date(2025, 1, 1), excel_serial_to_date(45658)
    assert excel_serial_to_date(46023) == date(2026, 1, 1), excel_serial_to_date(46023)
    assert excel_serial_to_date(46027.6604) == date(2026, 1, 5)


@caso("tabular com serial Excel na coluna de data converte certo")
def _():
    rows = [
        ["Data Lançamento", "Histórico", "Documento", "Valor Lançamento", "Saldo"],
        [46023.5, "PIX RECEBIDO", "1", "100,00", "100,00"],
        [46024.5, "PAG FORNEC", "2", "30,00", "70,00"],
    ]
    r = ingest_tabular_rows(rows)
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 1, 1), Decimal("100.00")), (date(2026, 1, 2), Decimal("-30.00"))], r["transacoes"]


@caso("tabular header em INGLES (Mercado Pago): RELEASE_DATE/TRANSACTION_NET_AMOUNT + bloco de resumo")
def _():
    rows = [
        ["INITIAL_BALANCE", "CREDITS", "DEBITS", "FINAL_BALANCE"],
        ["612.480,15", "2.918.700,22", "-3.266.311,76", "264.868,61"],
        [],
        ["RELEASE_DATE", "TRANSACTION_TYPE", "REFERENCE_ID", "TRANSACTION_NET_AMOUNT", "PARTIAL_BALANCE"],
        ["01-01-2026", "Dinheiro retido", "100000000001", "-74,08", "612.406,07"],
        ["01-01-2026", "Reembolso", "100000000002", "63,76", "612.469,83"],
    ]
    r = ingest_tabular_rows(rows)
    assert _by_date_val(r["transacoes"]) == [
        (date(2026, 1, 1), Decimal("-74.08")), (date(2026, 1, 1), Decimal("63.76"))], r["transacoes"]


@caso("header abaixo da linha 25 (bloco de metadados grande, ex.: BTG) ainda e achado")
def _():
    rows = [["meta", "x"]] * 30 + [
        ["Data", "Histórico", "Valor (R$)", "Saldo (R$)"],
        ["02/01/2026", "PIX RECEBIDO", "100,00", "100,00"],
    ]
    r = ingest_tabular_rows(rows)
    assert len(r["transacoes"]) == 1, r
    assert r["transacoes"][0]["valor"] == Decimal("100.00"), r["transacoes"]


@caso("sem coluna de data/valor detectavel -> status MAPEAR_COLUNAS, nao quebra")
def _():
    rows = [["foo", "bar", "baz"], ["1", "2", "3"]]
    r = ingest_tabular_rows(rows)
    assert r["status"] == "MAPEAR_COLUNAS", r
    assert r["transacoes"] == [], r


@caso("rows vazio -> VAZIO, nao quebra")
def _():
    r = ingest_tabular_rows([])
    assert r["status"] == "VAZIO", r


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> INGESTAO TABULAR OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
