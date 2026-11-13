"""Achado 9 do Gate 2: rodar de novo na mesma pasta de saida sem excecoes nao deixa o excecoes.csv antigo."""
from __future__ import annotations

from pathlib import Path

import ler_notas

NFE = (Path(__file__).parent / "fixtures" / "nfe_exemplo.xml").read_bytes()


def test_rodada_sem_excecoes_apaga_o_excecoes_csv_da_rodada_anterior(tmp_path):
    ruim, bom, out = tmp_path / "ruim", tmp_path / "bom", tmp_path / "out"
    ruim.mkdir(); bom.mkdir()
    (ruim / "x.xml").write_text("<x/>", encoding="utf-8")
    (bom / "n.xml").write_bytes(NFE)
    assert ler_notas.main(["processar", "--entrada", str(ruim), "--out", str(out)]) == 0
    assert (out / "excecoes.csv").exists()
    assert ler_notas.main(["processar", "--entrada", str(bom), "--out", str(out)]) == 0
    assert not (out / "excecoes.csv").exists()
    assert (out / "carga.csv").exists() and (out / "resumo.json").exists()
