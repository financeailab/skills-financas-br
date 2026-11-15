# -*- coding: utf-8 -*-
"""fluxo_caixa.py: CLI e2e (SPEC-00 §1 e invariante #7 da §8). Exit 0 com
fixture completa, exit 2 erro de entrada, exit 3 pasta vazia."""
import csv
import os

import pytest

import gen_vectors as gv
from fluxo_caixa import main


def _monta_pasta_extratos(tmp_path, nome="extratos"):
    pasta = tmp_path / nome
    pasta.mkdir()
    (pasta / "conta_a.ofx").write_text(gv.ofx_conta_a(), encoding="utf-8")
    (pasta / "conta_b.ofx").write_text(gv.ofx_conta_b(), encoding="utf-8")
    return pasta


def _escreve_titulos(tmp_path):
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
    return str(pagar_p), str(receber_p)


def test_e2e_fixture_completa_exit_0(tmp_path, capsys):
    pytest.importorskip("openpyxl")
    pasta = _monta_pasta_extratos(tmp_path)
    pagar, receber = _escreve_titulos(tmp_path)
    saida = tmp_path / "saida"

    rc = main([
        "--extratos", str(pasta),
        "--pagar", pagar, "--receber", receber,
        "--data-base", "2026-07-20",
        "--saida", str(saida),
    ])

    assert rc == 0
    assert (saida / "fluxo-de-caixa.xlsx").exists()
    out = capsys.readouterr().out
    assert "FLUXO DE CAIXA DIRETO" in out
    assert "semana(s) com saldo projetado negativo" in out


def test_extrato_inexistente_exit_2(tmp_path, capsys):
    rc = main(["--extratos", str(tmp_path / "nao-existe.ofx"), "--saida", str(tmp_path / "saida")])
    assert rc == 2
    assert "ERRO" in capsys.readouterr().out


def test_pasta_extratos_vazia_exit_3(tmp_path, capsys):
    pasta_vazia = tmp_path / "vazia"
    pasta_vazia.mkdir()

    rc = main(["--extratos", str(pasta_vazia), "--saida", str(tmp_path / "saida")])

    assert rc == 3
    assert "ERRO" in capsys.readouterr().out


def test_sem_pagar_receber_roda_so_realizado_exit_0(tmp_path, capsys):
    pytest.importorskip("openpyxl")
    pasta = _monta_pasta_extratos(tmp_path)
    saida = tmp_path / "saida"

    rc = main(["--extratos", str(pasta), "--saida", str(saida)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "projecao fica vazia" in out or "projecao: vazia" in out
    # sem titulo nao ha projecao (achado do Gate 2): nenhuma semana inventada, nenhum SEMANA_NEGATIVA
    import json
    assert main(["--extratos", str(pasta), "--json", "--saida", str(saida)]) == 0
    dados = json.loads((saida / "fluxo-de-caixa.json").read_text(encoding="utf-8"))
    assert dados["semanas"] == []
    assert "SEMANA_NEGATIVA" not in {a["tipo"] for a in dados["alertas"]}


def test_arquivo_pagar_com_coluna_faltando_exit_2(tmp_path, capsys):
    pasta = _monta_pasta_extratos(tmp_path)
    pagar_ruim = tmp_path / "pagar_ruim.csv"
    with open(pagar_ruim, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fornecedor", "valor"])  # falta vencimento
        w.writeheader()
        w.writerow({"fornecedor": "ACME", "valor": "10,00"})

    rc = main(["--extratos", str(pasta), "--pagar", str(pagar_ruim), "--saida", str(tmp_path / "saida")])

    assert rc == 2
    assert "ERRO" in capsys.readouterr().out


def test_data_base_invalida_exit_2(tmp_path, capsys):
    pasta = _monta_pasta_extratos(tmp_path)
    rc = main(["--extratos", str(pasta), "--data-base", "31-13-2026", "--saida", str(tmp_path / "saida")])
    assert rc == 2
    assert "ERRO" in capsys.readouterr().out


def test_contas_proprias_arquivo_inexistente_exit_2(tmp_path, capsys):
    pasta = _monta_pasta_extratos(tmp_path)
    rc = main(["--extratos", str(pasta), "--contas-proprias", str(tmp_path / "nao-existe.txt"),
               "--saida", str(tmp_path / "saida")])
    assert rc == 2
    assert "ERRO" in capsys.readouterr().out


def test_gera_csv_e_json_quando_pedido(tmp_path):
    pasta = _monta_pasta_extratos(tmp_path)
    pagar, receber = _escreve_titulos(tmp_path)
    saida = tmp_path / "saida"

    rc = main([
        "--extratos", str(pasta), "--pagar", pagar, "--receber", receber,
        "--data-base", "2026-07-20", "--saida", str(saida), "--csv", "--json",
    ])

    assert rc == 0
    assert (saida / "csv" / "alertas.csv").exists()
    assert (saida / "fluxo-de-caixa.json").exists()


def test_perfil_omie_em_arquivo_generico_falta_coluna_exit_2(tmp_path, capsys):
    pasta = _monta_pasta_extratos(tmp_path)
    pagar, _receber = _escreve_titulos(tmp_path)  # colunas do perfil generico

    rc = main(["--extratos", str(pasta), "--pagar", pagar, "--perfil", "omie",
               "--saida", str(tmp_path / "saida")])

    assert rc == 2
    assert "ERRO" in capsys.readouterr().out


def test_perfil_invalido_e_rejeitado_pelo_argparse(tmp_path):
    pasta = _monta_pasta_extratos(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["--extratos", str(pasta), "--pagar", "qualquer.csv", "--perfil", "sap-magico"])
    assert exc.value.code == 2
