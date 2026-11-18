# -*- coding: utf-8 -*-
"""Poe scripts/ e scripts/engine no sys.path, nos dois layouts: o monorepo (tests/ ao lado de scripts/ e de
tabelas/, dentro de motor/) e o repositorio publico (tests/ na raiz do plugin, o resto em
skills/consulta-da-reforma/). O banco e montado uma vez por sessao, num diretorio com espaco no nome (V7)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(HERE, ".."))
if os.path.isdir(os.path.join(RAIZ, "scripts")):  # monorepo; existe desde a T2 (scripts/engine), antes do consultar.py
    SKILL = RAIZ
else:
    SKILL = os.path.join(RAIZ, "skills", "consulta-da-reforma")
SCRIPTS = os.path.join(SKILL, "scripts")
TABELAS = os.path.join(SKILL, "tabelas")
for p in (os.path.join(SCRIPTS, "engine"), SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    import base
    c = base.abrir(cache_dir=tmp_path_factory.mktemp("cache com espaco"))
    yield c
    c.close()
