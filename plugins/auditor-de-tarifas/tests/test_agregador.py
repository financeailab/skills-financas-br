# -*- coding: utf-8 -*-
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gen_extrato_tarifas import (
    NAO_CLASSIFICADOS_2025,
    TOTAL_IOF_2025,
    TOTAL_TARIFA_2025,
    TOTAL_TARIFA_SEM_FILTRO,
    escreve_fixtures,
)
from scripts.engine.agregador import agregar
from scripts.engine.ingest import ler_extratos


def _carrega_txns(tmp_path):
    ofx_path, csv_path = escreve_fixtures(tmp_path)
    txns, avisos = ler_extratos([ofx_path, csv_path])
    assert avisos == []
    return txns


def test_total_tarifa_ano_bate_ao_centavo_sem_filtro(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path))
    assert resumo.total_tarifa_ano == TOTAL_TARIFA_SEM_FILTRO
    assert resumo.total_tarifa_ano == Decimal("238.80")


def test_total_tarifa_ano_bate_ao_centavo_com_filtro_2025(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.total_tarifa_ano == TOTAL_TARIFA_2025
    assert resumo.total_tarifa_ano == Decimal("213.80")


def test_iof_fica_a_parte_do_total_de_tarifa(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.total_iof_ano == TOTAL_IOF_2025
    assert resumo.total_iof_ano == Decimal("8.32")
    # o IOF nao pode estar embutido no total de tarifa nem em por_tipo
    assert "imposto" not in resumo.por_tipo


def test_operacao_grande_nao_entra_no_total(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path))
    # a TED de 50.000 (operacao real) nao pode aparecer em nenhum lugar do resumo
    assert resumo.total_tarifa_ano < Decimal("1000.00")
    assert sum(resumo.por_banco.values(), Decimal("0")) == resumo.total_tarifa_ano


def test_nao_classificados_pega_o_termo_inventado(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.nao_classificados == NAO_CLASSIFICADOS_2025
    assert resumo.nao_classificados == 1
    assert resumo.por_tipo["outra_tarifa"] == Decimal("4.20")


def test_por_banco_agrega_os_2_bancos(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.por_banco["341"] == Decimal("191.90")
    assert resumo.por_banco["237"] == Decimal("21.90")


def test_por_mes_agrega_janeiro_e_fevereiro(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.por_mes["2025-01"] == Decimal("66.10")
    assert resumo.por_mes["2025-02"] == Decimal("147.70")


def test_veredicto_conferir_quando_ha_nao_classificados(tmp_path):
    resumo = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo.veredicto == "CONFERIR"
    # nao-classificado netado a zero pelo estorno continua pedindo conferencia
    zerado = agregar([_txn("TAR XPTO", "-10.00"), _txn("ESTORNO TAR XPTO", "10.00")])
    assert zerado.total_tarifa_ano == Decimal("0.00")
    assert zerado.veredicto == "CONFERIR"


def test_veredicto_sem_tarifa_encontrada_quando_vazio():
    resumo = agregar([])
    assert resumo.total_tarifa_ano == Decimal("0.00")
    assert resumo.veredicto == "SEM TARIFA ENCONTRADA"
    assert resumo.periodo is None


def test_periodo_cobre_meses_vistos(tmp_path):
    resumo_sem_filtro = agregar(_carrega_txns(tmp_path))
    assert resumo_sem_filtro.periodo == ("2024-12", "2025-02")
    resumo_2025 = agregar(_carrega_txns(tmp_path), ano=2025)
    assert resumo_2025.periodo == ("2025-01", "2025-02")


# --- Bug 2: netar estorno de tarifa (credito = dinheiro de volta) ---

def _txn(descricao, valor, banco="341", d=None):
    from datetime import date
    from scripts.engine.ingest import Txn
    return Txn(data=d or date(2025, 3, 10), descricao=descricao, valor=Decimal(valor), banco=banco)


def test_estorno_total_de_tarifa_zera_o_total():
    # tarifa de -50 (debito) + estorno de +50 (credito) => custo liquido = 0, nao 100
    txns = [
        _txn("TAR MANUTENCAO CESTA", "-50.00"),
        _txn("ESTORNO TAR MANUTENCAO CESTA", "50.00"),
    ]
    resumo = agregar(txns)
    assert resumo.total_tarifa_ano == Decimal("0.00")
    assert resumo.por_banco.get("341") == Decimal("0.00")
    assert resumo.por_mes.get("2025-03") == Decimal("0.00")
    assert resumo.por_tipo.get("manutencao") == Decimal("0.00")


def test_estorno_parcial_de_tarifa_neta_o_liquido():
    # debito -50 + estorno parcial +20 => custo liquido 30
    txns = [
        _txn("TAR BOLETO EMISSAO", "-50.00"),
        _txn("ESTORNO TAR BOLETO EMISSAO", "20.00"),
    ]
    resumo = agregar(txns)
    assert resumo.total_tarifa_ano == Decimal("30.00")
    assert resumo.por_tipo.get("boleto") == Decimal("30.00")


def test_estorno_de_iof_neta_o_iof():
    txns = [
        _txn("IOF OPERACAO CREDITO", "-8.00"),
        _txn("ESTORNO IOF OPERACAO", "8.00"),
    ]
    resumo = agregar(txns)
    assert resumo.total_iof_ano == Decimal("0.00")


def test_debito_puro_de_tarifa_continua_positivo_no_custo():
    # sem estorno, o custo de tarifa e positivo (debito negativo vira custo positivo)
    resumo = agregar([_txn("TAR MANUTENCAO CESTA", "-29.90")])
    assert resumo.total_tarifa_ano == Decimal("29.90")


# --- Bug 4: periodo coberto reflete o extrato inteiro, nao so meses com tarifa ---

def test_periodo_inclui_mes_so_de_operacao():
    from datetime import date
    txns = [
        _txn("TED 5000,00 PAGAMENTO FORNECEDOR", "-5000.00", d=date(2026, 1, 15)),  # operacao, ignorada
        _txn("TAR MANUTENCAO CESTA", "-25.00", d=date(2026, 2, 10)),                 # tarifa
    ]
    resumo = agregar(txns)
    assert resumo.periodo == ("2026-01", "2026-02")


def test_periodo_de_extrato_sem_tarifa_nao_e_none():
    from datetime import date
    txns = [
        _txn("PIX RECEBIDO JOAO", "2500.00", d=date(2026, 3, 5)),   # credito, ignorado
        _txn("TED PAGAMENTO", "-800.00", d=date(2026, 4, 20)),      # operacao, ignorada
    ]
    resumo = agregar(txns)
    assert resumo.total_tarifa_ano == Decimal("0.00")
    assert resumo.veredicto == "SEM TARIFA ENCONTRADA"
    assert resumo.periodo == ("2026-03", "2026-04")
