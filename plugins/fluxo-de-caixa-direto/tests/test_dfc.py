# -*- coding: utf-8 -*-
"""dfc.py: realizado categoria x mes, saldo inicial, projecao de N semanas e
alertas (SPEC-00 §5/§6), com as 7 invariantes da SPEC-00 §8."""
from datetime import date, timedelta
from decimal import Decimal

import gen_vectors as gv
from categorizador import carregar_dicionario, CATEGORIA_NAO_CLASSIFICADO
from ingest_ofx import ingest_extratos
from ingest_erp import ler_titulos
from dfc import (
    indice_semana, categorizar_lancamentos, realizado_por_categoria_mes,
    calcular_saldo_inicial, alerta_dado_velho, alerta_nao_classificado_alto,
    projecao_semanal, montar,
    ALERTA_SEMANA_NEGATIVA, ALERTA_ATRASADO_EM_ABERTO, ALERTA_SALDO_ESTIMADO,
    ALERTA_DADO_VELHO, ALERTA_NAO_CLASSIFICADO_ALTO,
)

DATA_BASE = gv.DATA_BASE  # 2026-07-20, segunda-feira


# --- indice_semana ---

def test_indice_semana_da_propria_data_base_e_0():
    assert indice_semana(DATA_BASE, DATA_BASE) == 0


def test_indice_semana_futuro():
    assert indice_semana(DATA_BASE + timedelta(days=7), DATA_BASE) == 1
    assert indice_semana(DATA_BASE + timedelta(days=21), DATA_BASE) == 3


def test_indice_semana_passado_e_negativo_antes_de_clampar():
    assert indice_semana(DATA_BASE - timedelta(days=1), DATA_BASE) == -1


# --- categorizacao (invariante #1) e realizado (invariante #2) ---

def test_categorizar_lancamentos_nao_perde_nenhum_invariante_1(tmp_path):
    p = tmp_path / "a.ofx"
    p.write_text(gv.ofx_conta_a(), encoding="utf-8")
    res = ingest_extratos([str(p)])
    dic = carregar_dicionario()

    cat = categorizar_lancamentos(res.lancamentos, dic, contas_proprias=gv.CONTAS_PROPRIAS)

    assert len(cat) == len(res.lancamentos)
    soma_entrada = sum((l["valor"] for l in res.lancamentos), Decimal("0.00"))
    soma_saida = sum((l["valor"] for l in cat), Decimal("0.00"))
    assert soma_entrada == soma_saida


def test_realizado_categoria_mes_re_soma_bate_invariante_2():
    lancs = [
        {"data": date(2026, 6, 5), "valor": Decimal("100.00"), "categoria": "Recebimentos"},
        {"data": date(2026, 6, 20), "valor": Decimal("50.00"), "categoria": "Recebimentos"},
        {"data": date(2026, 7, 1), "valor": Decimal("-30.00"), "categoria": "Tarifas Bancárias"},
    ]
    agg = realizado_por_categoria_mes(lancs)
    assert agg[("Recebimentos", "2026-06")] == Decimal("150.00")
    assert agg[("Tarifas Bancárias", "2026-07")] == Decimal("-30.00")
    total_agg = sum(agg.values(), Decimal("0.00"))
    total_lancs = sum((l["valor"] for l in lancs), Decimal("0.00"))
    assert total_agg == total_lancs


# --- saldo inicial (LEDGERBAL mais recente / SALDO_ESTIMADO) ---

def test_calcular_saldo_inicial_soma_ledgerbal_das_2_contas(tmp_path):
    pa = tmp_path / "a.ofx"
    pa.write_text(gv.ofx_conta_a(), encoding="utf-8")
    pb = tmp_path / "b.ofx"
    pb.write_text(gv.ofx_conta_b(), encoding="utf-8")
    res = ingest_extratos([str(pa), str(pb)])

    saldo, alertas = calcular_saldo_inicial(res.contas, res.lancamentos)

    assert saldo == Decimal(gv.SALDO_INICIAL_ESPERADO)
    assert alertas == []


def test_calcular_saldo_inicial_sem_ledgerbal_estima_e_alerta(tmp_path):
    p = tmp_path / "sem_saldo.ofx"
    p.write_text(gv.ofx_sem_ledgerbal(), encoding="utf-8")
    res = ingest_extratos([str(p)])

    saldo, alertas = calcular_saldo_inicial(res.contas, res.lancamentos)

    assert saldo == Decimal("1000.00")  # soma dos lancamentos da conta (estimativa)
    assert len(alertas) == 1
    assert alertas[0]["tipo"] == ALERTA_SALDO_ESTIMADO


# --- DADO_VELHO ---

def test_dado_velho_dispara_quando_dtasof_mais_de_7_dias_antes(tmp_path):
    p = tmp_path / "velho.ofx"
    p.write_text(gv.ofx_dado_velho("20260701"), encoding="utf-8")  # 19 dias antes de 2026-07-20
    res = ingest_extratos([str(p)])

    alertas = alerta_dado_velho(res.contas, DATA_BASE)
    assert any(a["tipo"] == ALERTA_DADO_VELHO for a in alertas)


def test_dado_velho_nao_dispara_dentro_de_7_dias(tmp_path):
    p = tmp_path / "recente.ofx"
    p.write_text(gv.ofx_dado_velho("20260715"), encoding="utf-8")  # 5 dias antes
    res = ingest_extratos([str(p)])

    alertas = alerta_dado_velho(res.contas, DATA_BASE)
    assert alertas == []


# --- NAO_CLASSIFICADO_ALTO ---

def test_nao_classificado_alto_dispara_acima_de_20_por_cento():
    lancs = [
        {"categoria": "Recebimentos"},
        {"categoria": CATEGORIA_NAO_CLASSIFICADO},
        {"categoria": CATEGORIA_NAO_CLASSIFICADO},
    ]
    alertas = alerta_nao_classificado_alto(lancs)
    assert len(alertas) == 1
    assert alertas[0]["tipo"] == ALERTA_NAO_CLASSIFICADO_ALTO


def test_nao_classificado_alto_nao_dispara_no_gabarito_saudavel(tmp_path):
    pa = tmp_path / "a.ofx"
    pa.write_text(gv.ofx_conta_a(), encoding="utf-8")
    pb = tmp_path / "b.ofx"
    pb.write_text(gv.ofx_conta_b(), encoding="utf-8")
    res = ingest_extratos([str(pa), str(pb)])
    dic = carregar_dicionario()
    cat = categorizar_lancamentos(res.lancamentos, dic, contas_proprias=gv.CONTAS_PROPRIAS)

    assert alerta_nao_classificado_alto(cat) == []


# --- projecao semanal + invariantes #3 e #5 ---

def _titulos_do_gabarito(tmp_path):
    import csv
    pagar_p = tmp_path / "pagar.csv"
    receber_p = tmp_path / "receber.csv"
    with open(pagar_p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fornecedor", "documento", "vencimento", "valor", "status"])
        w.writeheader()
        w.writerows(gv.titulos_pagar_generico())
    with open(receber_p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cliente", "documento", "vencimento", "valor", "status"])
        w.writeheader()
        w.writerows(gv.titulos_receber_generico())
    pagar = ler_titulos(str(pagar_p), perfil="generico", tipo="pagar")
    receber = ler_titulos(str(receber_p), perfil="generico", tipo="receber")
    return pagar + receber


def test_titulo_baixado_nunca_entra_na_projecao_invariante_5(tmp_path):
    titulos = _titulos_do_gabarito(tmp_path)
    semanas, titulos_aberto, _alertas = projecao_semanal(Decimal("0.00"), titulos, DATA_BASE, 13)

    docs_em_aberto = {t["documento"] for t in titulos_aberto}
    assert "NF-0999" not in docs_em_aberto   # pago
    assert "NF-R502" not in docs_em_aberto   # recebido
    assert "NF-1001" in docs_em_aberto
    assert "NF-2000" in docs_em_aberto
    assert "NF-R500" in docs_em_aberto
    assert "NF-R501" in docs_em_aberto


def test_titulo_vencido_em_aberto_entra_semana_0_com_flag_atrasado(tmp_path):
    titulos = _titulos_do_gabarito(tmp_path)
    _semanas, titulos_aberto, alertas = projecao_semanal(Decimal("0.00"), titulos, DATA_BASE, 13)

    por_doc = {t["documento"]: t for t in titulos_aberto}
    assert por_doc["NF-1002"]["semana"] == 0
    assert por_doc["NF-1002"]["atrasado"] is True
    assert por_doc["NF-R501"]["semana"] == 0
    assert por_doc["NF-R501"]["atrasado"] is True
    assert por_doc["NF-1001"]["atrasado"] is False

    tipos_alerta = [a["tipo"] for a in alertas]
    assert tipos_alerta.count(ALERTA_ATRASADO_EM_ABERTO) == 2


def test_saldo_projetado_semana_0_e_1_bate_gabarito(tmp_path):
    titulos = _titulos_do_gabarito(tmp_path)
    saldo_inicial = Decimal(gv.SALDO_INICIAL_ESPERADO)

    semanas, _titulos_aberto, alertas = projecao_semanal(saldo_inicial, titulos, DATA_BASE, 13)

    assert semanas[0]["saldo"] == Decimal(gv.SALDO_SEMANA_0_ESPERADO)
    assert semanas[1]["saldo"] == Decimal(gv.SALDO_SEMANA_1_ESPERADO)
    assert any(a["tipo"] == ALERTA_SEMANA_NEGATIVA for a in alertas)


def test_invariante_3_saldo_semana_n_formula_generica(tmp_path):
    titulos = _titulos_do_gabarito(tmp_path)
    saldo_inicial = Decimal(gv.SALDO_INICIAL_ESPERADO)
    semanas, _titulos_aberto, _alertas = projecao_semanal(saldo_inicial, titulos, DATA_BASE, 13)

    acumulado_entradas = Decimal("0.00")
    acumulado_saidas = Decimal("0.00")
    for s in semanas:
        acumulado_entradas += s["entradas"]
        acumulado_saidas += s["saidas"]
        esperado = saldo_inicial + acumulado_entradas - acumulado_saidas
        assert s["saldo"] == esperado, f"semana {s['semana']}"


def test_titulo_fora_do_horizonte_nao_conta_no_rolling_mas_aparece_em_titulos_aberto():
    titulo_distante = [{
        "tipo": "pagar", "contraparte": "Fornecedor Distante", "documento": "NF-9999",
        "vencimento": DATA_BASE + timedelta(weeks=20), "valor": Decimal("999.00"),
        "status_raw": "aberto", "em_aberto": True,
    }]
    semanas, titulos_aberto, _alertas = projecao_semanal(Decimal("1000.00"), titulo_distante, DATA_BASE, 13)

    assert all(s["saidas"] == Decimal("0.00") for s in semanas)
    assert len(titulos_aberto) == 1
    assert titulos_aberto[0]["semana"] >= 13


# --- pipeline completo (montar) ---

def test_montar_pipeline_completo_gabarito(tmp_path):
    pa = tmp_path / "a.ofx"
    pa.write_text(gv.ofx_conta_a(), encoding="utf-8")
    pb = tmp_path / "b.ofx"
    pb.write_text(gv.ofx_conta_b(), encoding="utf-8")
    res = ingest_extratos([str(pa), str(pb)])
    titulos = _titulos_do_gabarito(tmp_path)
    dic = carregar_dicionario()

    out = montar(res.lancamentos, titulos, res.contas, DATA_BASE, 13, dic,
                 contas_proprias=gv.CONTAS_PROPRIAS)

    assert out.saldo_inicial == Decimal(gv.SALDO_INICIAL_ESPERADO)
    assert out.semanas[0]["saldo"] == Decimal(gv.SALDO_SEMANA_0_ESPERADO)
    assert out.semanas[1]["saldo"] == Decimal(gv.SALDO_SEMANA_1_ESPERADO)
    assert len(out.lancamentos) == gv.total_transacoes_realizadas()

    tipos_alerta = {a["tipo"] for a in out.alertas}
    assert ALERTA_SEMANA_NEGATIVA in tipos_alerta
    assert ALERTA_ATRASADO_EM_ABERTO in tipos_alerta

    docs_em_aberto = {t["documento"] for t in out.titulos_em_aberto}
    assert "NF-0999" not in docs_em_aberto
    assert "NF-R502" not in docs_em_aberto
