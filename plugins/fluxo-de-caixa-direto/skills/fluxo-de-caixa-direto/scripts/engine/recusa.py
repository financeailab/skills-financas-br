# -*- coding: utf-8 -*-
"""Recusa do proprio motor: o texto e montado aqui, so com numero de linha, coluna
logica, limite e o que a pessoa digitou na linha de comando; nunca com texto do
arquivo dela. E a unica excecao cujo texto o CLI imprime."""


class Recusa(ValueError):
    """Entrada recusada pelo motor, com mensagem segura para a saida."""
