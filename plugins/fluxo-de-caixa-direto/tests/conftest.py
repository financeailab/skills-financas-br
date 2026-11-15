# -*- coding: utf-8 -*-
"""Coloca scripts/ e scripts/engine no sys.path p/ os testes importarem os modulos do motor
de forma plana: `import ingest_ofx`, `from categorizador import categorizar`, etc.

Dois layouts: o monorepo (tests/ ao lado de scripts/, dentro de motor/) e o repositorio
publico (tests/ na raiz do plugin, scripts/ em skills/fluxo-de-caixa-direto/).

Tambem expoe CONVERSOR_ENGINE (dir do motor conversor-extrato) p/ o teste de
ACEITE REVERSO: o OFX que o conversor emite precisa ser lido pelo nosso
ingest_ofx (SPEC-00 §9). So existe no monorepo; fora dele o teste e pulado."""
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # motor/ ou plugins/<nome>/
if os.path.isfile(os.path.join(RAIZ, "scripts", "fluxo_caixa.py")):
    SCRIPTS = os.path.join(RAIZ, "scripts")
else:
    SCRIPTS = os.path.join(RAIZ, "skills", "fluxo-de-caixa-direto", "scripts")
ENGINE = os.path.join(SCRIPTS, "engine")
CONVERSOR_ENGINE = os.path.abspath(os.path.join(
    RAIZ, "..", "..", "conversor-extrato", "motor", "scripts", "engine"))

for p in (ENGINE, SCRIPTS):
    if p not in sys.path:
        sys.path.insert(0, p)
