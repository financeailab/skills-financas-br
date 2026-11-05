# -*- coding: utf-8 -*-
import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gen_extrato_tarifas import escreve_fixtures
from scripts.auditar_tarifas import main


def test_cli_stdout_nunca_imprime_lancamento_individual(tmp_path, capsys):
    escreve_fixtures(tmp_path)
    ret = main([str(tmp_path), "--ano", "2025"])
    assert ret == 0
    saida = capsys.readouterr().out
    # o total tem que aparecer...
    assert "213.80" in saida
    # ...mas nenhuma descricao de lancamento individual pode vazar pro stdout
    assert "FORNECEDOR" not in saida
    assert "JOAO SILVA" not in saida
    assert "50000" not in saida


def test_cli_reporta_total_e_veredicto(tmp_path, capsys):
    escreve_fixtures(tmp_path)
    main([str(tmp_path), "--ano", "2025"])
    saida = capsys.readouterr().out
    assert "213.80" in saida
    assert "8.32" in saida
    assert "CONFERIR" in saida


def test_cli_sem_filtro_ano_soma_tudo(tmp_path, capsys):
    escreve_fixtures(tmp_path)
    main([str(tmp_path)])
    saida = capsys.readouterr().out
    assert "238.80" in saida


def test_cli_saida_grava_csv_local_classificado(tmp_path, capsys):
    escreve_fixtures(tmp_path)
    saida_csv = tmp_path / "classificado.csv"
    main([str(tmp_path), "--ano", "2025", "--saida", str(saida_csv)])
    capsys.readouterr()  # limpa stdout/stderr

    assert saida_csv.exists()
    with open(saida_csv, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    assert linhas  # tem conteudo
    total = sum(Decimal(l["valor"]).copy_abs() for l in linhas if l["tipo"] != "imposto")
    assert total == Decimal("213.80")
    # a operacao real (TED 50000) nao pode estar no CSV classificado
    assert not any("FORNECEDOR" in l["descricao"] for l in linhas)


def test_cli_arquivo_inexistente_nao_derruba(tmp_path, capsys):
    ret = main([str(tmp_path / "nao_existe.ofx")])
    assert ret == 0
    err = capsys.readouterr().err
    assert "aviso" in err


def test_cli_rerun_com_saida_no_dir_nao_duplica(tmp_path, capsys):
    # Bug 6: --saida grava o CSV classificado no proprio dir de entrada;
    # um re-run nao pode re-ingerir esse arquivo e dobrar o total.
    escreve_fixtures(tmp_path)
    saida = tmp_path / "classificado.csv"
    main([str(tmp_path), "--ano", "2025", "--saida", str(saida)])
    capsys.readouterr()
    assert saida.exists()  # a saida ficou dentro do dir de entrada

    # 2a passada: o classificado ja existe no dir; o total deve seguir 213.80
    main([str(tmp_path), "--ano", "2025"])
    out = capsys.readouterr().out
    assert "213.80" in out
    assert "427.60" not in out  # nao duplicou

    # --saida nunca pode sobrescrever um extrato de entrada (arquivo ou achado na pasta)
    ofx_path, _ = escreve_fixtures(tmp_path)
    antes = Path(ofx_path).read_bytes()
    assert main([str(ofx_path), "--saida", str(ofx_path)]) == 2
    assert main([str(tmp_path), "--saida", str(ofx_path)]) == 2
    assert Path(ofx_path).read_bytes() == antes
