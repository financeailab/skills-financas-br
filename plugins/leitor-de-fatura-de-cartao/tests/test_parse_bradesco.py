# -*- coding: utf-8 -*-
"""Testa o parser tipo-Bradesco (posicional) contra o fixture gerado + o gabarito."""
import os

import pdfplumber
import pytest

import gen_faturas_pdf as gpdf
from bancos import bradesco


@pytest.fixture(scope="module")
def paginas(tmp_path_factory):
    outdir = str(tmp_path_factory.mktemp("bradesco_fixture"))
    path = gpdf.gerar("bradesco", os.path.join(outdir, "bradesco.pdf"))
    with pdfplumber.open(path) as pdf:
        return [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]


def test_parse_bradesco_cabecalho(paginas):
    r = bradesco.parse(paginas)
    esperado = gpdf.esperado("bradesco")
    assert r.emissor == "bradesco"
    assert r.vencimento == esperado["vencimento"]
    assert r.portadores == esperado["portadores"]


def test_parse_bradesco_lancamentos(paginas):
    r = bradesco.parse(paginas)
    esperado = gpdf.esperado("bradesco")["lancamentos"]
    assert len(r.lancamentos) == len(esperado)
    for lanc, esp in zip(r.lancamentos, esperado):
        assert lanc.data == esp["data"]
        assert lanc.portador == esp["portador"]
        assert lanc.estabelecimento == esp["estabelecimento"]
        assert lanc.parcela == esp["parcela"]
        assert lanc.moeda == esp["moeda"]
        assert lanc.valor == esp["valor"]
        assert lanc.internacional == (esp["moeda"] != "BRL")


def test_parse_bradesco_encargos_e_total(paginas):
    r = bradesco.parse(paginas)
    esperado = gpdf.esperado("bradesco")
    assert len(r.encargos) == len(esperado["encargos"])
    for enc, esp in zip(r.encargos, esperado["encargos"]):
        assert enc.rotulo == esp["rotulo"]
        assert enc.valor == esp["valor"]
    assert r.total_fatura == esperado["total_fatura"]


def test_parse_bradesco_parcela_extraida_no_formato_certo(paginas):
    r = bradesco.parse(paginas)
    parcelados = [l for l in r.lancamentos if l.parcela is not None]
    assert len(parcelados) == 1
    assert parcelados[0].parcela == "03/06"


def test_parse_bradesco_ordem_cronologica(paginas):
    r = bradesco.parse(paginas)
    datas = [l.data for l in r.lancamentos]
    assert datas == sorted(datas)


def test_parse_bradesco_estorno_negativo_capturado(paginas):
    """Achado Codex pre-PR: estorno ('-30,00', prefixo negativo na coluna VALOR)
    era pulado em silencio pela regex de valor."""
    from decimal import Decimal
    r = bradesco.parse(paginas)
    estornos = [l for l in r.lancamentos if l.valor < 0]
    assert len(estornos) == 1
    assert estornos[0].valor == Decimal("-30.00")
    assert "Estorno" in estornos[0].estabelecimento


def test_parse_bradesco_total_fecha_com_estorno(paginas):
    from prova_total import validar
    r = bradesco.parse(paginas)
    validar(r)
    assert r.veredicto == "OK"


def test_parse_bradesco_layout_desconhecido_sem_cabecalho():
    paginas_ruins = [{"texto": "documento qualquer sem nada reconhecivel", "words": []}]
    r = bradesco.parse(paginas_ruins)
    assert r.veredicto == "LAYOUT DESCONHECIDO"
    assert r.aviso != ""
