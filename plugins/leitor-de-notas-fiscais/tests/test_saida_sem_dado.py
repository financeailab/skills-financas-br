# -*- coding: utf-8 -*-
"""Canario de saida sem dado: nada do arquivo da pessoa (nome, xNome, campo) chega ao stdout,
ao stderr nem ao resumo.json. O texto fica so nos arquivos locais (carga/excecoes)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile

import pytest

import ler_notas
from tests.layout import SCRIPTS

CLI = os.path.join(SCRIPTS, "ler_notas.py")
S = "SENTINELA"

NFSE = f"""<?xml version="1.0"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="X">
<nNFSe>1</nNFSe><emit><CNPJ>11222333000181</CNPJ><xNome>{S}</xNome></emit>
<vServ>1000.00</vServ><vBC>1000.00</vBC><pAliqAplic>5.00</pAliqAplic><vISSQN>50.00</vISSQN>
<tpRetISSQN>1</tpRetISSQN><dhEmi>2026-03-15T10:00:00-03:00</dhEmi></infNFSe></NFSe>"""


def _run(args, cwd):
    return subprocess.run([sys.executable, CLI, *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _limpo(r, out=None):
    assert S not in r.stdout, r.stdout
    assert S not in r.stderr, r.stderr
    if out is not None and (out / "resumo.json").exists():
        assert S not in (out / "resumo.json").read_text(encoding="utf-8")


def _tres_comandos(tmp_path, entrada, extracoes):
    out = tmp_path / "out"
    rs = [_run(["validar", "--entrada", str(entrada)], tmp_path),
          _run(["processar", "--entrada", str(entrada), "--out", str(out)], tmp_path),
          _run(["processar-pdf", "--extracoes", str(extracoes), "--out", str(out / "pdf")], tmp_path)]
    for r in rs:
        _limpo(r, out)
    return rs


def test_sentinela_em_nome_de_arquivo_xnome_e_campo_invalido(tmp_path):
    pasta = tmp_path / "notas"
    pasta.mkdir()
    (pasta / f"{S}_ok.xml").write_text(NFSE, encoding="utf-8")
    (pasta / f"{S}_lixo.xml").write_text(f"<x>{S}</x>", encoding="utf-8")
    (pasta / f"{S}_latin1.xml").write_bytes(f"<x>{S} \xe7</x>".encode("latin-1"))
    ext = tmp_path / "ext.json"
    ext.write_text(json.dumps([
        {"arquivo": f"{S}.pdf", "extracao": {"classe": "nfse", "campos": {
            "emitente_nome": {"valor": S, "rotulo_exato": True},
            "valor_servicos": {"valor": S, "rotulo_exato": True},
            "iss_valor": {"valor": S, "rotulo_exato": False}}}},
        {"arquivo": f"{S}2.pdf", "extracao": {"classe": S, "campos": {}}},
    ]), encoding="utf-8")
    rs = _tres_comandos(tmp_path, pasta, ext)
    assert [r.returncode for r in rs] == [0, 0, 0]
    # o texto existe so no arquivo local
    assert S in (tmp_path / "out" / "carga.csv").read_text(encoding="utf-8-sig")
    assert "nao reconhecidas: 2" in rs[0].stdout
    assert ".xml" not in rs[0].stdout


def test_pasta_com_diretorio_chamado_xml_e_ignorada(tmp_path):
    pasta = tmp_path / "notas"
    (pasta / f"{S}.xml").mkdir(parents=True)
    ext = tmp_path / "ext.json"
    ext.write_text("[]", encoding="utf-8")
    rs = _tres_comandos(tmp_path, pasta, ext)
    assert [r.returncode for r in rs[:2]] == [0, 0]  # diretorio nao e nota: o os.walk so lista arquivos


def test_zip_que_nao_e_zip(tmp_path):
    z = tmp_path / f"{S}.zip"
    z.write_text(f"{S} nao e zip", encoding="utf-8")
    ext = tmp_path / "ext.json"
    ext.write_text("[]", encoding="utf-8")
    r = _run(["processar", "--entrada", str(z), "--out", str(tmp_path / "o")], tmp_path)
    _limpo(r)
    assert r.returncode == 2 and "[erro] ZIP ilegível" in r.stderr
    # caminho que nao existe (com o canario no nome): texto fixo, sem repetir o caminho
    r = _run(["validar", "--entrada", str(tmp_path / f"{S}-nao-existe")], tmp_path)
    _limpo(r)
    assert r.returncode == 2 and "[erro] caminho de entrada não encontrado" in r.stderr


def test_zip_valido_com_sentinela_no_nome(tmp_path):
    z = tmp_path / "ok.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr(f"{S}.xml", NFSE)
        f.writestr(f"{S}2.xml", f"<x>{S}</x>")
    out = tmp_path / "o"
    r = _run(["processar", "--entrada", str(z), "--out", str(out)], tmp_path)
    _limpo(r, out)
    assert r.returncode == 0


def test_json_ilegivel_e_nao_utf8(tmp_path):
    j = tmp_path / f"{S}.json"
    j.write_text(f"{{{S}", encoding="utf-8")
    r = _run(["processar-pdf", "--extracoes", str(j), "--out", str(tmp_path / "o")], tmp_path)
    _limpo(r)
    assert r.returncode == 2 and "[erro] JSON de extrações ilegível" in r.stderr
    j.write_bytes(f"[\"{S}\xe7\"]".encode("latin-1"))
    r = _run(["processar-pdf", "--extracoes", str(j), "--out", str(tmp_path / "o")], tmp_path)
    _limpo(r)
    assert r.returncode == 2 and "[erro] arquivo não está em UTF-8" in r.stderr


def test_json_de_formato_inesperado_cai_no_template(tmp_path):
    j = tmp_path / "ext.json"
    j.write_text(f'["{S}"]', encoding="utf-8")
    r = _run(["processar-pdf", "--extracoes", str(j), "--out", str(tmp_path / "o")], tmp_path)
    _limpo(r)
    assert r.returncode == 2 and "erro inesperado" in r.stderr


@pytest.mark.parametrize("cmd", ["validar", "processar", "processar-pdf"])
def test_arquivo_grande_recusado_sem_nome(tmp_path, monkeypatch, capsys, cmd):
    monkeypatch.setattr(ler_notas, "MAX_FILE_SIZE", 10)
    arq = tmp_path / f"{S}.xml"
    arq.write_text(NFSE, encoding="utf-8")
    flag = "--extracoes" if cmd == "processar-pdf" else "--entrada"
    rc = ler_notas.main([cmd, flag, str(arq)] + ([] if cmd == "validar" else ["--out", str(tmp_path / "o")]))
    cap = capsys.readouterr()
    assert rc == 2
    assert S not in cap.out and S not in cap.err
    assert "[erro] arquivo recusado" in cap.err
