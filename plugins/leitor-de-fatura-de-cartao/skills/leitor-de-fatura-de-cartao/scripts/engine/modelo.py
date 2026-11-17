# -*- coding: utf-8 -*-
"""Contrato canonico do leitor de fatura de cartao corporativo (PDF -> CSV/XLSX).

Fonte unica das dataclasses que atravessam o motor: detector -> parser por emissor
-> prova de completude -> emissores. Todo parser DEVOLVE um FaturaParsed; todo
emissor CONSOME um FaturaParsed. Dinheiro sempre em Decimal (nunca float).

Convencao de sinal: +despesa (soma ao total) / -estorno (abate do total).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Veredictos possiveis (SPEC-00 §6). Nunca finge que leu tudo.
OK = "OK"
TOTAL_NAO_FECHA = "TOTAL NAO FECHA"
LAYOUT_DESCONHECIDO = "LAYOUT DESCONHECIDO"
BAIXA_CONFIANCA = "BAIXA CONFIANCA"


@dataclass
class Lancamento:
    """Um lancamento de estabelecimento na fatura. `valor` ja vem com sinal
    (+despesa/-estorno). `parcela` = "NN/NN" (ex. "02/05") ou None se a vista."""
    data: date
    estabelecimento: str
    valor: Decimal
    portador: str = ""
    parcela: str | None = None
    moeda: str = "BRL"
    internacional: bool = False


@dataclass
class Encargo:
    """Linha de rodape (nao e lancamento de estabelecimento): IOF, anuidade,
    juros de mora, multa. Sempre soma ao total da fatura."""
    rotulo: str
    valor: Decimal


@dataclass
class FaturaParsed:
    """Resultado de parsear uma fatura. A prova de completude opera sobre isto."""
    emissor: str = ""                 # itau | bradesco | generico
    vencimento: date | None = None
    portadores: list[str] = field(default_factory=list)  # derivado, ordem de aparicao
    lancamentos: list[Lancamento] = field(default_factory=list)
    encargos: list[Encargo] = field(default_factory=list)
    total_fatura: Decimal | None = None   # total IMPRESSO na fatura (gabarito da prova)
    veredicto: str = OK                   # OK | TOTAL NAO FECHA | LAYOUT DESCONHECIDO | BAIXA CONFIANCA
    aviso: str = ""
    linhas_nao_lidas: int = 0  # linhas com data que o leitor nao conseguiu ler: impedem o OK (prova_total.validar)

    @property
    def total_calculado(self) -> Decimal:
        """Soma (com sinal) dos lancamentos + encargos."""
        s = Decimal("0.00")
        for l in self.lancamentos:
            s += l.valor
        for e in self.encargos:
            s += e.valor
        return s
