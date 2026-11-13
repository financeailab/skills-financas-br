import json
import os
import subprocess
import sys

from tests.layout import SCRIPTS
CLI = os.path.join(SCRIPTS, "ler_notas.py")

NFSE = """<?xml version="1.0"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="X">
<nNFSe>1</nNFSe><emit><CNPJ>11222333000181</CNPJ><xNome>Forn</xNome></emit>
<vServ>1000.00</vServ><vBC>1000.00</vBC><pAliqAplic>5.00</pAliqAplic><vISSQN>50.00</vISSQN>
<tpRetISSQN>1</tpRetISSQN><dhEmi>2026-03-15T10:00:00-03:00</dhEmi></infNFSe></NFSe>"""


def _run(args, cwd):
    return subprocess.run([sys.executable, CLI, *args], cwd=cwd, capture_output=True, text=True)


def test_validar_reconhece_familia(tmp_path):
    f = tmp_path / "nota.xml"
    f.write_text(NFSE, encoding="utf-8")
    r = _run(["validar", "--entrada", str(f)], tmp_path)
    assert r.returncode == 0
    assert "nfse_nacional" in r.stdout.lower()


def test_processar_gera_carga_resumo_excecoes(tmp_path):
    f = tmp_path / "nota.xml"
    f.write_text(NFSE, encoding="utf-8")
    out = tmp_path / "resultado"
    r = _run(["processar", "--entrada", str(f), "--perfil", "generico", "--out", str(out)], tmp_path)
    assert r.returncode == 0
    assert (out / "carga.csv").exists()
    assert (out / "resumo.json").exists()
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["total"] == 1
