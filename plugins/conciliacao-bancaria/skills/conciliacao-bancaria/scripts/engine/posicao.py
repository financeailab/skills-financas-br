# -*- coding: utf-8 -*-
"""Consolidador de Posicao de Caixa — varre uma pasta de OFX e soma os saldos.

Modo "posicao" da Conciliacao Bancaria (reusa o parser ingest_ofx.py). Para cada
arquivo .ofx de uma pasta: le o saldo final (LEDGERBAL), classifica conta x cartao,
soma o caixa e devolve o status contra um saldo minimo.

CONTRATO DE PRIVACIDADE (o mesmo fosso da conciliacao): este modulo roda LOCAL,
nao faz rede. O dado bruto (extrato) NUNCA sai daqui. So o resumo agregado (saldos
por conta, total, status) e exposto p/ a IA ou empurrado p/ uma Sheet — nunca a
linha de extrato.

Cartao x conta: a deteccao e ESTRUTURAL (envelope CREDITCARDMSGSRSV1). Como alguns
bancos (ex.: Nubank) exportam a CONTA no envelope de cartao, o cartao fica FORA do
caixa por padrao e o usuario pode forcar um arquivo como conta (forcar_conta).
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ingest_ofx import parse_ofx


@dataclass
class ContaConsolidada:
    arquivo: str
    banco: str
    agencia: str
    conta: str
    tipo_conta: str
    eh_cartao: bool
    saldo_final: Decimal | None
    data_saldo: object
    n_transacoes: int
    n_contas_no_arquivo: int
    entra_no_caixa: bool
    motivo_fora: str = ""        # "multiconta" / "cartao" / "sem saldo" / "moeda" / "repetida" / "repetida com saldos diferentes" / "" (entra)
    moeda: str = "BRL"           # CURDEF do arquivo (cru; a saida passa por moeda_saida)


@dataclass
class Consolidado:
    contas: list = field(default_factory=list)     # list[ContaConsolidada]
    total_caixa: Decimal = Decimal("0")
    saldo_minimo: Decimal | None = None
    n_caixa: int = 0
    n_cartoes: int = 0
    n_sem_saldo: int = 0
    n_multi_conta: int = 0
    n_repetidas: int = 0               # arquivos de conta ja contada em outro arquivo (fora do caixa)
    n_repetidas_conflito: int = 0      # contas repetidas com saldos diferentes na data mais recente (nenhuma entra)
    n_outra_moeda: int = 0             # contas em moeda que nao e BRL (fora do caixa)
    abaixo: bool = False
    deficit: Decimal = Decimal("0")
    por_banco: dict = field(default_factory=dict)  # banco -> total (so caixa)
    erros: list = field(default_factory=list)      # arquivos que falharam no parse


def varrer_pasta(pasta: str) -> list:
    """Le todos os .ofx da pasta -> list[(caminho, ExtratoOFX|None)]. Robusto: arquivo
    que falha no parse vira (caminho, None) (contabilizado depois em erros), nao derruba
    o run. Ordem estavel (sorted) p/ determinismo."""
    out = []
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.ofx"))):
        try:
            out.append((caminho, parse_ofx(caminho)))
        except Exception:                       # noqa: BLE001 — parse robusto; arquivo ruim vira erro
            out.append((caminho, None))
    return out


def _outra_moeda(moeda) -> bool:
    """So um codigo bem formado diferente de BRL tira a conta do caixa; CURDEF ilegivel segue como esta
    (nao ha como afirmar que e outra moeda, e a saida mostra "?")."""
    return moeda_saida(moeda) not in ("BRL", "?")


def _marca_repetidas(cons: "Consolidado") -> None:
    """Mesma conta (banco, agencia, conta; conta vazia nao agrupa) em mais de um arquivo: o caixa e um so.
    Entra a de data_saldo mais recente; as outras ficam fora ("repetida"). Empate de data com saldos
    diferentes: nenhuma entra ("repetida com saldos diferentes")."""
    grupos: dict = {}
    for c in cons.contas:
        if c.entra_no_caixa and c.conta:
            grupos.setdefault((c.banco, c.agencia, c.conta), []).append(c)
    for membros in grupos.values():
        if len(membros) < 2:
            continue
        recente = max(m.data_saldo or date.min for m in membros)
        empate = [m for m in membros if (m.data_saldo or date.min) == recente]
        conflito = len({m.saldo_final for m in empate}) > 1
        if conflito:
            cons.n_repetidas_conflito += 1
        for m in membros:
            if m is empate[0] and not conflito:
                continue
            m.entra_no_caixa = False
            m.motivo_fora = "repetida com saldos diferentes" if (conflito and m in empate) else "repetida"
            cons.n_repetidas += 1


def consolidar_extratos(parsed: list, saldo_minimo: Decimal | None = None,
                        forcar_conta=None) -> Consolidado:
    """Consolida uma lista de (caminho, ExtratoOFX|None). Funcao PURA (sem rede, sem I/O).

    - cartao (envelope CC) fica FORA do caixa, salvo se o arquivo estiver em forcar_conta.
    - arquivo sem LEDGERBAL nao soma (entra em n_sem_saldo; so transacoes, sem saldo).
    - a posicao e em reais: conta em outra moeda fica fora do caixa (motivo "moeda").
    - a mesma conta em dois arquivos conta uma vez (ver _marca_repetidas).
    - OFX com mais de uma conta fica fora do caixa (motivo "multiconta").
    - total_caixa = soma dos saldos das contas que entram.
    - status: abaixo = total_caixa < saldo_minimo (quando ha minimo).
    """
    forcar = {os.path.basename(x) for x in (forcar_conta or ())}
    cons = Consolidado(saldo_minimo=saldo_minimo)

    for caminho, ext in parsed:
        nome = os.path.basename(caminho)
        if ext is None:
            cons.erros.append(nome)
            continue

        forcado = nome in forcar
        eh_cartao = ext.eh_cartao and not forcado
        # D18: o saldo lido e so o da 1a conta; multiconta vence cartao e saldo e --forcar-conta nao o traz
        multi = ext.n_contas > 1
        entra = (not multi) and (not eh_cartao) and (ext.saldo_final is not None)
        motivo = "" if entra else ("multiconta" if multi else ("cartao" if eh_cartao else "sem saldo"))
        if entra and _outra_moeda(ext.moeda):
            entra, motivo = False, "moeda"

        cons.contas.append(ContaConsolidada(
            arquivo=nome, banco=ext.banco, agencia=ext.agencia, conta=ext.conta,
            tipo_conta=ext.tipo_conta, eh_cartao=ext.eh_cartao, saldo_final=ext.saldo_final,
            data_saldo=ext.data_saldo, n_transacoes=len(ext.transacoes),
            n_contas_no_arquivo=ext.n_contas, entra_no_caixa=entra, motivo_fora=motivo,
            moeda=ext.moeda,
        ))
        if multi:
            cons.n_multi_conta += 1

    _marca_repetidas(cons)

    for c in cons.contas:
        if c.entra_no_caixa:
            cons.total_caixa += c.saldo_final
            cons.n_caixa += 1
            chave = c.banco or "?"
            cons.por_banco[chave] = cons.por_banco.get(chave, Decimal("0")) + c.saldo_final
        elif c.motivo_fora == "cartao":
            cons.n_cartoes += 1
        elif c.motivo_fora == "moeda":
            cons.n_outra_moeda += 1
        elif c.motivo_fora == "sem saldo":
            cons.n_sem_saldo += 1

    if saldo_minimo is not None:
        cons.abaixo = cons.total_caixa < saldo_minimo
        cons.deficit = (saldo_minimo - cons.total_caixa) if cons.abaixo else Decimal("0")
    return cons


def status_texto(cons: Consolidado) -> str:
    if cons.saldo_minimo is None:
        return "SEM MINIMO DEFINIDO"
    return "ABAIXO DO MINIMO" if cons.abaixo else "DENTRO DO MINIMO"


def _mascara_conta(conta) -> str:
    """Mascara o numero de conta p/ tudo que SAI da maquina (resumo.json p/ a IA E Sheet p/ o Google,
    SPEC-06 #4/B1): mantem so os ultimos digitos, o resto vira bullets. Banco + saldo ja identificam a
    conta. So o posicao.csv LOCAL (no disco do analista) guarda o numero cheio."""
    s = str(conta or "").strip()
    if not s:
        return ""
    return "••••" + s[-2:] if len(s) > 2 else "••••"


# Validadores de SAIDA (stdout, resumo.json, Sheet): banco, tipo e moeda vem de tags do arquivo da pessoa
# (BANKID, ACCTTYPE, CURDEF) e podem trazer texto livre. So sai o que casa um vocabulario curto; senao "?".
# Nao mudam o objeto interno (tipo_conta, eh_cartao e a logica de caixa seguem com o valor cru).
_TIPOS_OK = {"CHECKING", "SAVINGS", "MONEYMRKT", "CREDITLINE", "CD", "CREDITCARD"}


def banco_saida(banco) -> str:
    s = str(banco or "").strip()
    return s if re.fullmatch(r"\d{1,5}", s) else "?"


def tipo_saida(tipo) -> str:
    s = str(tipo or "").strip().upper()
    return s if s in _TIPOS_OK else ("conta" if not s else "?")


def moeda_saida(moeda) -> str:
    s = str(moeda or "").strip()
    return s if re.fullmatch(r"[A-Z]{3}", s) else "?"


def _por_banco_saida(cons: Consolidado) -> dict:
    """por_banco com a chave validada; bancos invalidos agrupam sob "?" SOMANDO os saldos."""
    out: dict = {}
    for k, v in cons.por_banco.items():
        kk = banco_saida(k)
        out[kk] = out.get(kk, Decimal("0")) + v
    return {k: str(v) for k, v in sorted(out.items())}


def resumo_agregado(cons: Consolidado) -> dict:
    """Resumo seguro p/ a IA: saldos e totais, NUNCA linha de extrato. O numero de conta vai
    MASCARADO e o nome de arquivo nao sobe (SPEC-06 #4 — o fosso e o dado nao sair da maquina).
    O detalhe cru fica no CSV local (posicao.csv) e, se o analista optar, na Sheet dele (--sheet)."""
    return {
        "total_caixa": str(cons.total_caixa),
        "saldo_minimo": (str(cons.saldo_minimo) if cons.saldo_minimo is not None else None),
        "status": status_texto(cons),
        "deficit": str(cons.deficit),
        "n_contas_no_caixa": cons.n_caixa,
        "n_cartoes_fora": cons.n_cartoes,
        "n_sem_saldo": cons.n_sem_saldo,
        "n_arquivos_multi_conta": cons.n_multi_conta,
        "n_repetidas_fora": cons.n_repetidas,
        "n_repetidas_saldos_diferentes": cons.n_repetidas_conflito,
        "n_outra_moeda_fora": cons.n_outra_moeda,
        "erros_parse": len(cons.erros),
        "por_banco": _por_banco_saida(cons),
        "contas": [
            {
                "banco": banco_saida(c.banco), "conta": _mascara_conta(c.conta),
                "tipo": ("cartao" if c.eh_cartao else tipo_saida(c.tipo_conta)),
                "moeda": moeda_saida(c.moeda),
                "saldo_final": (str(c.saldo_final) if c.saldo_final is not None else None),
                "data_saldo": (str(c.data_saldo) if c.data_saldo else None),
                "n_transacoes": c.n_transacoes,
                "entra_no_caixa": c.entra_no_caixa,
                "motivo_fora": c.motivo_fora,
            }
            for c in cons.contas
        ],
    }
