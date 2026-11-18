# -*- coding: utf-8 -*-
"""Oraculo (V1): as asserções do spike, conferidas contra docs/exemplos.md da Receita, o
AtividadeSimplesControllerTest do repo do Simples e o Teste_tpdoc_9_RegressaoAnexoVigenciaExcecao."""
import pytest

import consultas

D27, D26 = "2027-03-10", "2026-06-01"


@pytest.mark.parametrize("codigo, grupo, data, cst, reducao", [
    ("200028", "cbs-ibs", D27, "200", {60.0}),   # educacao (exemplos.md, item 3)
    ("200003", "cbs-ibs", D27, "200", {100.0}),  # cesta basica (exemplos.md, item 1)
    ("000001", "cbs-ibs", D27, "000", {0.0}),    # tributacao integral grava reducao 0%
    ("000001", "is", D27, "000", None),          # a mesma cClassTrib no grupo IS, desde 2027
])
def test_classificacao(con, codigo, grupo, data, cst, reducao):
    r = consultas.classificacao(con, codigo, data, grupo)
    assert r["cst"] == cst
    if reducao is not None:
        assert {v for _, v in r["reducoes"]} == reducao
        assert [s for s, _ in r["reducoes"]] == ["CBS", "IBSUF", "IBSMun"]


def test_classificacao_is_nao_existe_em_2026(con):
    assert consultas.classificacao(con, "000001", D26, "is") is None


def test_referencia(con):
    assert consultas.referencia(con, D26) == [("CBS", 0.9), ("IBSUF", 0.1), ("IBSMun", 0.0)]
    assert consultas.referencia(con, "2027-01-01") == []


def test_referencia_borda_do_ano(con):
    assert len(consultas.referencia(con, "2026-12-31")) == 3
    assert consultas.referencia(con, "2027-01-01") == []


def test_ncm_imposto_seletivo(con):
    cerveja = consultas.ncm(con, "22030000", D27)
    assert cerveja["is_ad_valorem"] == (None,)  # incide, aliquota nao definida em lei
    arroz = consultas.ncm(con, "10063021", D27)
    assert arroz["is_ad_valorem"] is None and arroz["is_ad_rem"] is None


def test_is_por_nbs_vazio(con):
    assert con.execute("SELECT count(*) FROM ALIQUOTA_AD_VALOREM_SERVICO").fetchone()[0] == 0


@pytest.mark.parametrize("ncm, cclasstrib, data, grupo, esperado", [
    ("22030000", "000001", D27, "is", consultas.VINCULADA),
    ("22030000", "000001", D27, "cbs-ibs", consultas.SEM_LISTA),
    ("10063021", "200003", D27, "cbs-ibs", consultas.VINCULADA),
    ("02013000", "200035", D27, "cbs-ibs", consultas.NAO_VINCULADA),   # REG-011 do exemplos.md
    ("02074300", "200003", D26, "cbs-ibs", consultas.NAO_VINCULADA),   # excepcionada, A=1 E=1 S=0
    ("02071100", "200003", D26, "cbs-ibs", consultas.VINCULADA),       # generico, A=1 E=0
    ("24021000", "200003", D26, "cbs-ibs", consultas.NAO_VINCULADA),   # fora do anexo, A=0
    ("020712", "200003", D26, "cbs-ibs", consultas.INCOMPLETO),        # NCM de 6 digitos que existe; a lista exige 8
    ("99999999", "000001", D27, "cbs-ibs", consultas.CODIGO_INEXISTENTE),  # sem lista, mas a NCM nao existe
    ("99999999", "200003", D26, "cbs-ibs", consultas.CODIGO_INEXISTENTE),  # com lista, NCM inexistente
    ("220", "000001", D27, "cbs-ibs", consultas.CODIGO_INEXISTENTE),       # 3 digitos: nivel que nao existe
])
def test_vinculo(con, ncm, cclasstrib, data, grupo, esperado):
    assert consultas.vinculo(con, "ncm", ncm, cclasstrib, data, grupo) == esperado


def test_simples(con):
    atv = consultas.simples(con, "2027-01-01")
    assert len(atv) == 15
    assert atv[0][0] == "01" and atv[0][2:4] == ("I", None)
    assert atv[1][4] == "I, menos ICMS"
    assert [a[0] for a in atv if a[3]] == ["09"]
    assert atv[13][0] == "14" and atv[14][0] == "90" and atv[14][2:4] == (None, None)


def test_simples_antes_do_catalogo(con):
    assert consultas.simples(con, "2026-06-01") == []
