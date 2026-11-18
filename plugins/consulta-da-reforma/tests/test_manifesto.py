# -*- coding: utf-8 -*-
"""Manifesto ausente, ilegivel ou incompleto: cabecalho fixo e codigo 3, nunca 2 nem silencio."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import base
from conftest import SCRIPTS, TABELAS

ORIGINAL = json.loads(Path(TABELAS).joinpath("MANIFESTO.json").read_text(encoding="utf-8"))


def _sem(campo):
    m = dict(ORIGINAL)
    del m[campo]
    return m


CASOS = {
    "vazio": {},
    "lista": [],
    "sem data_copia": _sem("data_copia"),
    "sem arquivos": _sem("arquivos"),
    "data impossivel": {**ORIGINAL, "data_copia": "2026-13-40"},
    "data em outro formato": {**ORIGINAL, "data_copia": "18/11/2026"},
    "commit curto": {**ORIGINAL, "commit_sql": "8c538c9b"},
    "versao fora do padrao": {**ORIGINAL, "versao_base": "59"},
    "hash invalido": {**ORIGINAL, "arquivos": {"criacao/afterMigrate.sql": "x"}},
    "campo de outro tipo": {**ORIGINAL, "licenca": 1},
}


def _skill_com(tmp_path, conteudo):
    """Copia scripts/ e tabelas/ para tmp e troca o manifesto; conteudo None = sem arquivo, str = texto cru."""
    raiz = tmp_path.joinpath("skill")
    shutil.copytree(SCRIPTS, raiz.joinpath("scripts"), ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TABELAS, raiz.joinpath("tabelas"), ignore=shutil.ignore_patterns("__pycache__"))
    alvo = raiz.joinpath("tabelas", "MANIFESTO.json")
    if conteudo is None:
        alvo.unlink()
    else:
        alvo.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding="utf-8")
    return raiz


@pytest.mark.parametrize("nome", list(CASOS))
def test_ler_manifesto_recusa(tmp_path, nome):
    raiz = _skill_com(tmp_path, CASOS[nome])
    with pytest.raises(base.ManifestoInvalido):
        base.ler_manifesto(raiz.joinpath("tabelas"))


@pytest.mark.parametrize("conteudo", [None, "{nao e json", CASOS["vazio"], CASOS["sem data_copia"],
                                      CASOS["data impossivel"], CASOS["commit curto"]],
                         ids=["ausente", "ilegivel", "vazio", "sem data_copia", "data impossivel", "commit curto"])
def test_cli_com_manifesto_invalido(tmp_path, conteudo):
    raiz = _skill_com(tmp_path, conteudo)
    tmp = str(tmp_path.joinpath("tmp"))
    os.makedirs(tmp)
    r = subprocess.run([sys.executable, str(raiz.joinpath("scripts", "consultar.py")), "cclasstrib", "200028"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       env={**os.environ, "TMP": tmp, "TEMP": tmp, "TMPDIR": tmp})
    assert r.returncode == 3, (r.stdout, r.stderr)
    linhas = r.stdout.splitlines()
    assert linhas[:2] == [
        "Consulta de tabela oficial da Receita Federal (calculadora-rtc, MIT). Não é parecer tributário.",
        "O manifesto da cópia das tabelas está ausente, ilegível ou incompleto (tabelas/MANIFESTO.json). "
        "Reinstale a skill; nada foi consultado.",
    ]
    assert r.stderr == ""


def test_manifesto_real_passa():
    assert base.ler_manifesto(Path(TABELAS)) == ORIGINAL
