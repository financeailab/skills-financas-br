"""Testes do cheque sem rede: os 13 ensaios negativos do V5 + os plugins publicados reais.

Copia de scripts/d0/test_checar_sem_rede.py do monorepo financeailab. Ajuste de caminho
(registrado no relatorio da Task 4): REPO_ROOT usa parents[1] em vez de parents[2], porque
este arquivo vive em ferramentas/ (um nivel acima da raiz), nao em scripts/d0/ (dois niveis);
e os motores do monorepo (products/trilha-tesouraria/.../motor/scripts) nao existem aqui, entao
o teste descobre os plugins publicados por glob (plugins/*/skills/*/scripts) em vez de uma
lista fixa de dois caminhos do monorepo.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import checar_sem_rede as csr  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SCRIPT = Path(__file__).parent / "checar_sem_rede.py"


def _escrever(tmp_path: Path, nome_arquivo: str, codigo: str, plugin: str = "conciliacao-bancaria") -> Path:
    pasta_scripts = tmp_path / "plugins" / plugin / "skills" / plugin / "scripts"
    pasta_scripts.mkdir(parents=True, exist_ok=True)
    (pasta_scripts / nome_arquivo).write_text(codigo, encoding="utf-8")
    return tmp_path


def _rodar(pasta: Path):
    config = csr.carregar_config()
    achados = []
    for caminho, nome_plugin in csr._encontrar_arquivos(pasta):
        allowlist = csr._allowlist_para_plugin(config, nome_plugin)
        achados.extend(csr.checar_arquivo(caminho, allowlist, config))
    return achados


# Os 13 ensaios negativos do V5 (12 aqui; o 13º, sheets_push.py + socket, tem teste proprio).
CASOS_NEGATIVOS = {
    "import_socket": "import socket\n",
    "from_urllib_import_request": "from urllib import request\n",
    "import_asyncio_com_open_connection": "import asyncio\nasyncio.open_connection('h', 1)\n",
    "from_asyncio_import_open_connection": "from asyncio import open_connection\n",
    "import_ftplib": "import ftplib\n",
    "builtin_import_direto": '__import__("socket")\n',
    "importlib_import_module": 'importlib.import_module("socket")\n',
    "exec_chamada": 'exec("import socket")\n',
    "eval_chamada": 'eval("1")\n',
    "compile_chamada": 'compile("1", "x", "exec")\n',
    "subprocess_run": 'import subprocess\nsubprocess.run(["curl"])\n',
    "os_system": 'os.system("curl x")\n',
}


@pytest.mark.parametrize("nome_caso", sorted(CASOS_NEGATIVOS))
def test_ensaio_negativo_reprova(tmp_path, nome_caso):
    pasta = _escrever(tmp_path, "x.py", CASOS_NEGATIVOS[nome_caso])
    achados = _rodar(pasta)
    assert achados, f"esperava reprovacao para o ensaio: {nome_caso}"


def test_v5_13_import_socket_em_sheets_push_nao_cobre_arquivo_inteiro(tmp_path):
    codigo = (
        "def push_para_sheet():\n"
        "    import gspread\n"
        "    import socket\n"
        "    return gspread, socket\n"
    )
    pasta = _escrever(tmp_path, "sheets_push.py", codigo)
    achados = _rodar(pasta)
    motivos = [motivo for _, motivo in achados]
    assert any("socket" in m for m in motivos)
    assert not any("gspread" in m for m in motivos)


def test_gspread_no_topo_do_sheets_push_reprova(tmp_path):
    """A excecao vale so dentro de push_para_sheet; no topo do arquivo reprova."""
    pasta = _escrever(tmp_path, "sheets_push.py", "import gspread\n")
    assert _rodar(pasta) != []


def test_gspread_em_outra_funcao_do_sheets_push_reprova(tmp_path):
    codigo = "def outra_funcao():\n    import gspread\n    return gspread\n"
    pasta = _escrever(tmp_path, "sheets_push.py", codigo)
    assert _rodar(pasta) != []


def test_controle_gspread_dentro_de_push_para_sheet_passa(tmp_path):
    codigo = "def push_para_sheet():\n    import gspread\n    return gspread\n"
    pasta = _escrever(tmp_path, "sheets_push.py", codigo)
    assert _rodar(pasta) == []


def test_controle_gspread_em_outro_arquivo_reprova(tmp_path):
    pasta = _escrever(tmp_path, "outro.py", "import gspread\n")
    assert _rodar(pasta) != []


def test_plugins_publicados_passam():
    pastas = sorted(REPO_ROOT.glob("plugins/*/skills/*/scripts"))
    assert pastas, f"nenhum plugins/*/skills/*/scripts sob {REPO_ROOT}"
    for pasta in pastas:
        resultado = subprocess.run(
            [PYTHON, str(SCRIPT), str(pasta)],
            capture_output=True,
            text=True,
        )
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr
        assert "sem rede" in resultado.stdout
