#!/usr/bin/env python3
"""Cheque sem rede: AST fail-closed por lista fechada de imports permitidos.

Uso: python checar_sem_rede.py <pasta>

Varre <pasta>/**/skills/<nome>/scripts/**/*.py; cada diretorio skills/<nome>/scripts
usa a allowlist do plugin <nome> (stdlib + terceiros + internos declarados em
imports-permitidos.json). Se <pasta> nao contiver nenhum diretorio nesse formato,
trata <pasta> como uma pasta de scripts de motor (uso direto nos motores do
monorepo) e varre todo .py sob ela usando a uniao das allowlists de todos os plugins.

Reprova (uma linha por achado, "arquivo:linha: motivo"):
- erro de parse;
- import (estatico, em qualquer nivel, inclusive dentro de funcao) de modulo cujo
  nome de topo nao esteja na allowlist aplicavel (import relativo do proprio
  pacote e sempre permitido);
- chamada a __import__, exec, eval, compile, qualquer atributo de importlib,
  os.system, os.popen, os.exec*, os.spawn*, os.posix_spawn* (inclusive via
  "from os import system" etc., mesmo sem chamada).

Excecao: import de modulo listado em "excecoes" do JSON, casado por nome de
arquivo, nome do modulo e (quando declarada) nome da funcao que envolve o
no (hoje: "import gspread" dentro de "push_para_sheet" em sheets_push.py;
fora dessa funcao, no topo do arquivo ou em outra funcao, reprova).
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "imports-permitidos.json"

_OS_FORBIDDEN_PREFIXES = ("exec", "spawn", "posix_spawn")
_OS_FORBIDDEN_EXACT = {"system", "popen"}
_BUILTIN_FORBIDDEN = {"__import__", "exec", "eval", "compile"}


def carregar_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _allowlist_para_plugin(config: dict, nome_plugin):
    permitidos = set(config["stdlib"])
    plugins = config["plugins"]
    alvo = [plugins[nome_plugin]] if nome_plugin in plugins else plugins.values()
    for p in alvo:
        permitidos.update(p.get("terceiros", []))
        permitidos.update(p.get("internos", []))
    return permitidos


def _excecao_permite(config: dict, arquivo: Path, nome_modulo: str, funcao_atual) -> bool:
    for exc in config.get("excecoes", []):
        if arquivo.name != exc["arquivo"] or nome_modulo != exc["import"]:
            continue
        if "funcao" in exc and exc["funcao"] != funcao_atual:
            continue  # mesmo import, fora da funcao declarada: nao e excecao
        return True
    return False


def _os_forbidden(attr: str) -> bool:
    return attr in _OS_FORBIDDEN_EXACT or attr.startswith(_OS_FORBIDDEN_PREFIXES)


class _Visitor(ast.NodeVisitor):
    """Anda a arvore rastreando a funcao que envolve cada no (para a excecao
    por funcao) e coleta os achados."""

    def __init__(self, caminho: Path, allowlist: set, config: dict):
        self.caminho = caminho
        self.allowlist = allowlist
        self.config = config
        self.achados: list[tuple[int, str]] = []
        self._pilha_funcoes: list[str] = []
        self._os_nomes = {"os"}  # nomes que apontam para o modulo os ("import os as s")

    def _funcao_atual(self):
        return self._pilha_funcoes[-1] if self._pilha_funcoes else None

    def _excecao(self, nome_modulo: str) -> bool:
        return _excecao_permite(self.config, self.caminho, nome_modulo, self._funcao_atual())

    def visit_FunctionDef(self, node):
        self._pilha_funcoes.append(node.name)
        self.generic_visit(node)
        self._pilha_funcoes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node):
        for alias in node.names:
            topo = alias.name.split(".")[0]
            if alias.name == "os" and alias.asname:
                self._os_nomes.add(alias.asname)
            if topo not in self.allowlist and not self._excecao(topo):
                self.achados.append((node.lineno, f"import '{alias.name}' fora da allowlist"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level and node.level > 0:
            self.generic_visit(node)
            return  # import relativo do proprio pacote: sempre permitido
        topo = (node.module or "").split(".")[0]
        if topo == "os":
            for alias in node.names:
                if alias.name == "*" or _os_forbidden(alias.name):
                    self.achados.append(
                        (node.lineno, f"'from os import {alias.name}': chamada proibida")
                    )
        if topo not in self.allowlist and not self._excecao(topo):
            self.achados.append((node.lineno, f"import '{topo}' fora da allowlist"))
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id in _BUILTIN_FORBIDDEN:
            self.achados.append((node.lineno, f"chamada proibida '{func.id}'"))
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            if base == "importlib":
                self.achados.append((node.lineno, f"chamada proibida 'importlib.{func.attr}'"))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # pega chamada e simples referencia (f = os.system), inclusive via alias
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in self._os_nomes
            and _os_forbidden(node.attr)
        ):
            self.achados.append((node.lineno, f"uso proibido 'os.{node.attr}'"))
        self.generic_visit(node)


def checar_arquivo(caminho: Path, allowlist: set, config: dict):
    """Retorna lista de (linha, motivo) para um arquivo."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except SyntaxError as e:
        return [(e.lineno or 1, f"erro de parse: {e.msg}")]

    visitor = _Visitor(caminho, allowlist, config)
    visitor.visit(arvore)
    return visitor.achados


def _encontrar_arquivos(pasta: Path):
    """Retorna lista de (arquivo.py, nome_do_plugin_ou_None)."""
    dirs_skills = sorted(pasta.glob("**/skills/*/scripts"))
    if dirs_skills:
        return [
            (py, d.parent.name)
            for d in dirs_skills
            for py in sorted(d.rglob("*.py"))
        ]
    # modo motor: <pasta> ja e uma pasta scripts/ de um motor do monorepo (sem
    # skills/<nome>/scripts dentro), entao nao da pra inferir o plugin pelo
    # caminho; usa a uniao de todas as allowlists (None = sem plugin unico).
    # So serve para rodar direto nos motores do monorepo; no layout real do
    # repo publico (plugins/<nome>/skills/<nome>/scripts) vale a lista do
    # proprio plugin, isolada (ramo acima).
    return [(py, None) for py in sorted(pasta.rglob("*.py"))]


def main(argv) -> int:
    if len(argv) != 2:
        print("uso: checar_sem_rede.py <pasta>", file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consoles cp1252 do Windows nao tem U+2713
    pasta = Path(argv[1])
    config = carregar_config()
    arquivos = _encontrar_arquivos(pasta)

    total_achados = 0
    for caminho, nome_plugin in arquivos:
        allowlist = _allowlist_para_plugin(config, nome_plugin)
        for linha, motivo in checar_arquivo(caminho, allowlist, config):
            print(f"{caminho}:{linha}: {motivo}")
            total_achados += 1

    if total_achados:
        return 1
    print(f"✓ sem rede: {len(arquivos)} arquivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
