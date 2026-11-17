# -*- coding: utf-8 -*-
"""Prova de completude (SPEC-00 §7): irma da prova saldo-corrente do `conversor-extrato`.

    Σ lancamentos.valor + Σ encargos.valor == total_fatura   (tolerancia 1 centavo)

Sem `total_fatura` impresso reconhecido, a prova NAO pode fechar nem reprovar
por falta de gabarito -> `BAIXA CONFIANCA` (nunca `OK` sem prova real). Um
FaturaParsed sem NENHUM lancamento nem encargo (nada extraido) e sinal de
layout nao reconhecido -> `LAYOUT DESCONHECIDO`.
"""
from __future__ import annotations

from decimal import Decimal

from modelo import BAIXA_CONFIANCA, LAYOUT_DESCONHECIDO, OK, TOTAL_NAO_FECHA, FaturaParsed

TOLERANCIA = Decimal("0.01")

# Veredictos que ja saem "reprovados" antes de chegar aqui; a prova de total nao
# deve mascarar um problema de layout com um veredicto de completude.
_VEREDICTOS_TRAVADOS = {LAYOUT_DESCONHECIDO}


def validar(fatura: FaturaParsed) -> FaturaParsed:
    """Prova do total e, por cima, a rede de seguranca: linha com data que o leitor nao leu impede o OK, mesmo com
    a soma fechando (Gate 2 do clone: uma compra e um estorno perdidos se anulam). Muta e devolve `fatura`."""
    _validar_total(fatura)
    n = fatura.linhas_nao_lidas
    if n and fatura.veredicto != LAYOUT_DESCONHECIDO:
        if fatura.veredicto == OK:
            fatura.veredicto = BAIXA_CONFIANCA
        nota = f"{n} linha(s) com data nao lida(s): a extracao pode estar incompleta"
        fatura.aviso = f"{fatura.aviso}; {nota}" if fatura.aviso else nota
    return fatura


def _validar_total(fatura: FaturaParsed) -> FaturaParsed:
    """Muta `fatura.veredicto`/`fatura.aviso` conforme o fechamento do total.

    Devolve o mesmo objeto (mutacao in-place), para encadear com o resto do pipeline.
    """
    if fatura.veredicto in _VEREDICTOS_TRAVADOS:
        return fatura

    if not fatura.lancamentos and not fatura.encargos:
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = fatura.aviso or "nenhum lancamento nem encargo reconhecido no PDF"
        return fatura

    if fatura.total_fatura is None:
        fatura.veredicto = BAIXA_CONFIANCA
        fatura.aviso = "sem total impresso reconhecido; nao foi possivel provar completude"
        return fatura

    calculado = fatura.total_calculado
    delta = abs(calculado - fatura.total_fatura)
    if delta > TOLERANCIA:
        fatura.veredicto = TOTAL_NAO_FECHA
        fatura.aviso = (
            f"total nao fecha: lancamentos+encargos={calculado}, "
            f"mas total impresso={fatura.total_fatura} (delta={delta})"
        )
        return fatura

    fatura.veredicto = OK
    fatura.aviso = ""
    return fatura
