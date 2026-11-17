# -*- coding: utf-8 -*-
"""Coloca scripts/engine no sys.path p/ os testes importarem os modulos do motor
de forma plana: `import modelo`, `from bancos import itau`, `import emit_csv`, etc.

Dois layouts: o monorepo (tests/ ao lado de scripts/, dentro de motor/) e o repositorio
publico (tests/ na raiz do plugin, scripts/ em skills/leitor-de-fatura-de-cartao/)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(HERE, ".."))  # motor/ ou plugins/<nome>/
if os.path.isfile(os.path.join(RAIZ, "scripts", "ler_fatura.py")):
    SCRIPTS = os.path.join(RAIZ, "scripts")
else:
    SCRIPTS = os.path.join(RAIZ, "skills", "leitor-de-fatura-de-cartao", "scripts")
ENGINE = os.path.join(SCRIPTS, "engine")
FIXTURES = os.path.join(HERE, "fixtures")

for p in (ENGINE, SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)
