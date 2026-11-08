"""Testes do cheque saida sem dado (checar_saida_sem_dado.py).

Arquivo identico em scripts/d0/ (monorepo financeailab) e em ferramentas/ (repo publico):
so usa o script ao lado e pastas temporarias.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "checar_saida_sem_dado.py"
_spec = importlib.util.spec_from_file_location("checar_saida_sem_dado", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
TEMPLATE = _mod._TEMPLATE_MAIN


def _rodar(pasta: Path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(pasta)], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def _motor(tmp_path: Path, codigo: str, nome: str = "motor.py") -> Path:
    pasta = tmp_path / "plugins" / "x" / "skills" / "x" / "scripts"
    pasta.mkdir(parents=True)
    (pasta / nome).write_text(textwrap.dedent(codigo), encoding="utf-8")
    return tmp_path / "plugins"


def _em_def(src: str) -> str:
    """Trecho dentro de uma funcao (o topo do modulo so define, R3): a linha N do trecho vira N+1."""
    return "def f0():\n" + textwrap.indent(src, "    ")


REPROVA_R1 = {
    "print": "try:\n    f()\nexcept ValueError as e:\n    print(e)\n",
    "fstring": "try:\n    f()\nexcept ValueError as e:\n    avisos.append(f'linha 3: {e}')\n",
    "str": "try:\n    f()\nexcept ValueError as e:\n    x = str(e)\n",
    "repr": "try:\n    f()\nexcept ValueError as e:\n    x = repr(e)\n",
    "atribuicao": "try:\n    f()\nexcept ValueError as e:\n    guardada = e\n",
    "args": "try:\n    f()\nexcept ValueError as e:\n    x = e.args\n",
    "helper": "try:\n    f()\nexcept ValueError as e:\n    avisar(e)\n",
    "outro_nome": "try:\n    f()\nexcept (KeyError, ValueError) as err:\n    print('falhou', err, file=sys.stderr)\n",
    "system_exit": "try:\n    f()\nexcept ValueError as e:\n    raise SystemExit(f'erro: {e}')\n",
    "sys_exit": "try:\n    f()\nexcept ValueError as e:\n    sys.exit(str(e))\n",
    "logging_arg": "try:\n    f()\nexcept ValueError as e:\n    logging.error('falhou %s', e)\n",
    "except_star": "try:\n    f()\nexcept* ValueError as eg:\n    print(eg)\n",
}


@pytest.mark.parametrize("caso", sorted(REPROVA_R1))
def test_r1_reprova_texto_da_excecao(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, REPROVA_R1[caso]))
    assert codigo == 1, saida
    assert "motor.py:4: R1 texto da excecao" in saida


PASSA_R1 = {
    "raise_nome": "try:\n    f()\nexcept ValueError as e:\n    raise e\n",
    "raise_from": "try:\n    f()\nexcept ValueError as e:\n    raise RuntimeError('x') from e\n",
    "raise_com_texto": "try:\n    f()\nexcept ValueError as e:\n    raise ValueError(f'linha 3: {e}') from e\n",
    "isinstance": "try:\n    f()\nexcept Exception as e:\n    ok = isinstance(e, ValueError)\n",
    "tipo": "try:\n    f()\nexcept Exception as e:\n    print(type(e).__name__)\n",
    "classe": "try:\n    f()\nexcept Exception as e:\n    print(e.__class__.__name__)\n",
    "oserror": "try:\n    f()\nexcept OSError as e:\n    print(e.strerror, e.errno)\n",
    "sem_nome": "try:\n    f()\nexcept ValueError:\n    print('linha 3 invalida')\n",
    "exit_constante": "import sys\nsys.exit('uso: motor.py <arquivo>')\nraise SystemExit(2)\n",
}


@pytest.mark.parametrize("caso", sorted(PASSA_R1))
def test_r1_passa_uso_permitido(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, _em_def(PASSA_R1[caso])))
    assert codigo == 0, saida


@pytest.mark.parametrize("arg", ["f'erro {valor}'", "'erro %s' % valor", "'erro ' + valor", "'erro {}'.format(valor)", "str(valor)"])
def test_r1_reprova_system_exit_com_texto_formatado_fora_do_except(tmp_path, arg):
    for i, chamada in enumerate((f"sys.exit({arg})", f"raise SystemExit({arg})")):
        pasta = _motor(tmp_path / f"c{i}", f"import sys\nvalor = ler()\n{chamada}\n")
        codigo, saida = _rodar(pasta)
        assert codigo == 1, saida
        assert "motor.py:3: R1 SystemExit com texto formatado" in saida


REPROVA_R2 = {
    "print_exc": "import traceback\ntraceback.print_exc()\n",
    "alias": "import traceback as tb\ntb.format_exc()\n",
    "from_import": "from traceback import format_exc\n",
    "logging_exception": "import logging\nlogging.exception('falhou')\n",
    "exc_info": "import logging\nlogging.error('falhou', exc_info=True)\n",
    "sys_exception": "import sys\ntry:\n    f()\nexcept ValueError:\n    print(sys.exception())\n",
    "sys_exc_info": "import sys\ntry:\n    f()\nexcept ValueError:\n    print(sys.exc_info()[1])\n",
    "from_sys": "from sys import exc_info\n",
    # ponytail-review do fechar: .exception em logger de variavel ou atributo e sys com alias
    "logger_de_variavel": "import logging\n_L = logging.getLogger('x')\n" + _em_def("_L.exception('falhou')\n"),
    "logger_de_atributo": "class C:\n    def f(self):\n        self.log.exception('falhou')\n",
    "sys_com_alias": "import sys as s\n" + _em_def("print(s.exc_info()[1])\n"),
    "threading": "import threading\n",
    "from_threading": "from threading import Thread\n",
    "thread_baixo": "import _thread\n",
    "atexit": "import atexit\n",
    "multiprocessing": "from multiprocessing import Pool\n",
}


@pytest.mark.parametrize("caso", sorted(REPROVA_R2))
def test_r2_reprova_excecao_inteira(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, REPROVA_R2[caso]))
    assert codigo == 1, saida
    assert ": R2 " in saida


def test_r2_nao_tem_escape(tmp_path):
    src = "import traceback\n" + _em_def("traceback.print_exc()  # saida-ok: tentativa\n")
    codigo, saida = _rodar(_motor(tmp_path, src))
    assert codigo == 1 and "motor.py:3: R2 " in saida


REPROVA_R3 = {
    "sem_try": 'import sys\nif __name__ == "__main__":\n    sys.exit(main())\n',
    "try_estreito": 'if __name__ == "__main__":\n    try:\n        main()\n    except ValueError:\n        raise SystemExit(2)\n',
    "chamada_fora": 'if __name__ == "__main__":\n    configurar()\n    try:\n        main()\n    except Exception:\n        raise SystemExit(2)\n',
    "re_levanta": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        raise\n',
    "re_levanta_nome": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception as e:\n        raise e\n',
    "sem_saida": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        print("erro")\n',
    "saida_com_texto": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        raise SystemExit("erro")\n',
    "outra_chamada_no_handler": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        registrar()\n        raise SystemExit(2)\n',
    "finally_com_chamada": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        raise SystemExit(2)\n    finally:\n        fechar()\n',
    "else_com_chamada": 'if __name__ == "__main__":\n    try:\n        x = 1\n    except Exception:\n        raise SystemExit(2)\n    else:\n        main()\n',
    "estreito_re_levanta_antes": 'if __name__ == "__main__":\n    try:\n        main()\n    except ValueError:\n        raise\n    except Exception:\n        raise SystemExit(2)\n',
    "print_com_chamada": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        print(mensagem())\n        raise SystemExit(2)\n',
    "print_com_variavel": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        print(msg)\n        raise SystemExit(2)\n',
    "print_com_excecao": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception as e:\n        print(f"erro {e!r}")\n        raise SystemExit(2)\n',
    "print_arquivo_qualquer": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        print("erro", file=log)\n        raise SystemExit(2)\n',
    "saida_encadeada": 'if __name__ == "__main__":\n    try:\n        main()\n    except Exception as e:\n        raise SystemExit(2) from e\n',
    # a forma "except Exception + print do tipo + SystemExit(2)" vaza (Gate 1A passe 3): so o template passa
    "forma_terminal_antiga": 'import sys\nif __name__ == "__main__":\n    try:\n        raise SystemExit(main())\n    except Exception as e:\n        print(f"erro ({type(e).__name__})", file=sys.stderr)\n        raise SystemExit(2)\n',
    "comparacao_invertida": 'if "__main__" == __name__:\n    main()\n',
    "main_solto": "def main():\n    return 0\n\nmain()\n",
    "exit_main_solto": "import sys\ndef main():\n    return 0\n\nsys.exit(main())\n",
    "name_in_tupla": 'def executar():\n    pass\n\nif __name__ in ("__main__",):\n    executar()\n',
}


@pytest.mark.parametrize("caso", sorted(REPROVA_R3))
def test_r3_reprova_entrada_fora_do_template(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, REPROVA_R3[caso]))
    assert codigo == 1, saida
    assert ": R3 ponto de entrada" in saida


def _com_template(antes: str = "def main():\n    return 0\n", depois: str = "", bloco: str | None = None) -> str:
    return antes + (TEMPLATE if bloco is None else bloco) + depois


def test_r3_passa_com_template(tmp_path):
    codigo, saida = _rodar(_motor(tmp_path, _com_template()))
    assert codigo == 0, saida
    assert "0 escape(s)" in saida  # o `_e.code` do template nao vira R1 nem escape


def test_r3_passa_com_comentario_e_linha_em_branco_no_template(tmp_path):
    bloco = TEMPLATE.replace("    _codigo = 2\n", "    # o template e literal\n\n    _codigo = 2  # padrao\n")
    assert _rodar(_motor(tmp_path, _com_template(bloco=bloco)))[0] == 0


REPROVA_TEMPLATE = {
    "nao_e_o_ultimo": dict(depois="\nx = 1\n"),
    "dentro_de_try": dict(bloco="try:\n" + textwrap.indent(TEMPLATE, "    ") + "except BaseException:\n    raise ValueError('x')\n"),
    "print_no_lugar_do_write": dict(bloco=TEMPLATE.replace("_sys.stderr.write(", "print(")),
    "saida_com_sys_exit": dict(bloco=TEMPLATE.replace("raise SystemExit(_codigo", "_sys.exit(_codigo")),
    "except_estreito": dict(bloco=TEMPLATE.replace("except BaseException:\n        try", "except Exception:\n        try")),
    "duas_entradas": dict(antes="def main():\n    return 0\n" + TEMPLATE),
    "chamada_extra_antes": dict(antes="def main():\n    return 0\n\nmain()\n"),
}


@pytest.mark.parametrize("caso", sorted(REPROVA_TEMPLATE))
def test_r3_reprova_template_alterado(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, _com_template(**REPROVA_TEMPLATE[caso])))
    assert codigo == 1, saida
    assert ": R3 ponto de entrada" in saida


# Topo do modulo: fora do template so definicao (Gate 1A passe 4: codigo no topo roda antes do template).
REPROVA_TOPO = {
    "chamada": "valor = 'x'\nint(valor)\n",
    "raise": "mensagem = 'x'\nraise SystemExit(mensagem)\n",
    "for": "for x in []:\n    pass\n",
    "with": "with open('a') as f:\n    pass\n",
    "try_com_chamada": "try:\n    configurar()\nexcept ImportError:\n    pass\n",
    "try_com_finally": "try:\n    import x\nfinally:\n    pass\n",
    "if_com_chamada_no_corpo": "if True:\n    configurar()\n",
    "corpo_de_classe": "class Config:\n    int('7')\n",  # Gate 1B passe 1: o corpo da classe roda na definicao
}


@pytest.mark.parametrize("caso", sorted(REPROVA_TOPO))
def test_r3_reprova_execucao_no_topo(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, _com_template(antes=REPROVA_TOPO[caso] + "def main():\n    return 0\n")))
    assert codigo == 1, saida
    assert "motor.py:" in saida and ": R3 execucao no topo" in saida


PASSA_TOPO = {
    "docstring": '"""Motor."""\n',
    "sys_path": "import sys\nsys.path.insert(0, 'x')\n",
    "if_sys_path": "import sys\nif str('x') not in sys.path:\n    sys.path.insert(0, 'x')\n",
    "import_opcional": "try:\n    import pdfplumber\nexcept ImportError:\n    pdfplumber = None\n",
    "type_checking": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pathlib import Path\n",
    "atribuicoes": "import re\nPADRAO = re.compile('x')\nN: int = 1\n",
    "classe_que_so_define": "class C:\n    '''doc'''\n    N = 1\n\n    def f(self):\n        return 1\n",
}


@pytest.mark.parametrize("caso", sorted(PASSA_TOPO))
def test_r3_passa_topo_que_so_define(tmp_path, caso):
    codigo, saida = _rodar(_motor(tmp_path, _com_template(antes=PASSA_TOPO[caso] + "def main():\n    return 0\n")))
    assert codigo == 0, saida


def test_r3_script_auxiliar_sem_template_reprova(tmp_path):
    pasta = _motor(tmp_path, _com_template())
    (pasta / "x" / "skills" / "x" / "scripts" / "lote.py").write_text("import engine\nengine.executar()\n", encoding="utf-8")
    codigo, saida = _rodar(pasta)
    assert codigo == 1 and "lote.py:2: R3 execucao no topo" in saida


@pytest.mark.parametrize("antes", [
    "n = int('7')\n",
    "if int('7'):\n    pass\n",
    "def g(x=int('7')):\n    return x\n",
    "import functools\n@functools.lru_cache(maxsize=int('7'))\ndef g():\n    return 1\n",
    "class C:\n    N = int('7')\n",
], ids=["atribuicao", "teste_de_if", "default", "decorador", "atribuicao_de_classe"])
def test_limite_expressao_avaliada_na_definicao_passa(tmp_path, antes):
    # limite declarado (spec D2): a expressao roda antes do template; o teste-canario do motor cobre
    assert _rodar(_motor(tmp_path, _com_template(antes=antes + "def main():\n    return 0\n")))[0] == 0


# Prova do template: cada caso roda o motor em subprocesso; nada de CANARIO nem traceback na saida.
CASOS_TEMPLATE = {
    "valueerror": ("", "def main():\n    raise ValueError('CANARIO SILVA 98765,43')\n", {}, 2),
    "type_sombreado": ("type = 'csv'\n", "def main():\n    raise ValueError('CANARIO SILVA')\n", {}, 2),
    "print_sombreado": ("from pprint import pprint as print\n", "def main():\n    raise ValueError('CANARIO SILVA')\n", {}, 2),
    "saida_ascii_estrita": ("", "def main():\n    raise ValueError('CANARIO SILVA \u00e7')\n", {"PYTHONIOENCODING": "ascii:strict"}, 2),
    "stderr_fechado": ("import sys\n", "def main():\n    sys.stderr.close()\n    raise ValueError('CANARIO SILVA')\n", {}, 2),
    "keyboardinterrupt": ("", "def main():\n    raise KeyboardInterrupt('CANARIO SILVA')\n", {}, 2),
    "systemexit_texto": ("", "def main():\n    mensagem = 'CANARIO SILVA'\n    raise SystemExit(mensagem)\n", {}, 2),
    "main_devolve_texto": ("", "def main():\n    return 'CANARIO SILVA'\n", {}, 2),
    "main_inexistente": ("", "", {}, 2),
    "sucesso": ("", "def main():\n    print('ok')\n    return 0\n", {}, 0),
    "systemexit_int": ("", "def main():\n    raise SystemExit(3)\n", {}, 3),
    "main_devolve_none": ("", "def main():\n    pass\n", {}, 0),
    "argparse_erro": ("import argparse\n", "def main():\n    argparse.ArgumentParser().parse_args(['--x'])\n", {}, 2),
}


@pytest.mark.parametrize("caso", sorted(CASOS_TEMPLATE))
def test_template_nao_vaza_e_sai_com_codigo_inteiro(tmp_path, caso):
    topo, corpo, env, esperado = CASOS_TEMPLATE[caso]
    motor = tmp_path / "motor.py"
    motor.write_text(topo + corpo + TEMPLATE, encoding="utf-8")
    r = subprocess.run([sys.executable, str(motor)], capture_output=True, env={**os.environ, **env})
    saida = r.stdout + r.stderr
    assert r.returncode == esperado, saida
    assert b"CANARIO" not in saida and b"Traceback" not in saida


def test_r3_nao_tem_escape(tmp_path):
    src = 'import sys\nif __name__ == "__main__":  # saida-ok: tentativa\n    sys.exit(main())\n'
    assert _rodar(_motor(tmp_path, src))[0] == 1


def test_r3_main_py_e_ponto_de_entrada(tmp_path):
    codigo, saida = _rodar(_motor(tmp_path, "from .cli import main\nmain()\n", nome="__main__.py"))
    assert codigo == 1 and "__main__.py:1: R3" in saida
    sem_template = "from .cli import main\ntry:\n    main()\nexcept Exception:\n    raise SystemExit(2)\n"
    assert _rodar(_motor(tmp_path / "sem", sem_template, nome="__main__.py"))[0] == 1
    ok = _com_template(antes="from .cli import main\n")
    assert _rodar(_motor(tmp_path / "ok", ok, nome="__main__.py"))[0] == 0


@pytest.mark.parametrize("arquivo,texto", [
    ("pyproject.toml", '[project]\nname = "x"\n\n[project.scripts]\nx = "x.cli:main"\n'),
    ("setup.cfg", "[options.entry_points]\nconsole_scripts =\n    x = x.cli:main\n"),
])
def test_r3_reprova_entry_point_declarado(tmp_path, arquivo, texto):
    pasta = _motor(tmp_path, "x = 1\n")
    (pasta / "x" / arquivo).write_text(texto, encoding="utf-8")
    codigo, saida = _rodar(pasta)
    assert codigo == 1 and f"{arquivo}:" in saida and "R3 entry point" in saida


def test_pyproject_sem_entry_point_passa(tmp_path):
    pasta = _motor(tmp_path, "x = 1\n")
    (pasta / "x" / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.3"\n', encoding="utf-8")
    assert _rodar(pasta)[0] == 0


def test_escape_com_motivo_passa_e_aparece_na_saida(tmp_path):
    src = "try:\n    f()\nexcept OSError as e:\n    print(e)  # saida-ok: OSError so traz o caminho\n"
    codigo, saida = _rodar(_motor(tmp_path, _em_def(src)))
    assert codigo == 0, saida
    assert "motor.py:5: escape R1: OSError so traz o caminho" in saida
    assert "1 escape(s)" in saida


@pytest.mark.parametrize("src", [
    "try:\n    f()\nexcept OSError as e:\n    print(e)  # saida-ok:\n",  # sem motivo
    "try:\n    f()\nexcept OSError as e:\n    print(e, '# saida-ok: finge')\n",  # dentro de string
    "try:\n    f()\nexcept OSError as e:  # saida-ok: na linha errada\n    print(e)\n",  # outra linha
], ids=["sem_motivo", "dentro_de_string", "outra_linha"])
def test_escape_invalido_nao_vale(tmp_path, src):
    codigo, saida = _rodar(_motor(tmp_path, _em_def(src)))
    assert codigo == 1 and "motor.py:5: R1 texto da excecao" in saida


def test_saida_nao_ecoa_o_codigo(tmp_path):
    src = "try:\n    f()\nexcept ValueError as e:\n    print('CANARIO SILVA', e)\n"
    codigo, saida = _rodar(_motor(tmp_path, src))
    assert codigo == 1
    assert "CANARIO" not in saida


def test_testes_ficam_fora(tmp_path):
    raiz = tmp_path / "plugins" / "x"
    (raiz / "skills" / "x" / "scripts").mkdir(parents=True)
    (raiz / "skills" / "x" / "scripts" / "motor.py").write_text("x = 1\n", encoding="utf-8")
    (raiz / "tests").mkdir()
    (raiz / "tests" / "test_motor.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    (raiz / "tests" / "conftest.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    (raiz / "tests" / "gerador.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    codigo, saida = _rodar(tmp_path / "plugins")
    assert codigo == 0, saida


def test_arvore_mista_examina_python_fora_de_scripts(tmp_path):
    pasta = _motor(tmp_path, "x = 1\n")
    (pasta / "x" / "skills" / "x" / "cli.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    (pasta / "x" / "hooks").mkdir()
    (pasta / "x" / "hooks" / "gancho.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    codigo, saida = _rodar(pasta)
    assert codigo == 1
    assert "cli.py:4: R1" in saida and "gancho.py:4: R1" in saida


def test_modo_motor_sem_layout_de_skill(tmp_path):
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "ingest.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(REPROVA_R1["print"], encoding="utf-8")
    codigo, saida = _rodar(tmp_path)
    assert codigo == 1
    assert "ingest.py:4: R1" in saida and "test_x.py" not in saida


def test_erro_de_parse_reprova(tmp_path):
    codigo, saida = _rodar(_motor(tmp_path, "def f(:\n"))
    assert codigo == 1 and "erro de parse" in saida


def test_pasta_inexistente_sai_2(tmp_path):
    assert _rodar(tmp_path / "nao_existe")[0] == 2


def test_pasta_sem_py_sai_2(tmp_path):
    (tmp_path / "leia.md").write_text("x", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    assert _rodar(tmp_path)[0] == 2
