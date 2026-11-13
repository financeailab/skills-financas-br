# -*- coding: utf-8 -*-
"""V4: o corte de 50 por lote deixa de ser mudo (pasta, ZIP e extracoes)."""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import openpyxl
import pytest

import ler_notas
from engine.batch import CAP_LOTE, processar_extracoes, processar_lote, processar_zip
from tests.layout import SCRIPTS

CLI = os.path.join(SCRIPTS, "ler_notas.py")
FIX = Path(__file__).parent / "fixtures"
XML = (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")


def _xml(i):  # nota distinta por indice: copias iguais seriam a mesma nota repetida
    return XML.replace("01234567890123456789012345678901234567890123456789", f"{i:050d}")
EXT = {"classe": "nfse", "campos": {
    "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
    "valor_servicos": {"valor": "5000.00", "rotulo_exato": True},
    "iss_base": {"valor": "5000.00", "rotulo_exato": True},
    "iss_aliquota": {"valor": "5.00", "rotulo_exato": True},
    "iss_valor": {"valor": "250.00", "rotulo_exato": True}}}
AVISO = "ficaram fora: veja o excecoes.csv e rode de novo com o resto"


def _run(args, cwd):
    return subprocess.run([sys.executable, CLI, *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _pasta(tmp_path, n):
    pasta = tmp_path / "notas"
    pasta.mkdir()
    for i in range(n):
        (pasta / f"n{i:03d}.xml").write_text(_xml(i), encoding="utf-8")
    return pasta


def _linhas_fora(out):
    with open(out / "excecoes.csv", encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f, delimiter=";") if "acima do limite de 50" in r["motivo"]]


def _resumo_xlsx(out):
    ws = openpyxl.load_workbook(out / "carga.xlsx")["Resumo"]
    return {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value for r in range(3, 12)}


@pytest.mark.parametrize("n,fora", [(49, 0), (50, 0), (51, 1), (55, 5)])
def test_pasta_corta_e_avisa(tmp_path, n, fora):
    out = tmp_path / "out"
    r = _run(["processar", "--entrada", str(_pasta(tmp_path, n)), "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stderr
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["recebidas"] == n and resumo["fora_do_limite"] == fora
    assert resumo["total"] == min(n, 50) and resumo["falhou"] == 0
    assert list(resumo)[3:6] == ["falhou", "recebidas", "fora_do_limite"]
    assert (AVISO in r.stdout) == (fora > 0)
    if fora:
        assert f"[!] {fora} nota(s) acima do limite de 50 por lote {AVISO}" in r.stdout
        assert [x["arquivo_origem"] for x in _linhas_fora(out)] == [f"n{i:03d}.xml" for i in range(50, n)]
    x = _resumo_xlsx(out)
    assert x["Recebidas"] == n and x["Fora do limite"] == fora


def test_zip_corta_e_avisa(tmp_path):
    z = tmp_path / "lote.zip"
    with zipfile.ZipFile(z, "w") as f:
        for i in range(55):
            f.writestr(f"n{i:03d}.xml", _xml(i))
    out = tmp_path / "out"
    r = _run(["processar", "--entrada", str(z), "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stderr
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert (resumo["recebidas"], resumo["fora_do_limite"], resumo["total"]) == (55, 5, 50)
    assert len(_linhas_fora(out)) == 5 and AVISO in r.stdout
    assert _resumo_xlsx(out)["Fora do limite"] == 5


def test_zip_com_recusados_dentro_do_corte_nao_perde_o_excedente():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bomb.xml", "a" * (3 * 1024 * 1024), compress_type=zipfile.ZIP_DEFLATED)  # razao > 1000
        for i in range(54):
            z.writestr(f"n{i:03d}.xml", _xml(i))
    r = processar_zip(buf.getvalue())
    assert r["resumo"]["recebidas"] == 55 and r["resumo"]["fora_do_limite"] == 5
    assert r["resumo"]["falhou"] == 1 and r["resumo"]["total"] == 49


def test_extracoes_cortam_e_avisam(tmp_path):
    j = tmp_path / "ext.json"
    j.write_text(json.dumps([{"arquivo": f"d{i:03d}.pdf", "extracao": EXT} for i in range(55)]), encoding="utf-8")
    out = tmp_path / "out"
    r = _run(["processar-pdf", "--extracoes", str(j), "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stderr
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert (resumo["recebidas"], resumo["fora_do_limite"], resumo["total"], resumo["falhou"]) == (55, 5, 50, 0)
    assert len(_linhas_fora(out)) == 5 and AVISO in r.stdout


def test_extracoes_50_nao_avisam():
    r = processar_extracoes([(f"d{i}.pdf", EXT) for i in range(50)])
    assert r["resumo"]["fora_do_limite"] == 0 and r["resumo"]["recebidas"] == 50


def test_fora_do_limite_nunca_negativo_e_zero_xml(tmp_path):
    r = processar_lote([])
    assert r["resumo"]["recebidas"] == 0 and r["resumo"]["fora_do_limite"] == 0
    out = tmp_path / "out"
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    p = _run(["processar", "--entrada", str(vazia), "--out", str(out)], tmp_path)
    assert p.returncode == 0, p.stderr
    assert json.loads((out / "resumo.json").read_text(encoding="utf-8"))["total"] == 0


def test_53o_acima_de_100mb_nao_e_aberto(tmp_path, monkeypatch, capsys):
    pasta = _pasta(tmp_path, 55)
    tamanhos = {}
    real = os.path.getsize
    monkeypatch.setattr(ler_notas.os.path, "getsize", lambda p: (tamanhos.setdefault(p, real(p)), 101 * 1024 * 1024 if p.endswith("n052.xml") else real(p))[1])
    rc = ler_notas.main(["processar", "--entrada", str(pasta), "--out", str(tmp_path / "out")])
    assert rc == 0
    resumo = json.loads((tmp_path / "out" / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["fora_do_limite"] == 5 and resumo["falhou"] == 0
    assert not any(p.endswith("n052.xml") for p in tamanhos)  # nem o tamanho foi conferido


def test_3o_acima_de_100mb_vira_excecao_e_o_lote_segue(tmp_path, monkeypatch):
    pasta = _pasta(tmp_path, 5)
    real = os.path.getsize
    monkeypatch.setattr(ler_notas.os.path, "getsize", lambda p: 101 * 1024 * 1024 if p.endswith("n002.xml") else real(p))
    out = tmp_path / "out"
    rc = ler_notas.main(["processar", "--entrada", str(pasta), "--out", str(out)])
    assert rc == 0
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["total"] == 4 and resumo["falhou"] == 1 and resumo["fora_do_limite"] == 0
    with open(out / "excecoes.csv", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    grandes = [ln for ln in linhas if "100 MB" in ln["motivo"]]  # as outras 3 sao a mesma nota repetida
    assert len(grandes) == 1 and grandes[0]["arquivo_origem"] == "n002.xml"


def test_arquivo_unico_acima_do_limite_segue_recusa(tmp_path, monkeypatch, capsys):
    arq = tmp_path / "a.xml"
    arq.write_text(XML, encoding="utf-8")
    monkeypatch.setattr(ler_notas.os.path, "getsize", lambda p: 101 * 1024 * 1024)
    assert ler_notas.main(["processar", "--entrada", str(arq), "--out", str(tmp_path / "o")]) == 2


def test_validar_com_55_e_com_iso_8859_1(tmp_path):
    pasta = _pasta(tmp_path, 55)
    r = _run(["validar", "--entrada", str(pasta)], tmp_path)
    assert r.returncode == 0
    assert "notas reconhecidas: 50" in r.stdout and "fora do limite: 5" in r.stdout
    pasta2 = tmp_path / "p2"
    pasta2.mkdir()
    (pasta2 / "ok.xml").write_text(XML, encoding="utf-8")
    (pasta2 / "latin.xml").write_bytes("<x>açúcar</x>".encode("latin-1"))
    r = _run(["validar", "--entrada", str(pasta2)], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "notas reconhecidas: 1" in r.stdout and "nao reconhecidas: 1" in r.stdout
    assert "fora do limite" not in r.stdout


def test_cap_unico():
    assert ler_notas.CAP_LOTE is CAP_LOTE and CAP_LOTE == 50
