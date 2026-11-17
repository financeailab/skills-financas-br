# -*- coding: utf-8 -*-
"""Teste e2e da fatia de INTEGRACAO: PDF-fixture -> ler()/main() -> CSV/XLSX.

Cobre os 2 emissores (itau/bradesco), a versao "furada" (TOTAL NAO FECHA), o
layout desconhecido (LAYOUT DESCONHECIDO), o generico best-effort (BAIXA
CONFIANCA), o PDF corrompido (erro antifragil) e os exit codes distintos por
veredicto (SPEC-00 §6), alem do modo --lote via CLI."""
from __future__ import annotations

import os
import sys

import gen_faturas_pdf

from conftest import SCRIPTS  # noqa: E402  (dois layouts: monorepo e publico)

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from ler_fatura import ler, main  # noqa: E402

EMISSORES = ["itau", "bradesco"]


def test_ler_todos_formatos_por_emissor(tmp_path):
    for emissor in EMISSORES:
        pdf_path = gen_faturas_pdf.gerar(emissor, str(tmp_path / f"{emissor}.pdf"))
        base = str(tmp_path / f"saida-{emissor}")
        resumo = ler(pdf_path, saida=base, formato="todos")

        assert resumo["emissor"] == emissor
        assert resumo["veredicto"] == "OK"

        esperado = gen_faturas_pdf.esperado(emissor)
        assert resumo["n_lancamentos"] == len(esperado["lancamentos"])
        assert resumo["total_calculado"] == esperado["total_fatura"]

        for ext in ("csv", "xlsx"):
            path = f"{base}.{ext}"
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


def test_ler_furado_reprova_total_nao_fecha_e_exit_2(tmp_path):
    for emissor in EMISSORES:
        pdf_path = gen_faturas_pdf.gerar(emissor, str(tmp_path / f"{emissor}_furado.pdf"), furado=True)
        base = str(tmp_path / f"saida-{emissor}-furado")
        resumo = ler(pdf_path, saida=base, formato="csv")
        assert resumo["veredicto"] == "TOTAL NAO FECHA"

        exit_code = main([pdf_path, "--saida", base + "-cli", "--formato", "csv"])
        assert exit_code == 2


def test_ler_generico_reconhecivel_vira_baixa_confianca_e_exit_4(tmp_path):
    pdf_path = gen_faturas_pdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    base = str(tmp_path / "saida-generico")
    resumo = ler(pdf_path, saida=base, formato="csv")
    assert resumo["veredicto"] == "BAIXA CONFIANCA"
    assert resumo["n_lancamentos"] == 4  # 3 compras + 1 estorno contabil "(37,50)"

    exit_code = main([pdf_path, "--saida", base + "-cli", "--formato", "csv"])
    assert exit_code == 4


def test_ler_ilegivel_vira_layout_desconhecido_e_exit_3(tmp_path):
    pdf_path = gen_faturas_pdf.gerar_generico_ilegivel(str(tmp_path / "ilegivel.pdf"))
    base = str(tmp_path / "saida-ilegivel")
    resumo = ler(pdf_path, saida=base, formato="csv")
    assert resumo["veredicto"] == "LAYOUT DESCONHECIDO"

    exit_code = main([pdf_path, "--saida", base + "-cli", "--formato", "csv"])
    assert exit_code == 3


def test_ler_formato_unico_nao_gera_outros(tmp_path):
    pdf_path = gen_faturas_pdf.gerar("itau", str(tmp_path / "itau.pdf"))
    base = str(tmp_path / "saida-so-csv")
    ler(pdf_path, saida=base, formato="csv")
    assert os.path.exists(f"{base}.csv")
    assert not os.path.exists(f"{base}.xlsx")


def test_ler_emissor_forcado(tmp_path):
    pdf_path = gen_faturas_pdf.gerar("bradesco", str(tmp_path / "bradesco.pdf"))
    base = str(tmp_path / "saida-forcado")
    resumo = ler(pdf_path, saida=base, formato="csv", emissor="bradesco")
    assert resumo["emissor"] == "bradesco"


def test_ler_pdf_corrompido_nao_lanca_e_exit_1(tmp_path):
    pdf_ruim = tmp_path / "corrompido.pdf"
    pdf_ruim.write_bytes(b"isto nao e um pdf de verdade")
    base = str(tmp_path / "saida-corrompido")
    resumo = ler(str(pdf_ruim), saida=base, formato="todos")
    assert resumo["veredicto"] not in ("OK",)
    assert "erro" in resumo

    exit_code = main([str(pdf_ruim), "--saida", base + "-cli", "--formato", "csv"])
    assert exit_code == 1


def test_cli_lote_consolida_e_gera_excecoes(tmp_path):
    pasta = tmp_path / "faturas"
    pasta.mkdir()
    gen_faturas_pdf.gerar("itau", str(pasta / "itau.pdf"))
    gen_faturas_pdf.gerar("bradesco", str(pasta / "bradesco.pdf"))
    gen_faturas_pdf.gerar("itau", str(pasta / "itau_furado.pdf"), furado=True)

    out_csv = tmp_path / "consolidado.csv"
    out_xlsx = tmp_path / "consolidado.xlsx"
    exit_code = main(["--lote", str(pasta), "--csv", str(out_csv), "--xlsx", str(out_xlsx)])

    assert out_csv.exists()
    assert out_xlsx.exists()
    # pior veredicto entre as 3 faturas (2x OK, 1x TOTAL NAO FECHA) -> exit 2
    assert exit_code == 2


def test_cli_lote_sem_csv_nem_xlsx_erro_de_uso(tmp_path, capsys):
    pasta = tmp_path / "faturas_vazia"
    pasta.mkdir()
    import pytest
    with pytest.raises(SystemExit):
        main(["--lote", str(pasta)])
