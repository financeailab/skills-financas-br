# -*- coding: utf-8 -*-
"""V6: o motor so le tabelas. Nenhuma multiplicacao ou divisao em scripts/ (caminhos usam joinpath)."""
import ast
import pathlib

from conftest import SCRIPTS

PROIBIDOS = (ast.Mult, ast.Div, ast.FloorDiv, ast.MatMult)


def test_scripts_sem_multiplicacao_nem_divisao():
    achados = []
    for arq in pathlib.Path(SCRIPTS).rglob("*.py"):
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, (ast.BinOp, ast.AugAssign)) and isinstance(no.op, PROIBIDOS):
                achados.append(f"{arq.name}:{no.lineno}")
    assert not achados, achados
