# -*- coding: utf-8 -*-
"""DFC metodo direto: realizado por categoria (mes) + projecao rolante de N
semanas + alertas (SPEC-00 §5/§6). Consome lancamentos ja ingeridos (ingest_ofx)
e titulos ja ingeridos (ingest_erp); a categorizacao delega pro categorizador.py.

Honestidade fixa (SPEC-00 §5, vai no rodape de toda saida): a projecao assume
titulo pago no vencimento. Nao e conciliacao nem garantia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from categorizador import categorizar, CATEGORIA_NAO_CLASSIFICADO

ZERO = Decimal("0.00")

ALERTA_SEMANA_NEGATIVA = "SEMANA_NEGATIVA"
ALERTA_ATRASADO_EM_ABERTO = "ATRASADO_EM_ABERTO"
ALERTA_SALDO_ESTIMADO = "SALDO_ESTIMADO"
ALERTA_DADO_VELHO = "DADO_VELHO"
ALERTA_NAO_CLASSIFICADO_ALTO = "NAO_CLASSIFICADO_ALTO"

LIMIAR_NAO_CLASSIFICADO_ALTO = Decimal("0.20")
LIMIAR_DADO_VELHO_DIAS = 7


@dataclass
class DFCResult:
    lancamentos: list = field(default_factory=list)            # categorizados
    realizado_categoria_mes: dict = field(default_factory=dict)  # (categoria, 'AAAA-MM') -> Decimal
    saldo_inicial: Decimal = ZERO
    semanas: list = field(default_factory=list)                 # [{semana, entradas, saidas, saldo}]
    titulos_em_aberto: list = field(default_factory=list)       # todos os em aberto, com semana + atrasado
    alertas: list = field(default_factory=list)                 # [{tipo, detalhe}]


def indice_semana(d: date, data_base: date) -> int:
    """Semana 0 = a semana (segunda a domingo) que contem `data_base` (Decisao
    D2 do plano de build). Pode devolver indice negativo p/ datas antes dessa
    semana; quem chama decide se clampa pra 0 (titulo vencido em aberto)."""
    inicio_semana_0 = data_base - timedelta(days=data_base.weekday())
    return (d - inicio_semana_0).days // 7


def categorizar_lancamentos(lancamentos: list[dict], dicionario, contas_proprias=None) -> list[dict]:
    """Aplica o categorizador em cada lancamento. Nao perde nenhum (invariante
    #1, SPEC-00 §8): mesma quantidade e mesma soma de valor na saida."""
    out = []
    for l in lancamentos:
        categoria, regra = categorizar(l["descricao"], dicionario, contas_proprias)
        out.append({**l, "categoria": categoria, "regra_aplicada": regra})
    return out


def realizado_por_categoria_mes(lancamentos_categorizados: list[dict]) -> dict:
    """{(categoria, 'AAAA-MM'): Decimal soma}. Re-somar os valores bate com a
    soma de todos os lancamentos (invariante #2, SPEC-00 §8)."""
    agg: dict = {}
    for l in lancamentos_categorizados:
        chave = (l["categoria"], l["data"].strftime("%Y-%m"))
        agg[chave] = agg.get(chave, ZERO) + l["valor"]
    return agg


def calcular_saldo_inicial(contas: dict, lancamentos: list[dict]) -> tuple[Decimal, list[dict]]:
    """Soma o LEDGERBAL mais recente de cada conta (SPEC-00 §5). Conta sem
    LEDGERBAL: soma dos lancamentos dela como estimativa + alerta
    SALDO_ESTIMADO (nunca falha silenciosamente)."""
    por_conta: dict = {}
    for l in lancamentos:
        por_conta.setdefault(l["conta_id"], []).append(l)

    total = ZERO
    alertas = []
    for conta_id, conta in contas.items():
        if conta.saldo_final is not None:
            total += conta.saldo_final
            continue
        estimado = sum((l["valor"] for l in por_conta.get(conta_id, [])), ZERO)
        total += estimado
        alertas.append({
            "tipo": ALERTA_SALDO_ESTIMADO,
            "detalhe": (f"conta {conta_id} sem saldo final (LEDGERBAL) no OFX; saldo estimado pela "
                        f"soma dos lancamentos ingeridos (R$ {estimado})"),
        })
    return total, alertas


def alerta_dado_velho(contas: dict, data_base: date) -> list[dict]:
    """DTASOF (data do saldo) mais de 7 dias antes da data-base -> extrato pode
    estar desatualizado pra confiar na projecao (SPEC-00 §6)."""
    alertas = []
    for conta_id, conta in contas.items():
        if conta.data_saldo is None:
            continue
        dias = (data_base - conta.data_saldo).days
        if dias > LIMIAR_DADO_VELHO_DIAS:
            alertas.append({
                "tipo": ALERTA_DADO_VELHO,
                "detalhe": f"conta {conta_id}: extrato mais recente e de {conta.data_saldo} ({dias} dias antes da data-base)",
            })
    return alertas


def alerta_nao_classificado_alto(lancamentos_categorizados: list[dict]) -> list[dict]:
    total = len(lancamentos_categorizados)
    if total == 0:
        return []
    sem_categoria = sum(1 for l in lancamentos_categorizados if l["categoria"] == CATEGORIA_NAO_CLASSIFICADO)
    if Decimal(sem_categoria) / Decimal(total) > LIMIAR_NAO_CLASSIFICADO_ALTO:
        pct = sem_categoria * 100 // total
        return [{
            "tipo": ALERTA_NAO_CLASSIFICADO_ALTO,
            "detalhe": (f"{sem_categoria} de {total} lancamentos (~{pct}%) sem categoria; "
                        f"considere expandir o dicionario-categorias.csv"),
        }]
    return []


def projecao_semanal(saldo_inicial: Decimal, titulos: list[dict], data_base: date, semanas: int
                      ) -> tuple[list[dict], list[dict], list[dict]]:
    """Projeta N semanas a partir do saldo inicial. Titulo baixado (em_aberto=False)
    NUNCA entra (invariante #5). Titulo vencido em aberto entra na semana 0 + fica
    marcado `atrasado=True` (SPEC-00 §5). Devolve (semanas, titulos_em_aberto, alertas)."""
    entradas = [ZERO] * semanas
    saidas = [ZERO] * semanas
    titulos_em_aberto = []
    alertas = []

    for t in titulos:
        if not t.get("em_aberto"):
            continue  # invariante #5: baixado nunca entra na projecao
        atrasado = t["vencimento"] < data_base
        idx = max(indice_semana(t["vencimento"], data_base), 0)
        enriquecido = {**t, "semana": idx, "atrasado": atrasado}
        titulos_em_aberto.append(enriquecido)
        if atrasado:
            alertas.append({
                "tipo": ALERTA_ATRASADO_EM_ABERTO,
                "detalhe": (f"{t['tipo']} '{t.get('documento') or '(sem numero)'}' de "
                            f"{t.get('contraparte') or '(sem nome)'} venceu em {t['vencimento']} "
                            f"(R$ {t['valor']}) e segue em aberto"),
            })
        if idx < semanas:
            if t["tipo"] == "receber":
                entradas[idx] += t["valor"]
            else:
                saidas[idx] += t["valor"]
        # titulo em aberto fora do horizonte de projecao: entra em titulos_em_aberto
        # (aba "Titulos em aberto" mostra tudo), mas nao soma no rolling de N semanas.

    saldo = saldo_inicial
    semanas_out = []
    for k in range(semanas):
        saldo = saldo + entradas[k] - saidas[k]
        semanas_out.append({"semana": k, "entradas": entradas[k], "saidas": saidas[k], "saldo": saldo})
        if saldo < 0:
            alertas.append({
                "tipo": ALERTA_SEMANA_NEGATIVA,
                "detalhe": f"semana {k}: saldo projetado R$ {saldo}",
            })

    return semanas_out, titulos_em_aberto, alertas


def montar(lancamentos: list[dict], titulos: list[dict], contas: dict,
           data_base: date, semanas: int, dicionario, contas_proprias=None) -> DFCResult:
    """Orquestra o pipeline completo: categoriza, agrega o realizado, calcula o
    saldo inicial, projeta N semanas e junta todos os alertas."""
    lancs_cat = categorizar_lancamentos(lancamentos, dicionario, contas_proprias)
    realizado = realizado_por_categoria_mes(lancs_cat)
    saldo_ini, alertas_saldo = calcular_saldo_inicial(contas, lancamentos)
    semanas_out, titulos_aberto, alertas_proj = projecao_semanal(saldo_ini, titulos, data_base, semanas)

    alertas = (alertas_saldo + alertas_proj + alerta_dado_velho(contas, data_base)
               + alerta_nao_classificado_alto(lancs_cat))

    return DFCResult(
        lancamentos=lancs_cat,
        realizado_categoria_mes=realizado,
        saldo_inicial=saldo_ini,
        semanas=semanas_out,
        titulos_em_aberto=titulos_aberto,
        alertas=alertas,
    )
