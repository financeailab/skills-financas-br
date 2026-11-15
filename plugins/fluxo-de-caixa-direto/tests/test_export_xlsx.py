# -*- coding: utf-8 -*-
"""export_xlsx.py: 5 abas na ordem certa (SPEC-00 §7), saldo negativo em
vermelho, CSV 1 por aba e JSON com tudo serializavel."""
import csv
import json

import pytest

import gen_vectors as gv
from categorizador import carregar_dicionario
from ingest_ofx import ingest_extratos
from ingest_erp import ler_titulos
from dfc import montar
from export_xlsx import (
    exportar_xlsx, exportar_csv, exportar_json, montar_estrutura_json,
    NOMES_ABAS, FRASE_HONESTIDADE, XlsxIndisponivel,
)

openpyxl = pytest.importorskip("openpyxl")


def _resultado_gabarito(tmp_path):
    pa = tmp_path / "a.ofx"
    pa.write_text(gv.ofx_conta_a(), encoding="utf-8")
    pb = tmp_path / "b.ofx"
    pb.write_text(gv.ofx_conta_b(), encoding="utf-8")
    res_ofx = ingest_extratos([str(pa), str(pb)])

    pagar_p = tmp_path / "pagar.csv"
    with open(pagar_p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fornecedor", "documento", "vencimento", "valor", "status"])
        w.writeheader()
        w.writerows(gv.titulos_pagar_generico())
    receber_p = tmp_path / "receber.csv"
    with open(receber_p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cliente", "documento", "vencimento", "valor", "status"])
        w.writeheader()
        w.writerows(gv.titulos_receber_generico())
    titulos = (ler_titulos(str(pagar_p), perfil="generico", tipo="pagar")
               + ler_titulos(str(receber_p), perfil="generico", tipo="receber"))

    dic = carregar_dicionario()
    return montar(res_ofx.lancamentos, titulos, res_ofx.contas, gv.DATA_BASE, 13, dic,
                  contas_proprias=gv.CONTAS_PROPRIAS)


def test_workbook_tem_5_abas_na_ordem_certa(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    destino = tmp_path / "fluxo.xlsx"
    exportar_xlsx(resultado, gv.DATA_BASE, str(destino))

    wb = openpyxl.load_workbook(str(destino))
    assert wb.sheetnames == NOMES_ABAS


def test_resumo_saldo_negativo_fica_vermelho(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    destino = tmp_path / "fluxo.xlsx"
    exportar_xlsx(resultado, gv.DATA_BASE, str(destino))

    wb = openpyxl.load_workbook(str(destino))
    ws = wb["Resumo"]
    # semana 1 (linha da tabela = header(5) + 1 + indice da semana) tem saldo negativo
    linha_semana_1 = 5 + 1 + 1
    cell = ws.cell(row=linha_semana_1, column=4)
    assert cell.value < 0
    assert cell.fill.fgColor.rgb == "FFF8D7DA"


def test_resumo_tem_a_frase_de_honestidade(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    destino = tmp_path / "fluxo.xlsx"
    exportar_xlsx(resultado, gv.DATA_BASE, str(destino))

    wb = openpyxl.load_workbook(str(destino))
    ws = wb["Resumo"]
    textos = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    assert any(FRASE_HONESTIDADE in t for t in textos)


def test_titulo_atrasado_fica_destacado_na_aba_titulos(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    destino = tmp_path / "fluxo.xlsx"
    exportar_xlsx(resultado, gv.DATA_BASE, str(destino))

    wb = openpyxl.load_workbook(str(destino))
    ws = wb["Títulos em aberto"]
    achou_atrasado = False
    for row in ws.iter_rows(min_row=2, values_only=False):
        if row[-1].value == "Sim":
            achou_atrasado = True
            assert row[0].fill.fgColor.rgb == "FFFDE8C8"
    assert achou_atrasado


def test_export_csv_grava_1_arquivo_por_aba(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    pasta = tmp_path / "csv"
    caminhos = exportar_csv(resultado, gv.DATA_BASE, str(pasta))

    assert len(caminhos) == 5
    for c in caminhos:
        with open(c, encoding="utf-8-sig") as f:
            linhas = list(csv.reader(f, delimiter=";"))
        assert len(linhas) >= 1  # ao menos o cabecalho

    with open(pasta / "lancamentos.csv", encoding="utf-8-sig") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    assert len(linhas) == 1 + gv.total_transacoes_realizadas()


def test_export_json_serializa_tudo(tmp_path):
    resultado = _resultado_gabarito(tmp_path)
    destino = tmp_path / "fluxo.json"
    exportar_json(resultado, gv.DATA_BASE, str(destino))

    with open(destino, encoding="utf-8") as f:
        estrutura = json.load(f)

    assert estrutura["data_base"] == "2026-07-20"
    assert estrutura["saldo_inicial"] == str(resultado.saldo_inicial)
    assert len(estrutura["lancamentos"]) == gv.total_transacoes_realizadas()
    assert len(estrutura["semanas"]) == 13
    assert estrutura["honestidade"] == FRASE_HONESTIDADE
    assert any(a["tipo"] == "SEMANA_NEGATIVA" for a in estrutura["alertas"])


def test_montar_estrutura_json_e_json_dumpavel_com_o_default(tmp_path):
    """Confere que o serializer default do exportador cobre 100% dos valores
    (json.dumps sem cobertura completa estouraria TypeError)."""
    resultado = _resultado_gabarito(tmp_path)
    estrutura = montar_estrutura_json(resultado, gv.DATA_BASE)

    from export_xlsx import _json_default
    texto = json.dumps(estrutura, default=_json_default)
    assert texto  # nao levantou TypeError
