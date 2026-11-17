# -*- coding: utf-8 -*-
"""Testa o parser tipo-Itau contra o fixture gerado + o gabarito de gen_faturas_pdf.esperado()."""
import os

import pdfplumber
import pytest

import gen_faturas_pdf as gpdf
from bancos import itau


@pytest.fixture(scope="module")
def paginas(tmp_path_factory):
    outdir = str(tmp_path_factory.mktemp("itau_fixture"))
    path = gpdf.gerar("itau", os.path.join(outdir, "itau.pdf"))
    with pdfplumber.open(path) as pdf:
        return [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]


def test_parse_itau_cabecalho(paginas):
    r = itau.parse(paginas)
    esperado = gpdf.esperado("itau")
    assert r.emissor == "itau"
    assert r.vencimento == esperado["vencimento"]
    assert r.portadores == esperado["portadores"]


def test_parse_itau_lancamentos(paginas):
    r = itau.parse(paginas)
    esperado = gpdf.esperado("itau")["lancamentos"]
    assert len(r.lancamentos) == len(esperado)
    for lanc, esp in zip(r.lancamentos, esperado):
        assert lanc.data == esp["data"]
        assert lanc.portador == esp["portador"]
        assert lanc.estabelecimento == esp["estabelecimento"]
        assert lanc.parcela == esp["parcela"]
        assert lanc.moeda == esp["moeda"]
        assert lanc.valor == esp["valor"]
        assert lanc.internacional == (esp["moeda"] != "BRL")


def test_parse_itau_encargos_e_total(paginas):
    r = itau.parse(paginas)
    esperado = gpdf.esperado("itau")
    assert len(r.encargos) == len(esperado["encargos"])
    for enc, esp in zip(r.encargos, esperado["encargos"]):
        assert enc.rotulo == esp["rotulo"]
        assert enc.valor == esp["valor"]
    assert r.total_fatura == esperado["total_fatura"]


def test_parse_itau_parcela_extraida_no_formato_certo(paginas):
    r = itau.parse(paginas)
    parcelados = [l for l in r.lancamentos if l.parcela is not None]
    assert len(parcelados) == 1
    assert parcelados[0].parcela == "02/05"


def test_parse_itau_ordem_cronologica(paginas):
    r = itau.parse(paginas)
    datas = [l.data for l in r.lancamentos]
    assert datas == sorted(datas)


def test_parse_itau_estorno_negativo_capturado(paginas):
    """Achado Codex pre-PR: estorno ('R$ 64,90-', sufixo negativo) era pulado em
    silencio pela regex de valor. O lancamento negativo tem que aparecer na saida
    com valor negativo (schema canonico: +despesa/-estorno)."""
    from decimal import Decimal
    r = itau.parse(paginas)
    estornos = [l for l in r.lancamentos if l.valor < 0]
    assert len(estornos) == 1
    assert estornos[0].valor == Decimal("-64.90")
    assert "Estorno" in estornos[0].estabelecimento


def test_parse_itau_total_fecha_com_estorno(paginas):
    """A prova de completude so fecha se o estorno for capturado (o total impresso
    no fixture ja desconta o estorno)."""
    from prova_total import validar
    r = itau.parse(paginas)
    validar(r)
    assert r.veredicto == "OK"


def test_parse_itau_layout_desconhecido_sem_cabecalho():
    paginas_ruins = [{"texto": "documento qualquer sem nada reconhecivel", "words": []}]
    r = itau.parse(paginas_ruins)
    assert r.veredicto == "LAYOUT DESCONHECIDO"
    assert r.aviso != ""
