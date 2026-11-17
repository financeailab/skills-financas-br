# -*- coding: utf-8 -*-
"""Testes do emissor CSV (emit_csv.py)."""
from datetime import date
from decimal import Decimal

from modelo import Encargo, FaturaParsed, Lancamento
from emit_csv import emit


def _fatura():
    return FaturaParsed(
        emissor="itau",
        portadores=["CARLOS EDUARDO LIMA"],
        lancamentos=[
            Lancamento(date(2026, 1, 5), "Supermercado Bom Preco", Decimal("358.40"),
                       portador="CARLOS EDUARDO LIMA"),
            Lancamento(date(2026, 1, 8), "Loja Tech Informatica", Decimal("210.00"),
                       portador="CARLOS EDUARDO LIMA", parcela="02/05"),
            Lancamento(date(2026, 1, 12), "Hotel Barcelona Espanha", Decimal("892.15"),
                       portador="MARIA SILVA SOUZA", moeda="EUR", internacional=True),
        ],
        encargos=[Encargo("IOF", Decimal("53.53"))],
        total_fatura=Decimal("1514.08"),
    )


def test_emit_csv_tem_bom_e_cabecalho():
    texto = emit(_fatura())
    assert texto.startswith("﻿")
    primeira_linha = texto.split("\r\n")[0].lstrip("﻿")
    assert primeira_linha == "data;portador;estabelecimento;parcela;valor;moeda;internacional"


def test_emit_csv_uma_linha_por_lancamento_mais_encargos():
    texto = emit(_fatura())
    linhas = [l for l in texto.split("\r\n") if l]
    # 1 cabecalho + 3 lancamentos + 1 encargo
    assert len(linhas) == 5


def test_emit_csv_campos_do_lancamento_parcelado():
    texto = emit(_fatura())
    linhas = texto.split("\r\n")
    linha_parcelada = next(l for l in linhas if "Loja Tech Informatica" in l)
    campos = linha_parcelada.split(";")
    assert campos[0] == "2026-01-08"
    assert campos[1] == "CARLOS EDUARDO LIMA"
    assert campos[3] == "02/05"
    assert campos[4] == "210.00"
    assert campos[6] == "nao"


def test_emit_csv_lancamento_internacional_marcado():
    texto = emit(_fatura())
    linhas = texto.split("\r\n")
    linha_intl = next(l for l in linhas if "Hotel Barcelona" in l)
    campos = linha_intl.split(";")
    assert campos[5] == "EUR"
    assert campos[6] == "sim"


def test_emit_csv_encargo_vira_linha_com_rotulo():
    texto = emit(_fatura())
    assert "Encargo: IOF" in texto
    assert "53.53" in texto


def test_emit_csv_escapa_ponto_e_virgula_na_descricao():
    fatura = FaturaParsed(lancamentos=[
        Lancamento(date(2026, 1, 1), "Loja A; Filial B", Decimal("10.00")),
    ])
    texto = emit(fatura)
    assert '"Loja A; Filial B"' in texto
