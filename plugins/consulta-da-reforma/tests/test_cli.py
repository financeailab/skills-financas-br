# -*- coding: utf-8 -*-
"""CLI (V3, V5 e bordas): cabecalho em toda saida, codigos de saida, entrada nunca ecoada, limites."""
import datetime
import os
import sqlite3
import subprocess
import sys

import pytest

from conftest import SCRIPTS

import base  # noqa: E402
import consultar  # noqa: E402  (SCRIPTS ja esta no sys.path pelo conftest)

CLI = os.path.join(SCRIPTS, "consultar.py")
SENT = "SENTINELA"


@pytest.fixture(scope="module")
def rodar(tmp_path_factory):
    tmp = str(tmp_path_factory.mktemp("tmp cli"))
    env = {**os.environ, "TMP": tmp, "TEMP": tmp, "TMPDIR": tmp}

    def _rodar(*args):
        return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300, env=env)
    return _rodar


def _cabecalho_ok(saida):
    m = base.ler_manifesto()  # derivado do manifesto: segue valendo depois de cada atualizacao da copia
    linhas = saida.splitlines()
    assert linhas[0] == consultar.LINHA_1
    assert linhas[1].startswith(f"Cópia das tabelas de {consultar.br(m['data_copia'])} (commit {m['commit_sql'][:8]} "
                                f"de {consultar.br(m['data_commit_sql'])}, base {m['versao_base']})")


@pytest.mark.parametrize("args, codigo", [
    (["cclasstrib", "200028", "--data", "2027-03-10"], 0),
    (["cclasstrib", "999999"], 1),
    (["cclasstrib", "200028", "--data", "1990-01-01"], 1),
    (["cclasstrib", "12345"], 2),
    (["referencia", "--data", "2026-06-01"], 0),
    (["referencia", "--data", "2027-01-01"], 1),
    (["ncm", "2203.00.00", "--data", "2027-03-10"], 0),
    (["nbs", "122011200", "--data", "2027-03-10"], 0),
    (["nbs", "12201"], 2),
    (["vinculo", "--ncm", "02071100", "--cclasstrib", "200003", "--data", "2026-06-01"], 0),
    (["vinculo", "--ncm", "020712", "--cclasstrib", "200003", "--data", "2026-06-01"], 2),
    (["vinculo", "--ncm", "99999999", "--cclasstrib", "000001", "--data", "2027-03-10"], 1),
    (["vinculo", "--ncm", "99999999", "--cclasstrib", "200003", "--data", "2026-06-01"], 1),
    (["simples", "--data", "2027-01-01"], 0),
    (["simples", "09", "--data", "2026-06-01"], 1),
    (["buscar", "educacao"], 0),
    (["buscar", "zzzqqq"], 1),
    (["sobre"], 0),
    (["inexistente"], 2),
    ([], 2),
])
def test_cabecalho_e_codigo_de_saida(rodar, args, codigo):
    r = rodar(*args)
    assert r.returncode == codigo, r.stdout
    _cabecalho_ok(r.stdout)


@pytest.mark.parametrize("args", [
    ["cclasstrib", SENT], ["ncm", SENT], ["buscar", SENT + "%$"], ["cclasstrib", "200028", "--data", SENT],
    ["vinculo", "--ncm", SENT, "--cclasstrib", "200003"], ["--" + SENT], ["simples", SENT],
])
def test_entrada_invalida_nao_ecoa(rodar, args):
    r = rodar(*args)
    assert r.returncode == 2
    assert SENT not in r.stdout and SENT not in r.stderr


def test_ausente_nulo_e_zero_tem_textos_proprios(rodar):
    r = rodar("ncm", "10063021", "--data", "2027-03-10")
    assert "Imposto Seletivo: sem incidência na base oficial" in r.stdout
    r = rodar("ncm", "22030000", "--data", "2027-03-10")
    assert "alíquota ad valorem não definida na base oficial" in r.stdout and " 0%" not in r.stdout
    r = rodar("cclasstrib", "000001", "--data", "2027-03-10")
    assert "Redução: CBS 0%; IBSUF 0%; IBSMun 0%" in r.stdout


def test_busca_sem_acento_e_limite(rodar):
    r = rodar("buscar", "EDUCAÇÃO")
    assert "200028:" in r.stdout
    r = rodar("buscar", "servicos")
    total = int(r.stdout.split("Encontrados ")[1].split(";")[0])
    assert total > 20 and "mostrando 20:" in r.stdout
    assert len([linha for linha in r.stdout.splitlines() if linha[:6].isdigit()]) == 20


@pytest.mark.parametrize("termo, valido", [("ab", False), ("abc", True), ("a" * 60, True), ("a" * 61, False),
                                           ("educação", True), ("50%", False), ("   ", False)])
def test_limite_do_termo(termo, valido):
    assert (consultar.termo_valido(termo) is not None) == valido


@pytest.mark.parametrize("texto, tamanhos, esperado", [
    ("22", range(2, 9), "22"), ("2203.00.00", range(2, 9), "22030000"), ("2", range(2, 9), None),
    ("220300001", range(2, 9), None), ("٢٢٠٣", range(2, 9), None),
    ("1.2201.12.00", (9,), "122011200"),
])
def test_codigo_valido(texto, tamanhos, esperado):
    assert consultar.codigo_valido(texto, tamanhos) == esperado


@pytest.mark.parametrize("dias, aviso", [(0, False), (60, False), (61, True)])
def test_aviso_de_idade(dias, aviso):
    m = {"data_copia": "2026-11-18", "commit_sql": "8c538c9b" + "0" * 32, "data_commit_sql": "2026-10-22",
         "versao_base": "V0059"}
    linhas = consultar.cabecalho(m, datetime.date(2026, 11, 18) + datetime.timedelta(days=dias))
    assert len(linhas) == (3 if aviso else 2)
    if aviso:
        assert f"{dias} dias" in linhas[2]


def test_data_valida():
    hoje = datetime.date(2026, 11, 18)
    assert consultar.data_valida(None, hoje) == "2026-11-18"
    assert consultar.data_valida("2027-02-29", hoje) is None
    assert consultar.data_valida("20270310", hoje) is None
    assert consultar.data_valida("2027-03-10", hoje) == "2027-03-10"


@pytest.mark.parametrize("erro", [OSError(), PermissionError(), sqlite3.OperationalError()])
def test_falha_ao_montar_o_banco_e_codigo_3(monkeypatch, capsys, erro):
    def falha(*_a, **_k):
        raise erro

    monkeypatch.setattr(base, "abrir", falha)
    assert consultar.main(["cclasstrib", "200028"]) == 3
    saida = capsys.readouterr().out.splitlines()
    assert saida[0] == consultar.LINHA_1 and saida[-1] == consultar.SEM_BANCO


def test_aliquota_definida_sai_com_unidade():
    assert consultar._texto_is((10.0,), "ad valorem") == "alíquota ad valorem 10%"
    assert consultar._texto_is((1.5, "Vintena de cigarro"), "ad rem") == "alíquota ad rem 1,5 por vintena de cigarro"
    assert consultar._texto_is((1.5, None), "ad rem") == "alíquota ad rem 1,5 por unidade da tabela"
    assert consultar._texto_is((None,), "ad valorem") == "alíquota ad valorem não definida na base oficial"


@pytest.mark.parametrize("valor, texto", [(60.0, "60"), (0.9, "0,9"), (12.345678, "12,345678"), ("x", "x")])
def test_num_sem_arredondar(valor, texto):
    assert consultar.num(valor) == texto


def test_ncm_curta_com_is_nos_subitens_nao_diz_sem_incidencia(rodar):
    # 2402 nao tem linha propria de IS, mas 24021000 tem
    r = rodar("ncm", "2402", "--data", "2027-03-10")
    assert r.returncode == 0 and "sem incidência" not in r.stdout
    assert "Imposto Seletivo: incide em subitens desta NCM nesta data" in r.stdout


def test_ncm_depois_das_linhas_do_is_nao_diz_sem_incidencia(rodar):
    # as linhas do IS acabam em 31/12/2033; depois disso a base nao afirma nada
    r = rodar("ncm", "2203.00.00", "--data", "2034-01-01")
    assert r.returncode == 0 and "sem incidência" not in r.stdout
    assert "traz linhas do Imposto Seletivo para esta NCM só até 31/12/2033" in r.stdout


def test_ncm_antes_do_is_diz_que_ainda_nao_vige(rodar):
    # o exemplo da SKILL (cerveja) com data anterior ao IS
    r = rodar("ncm", "2203.00.00", "--data", "2026-06-01")
    assert r.returncode == 0 and "sem incidência" not in r.stdout
    assert "Imposto Seletivo: ainda não vige nesta data (na base oficial, começa em 01/01/2027)" in r.stdout


def test_simples_codigo_inexistente_nao_culpa_o_catalogo(rodar):
    r = rodar("simples", "99", "--data", "2027-01-01")
    assert r.returncode == 1 and "Nenhuma atividade do Simples Nacional com esse código nesta data." in r.stdout
    r = rodar("simples", "01", "--data", "2026-06-01")
    assert "o catálogo começa em 01/01/2027" in r.stdout
