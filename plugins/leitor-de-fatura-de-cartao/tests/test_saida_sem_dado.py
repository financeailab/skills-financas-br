# -*- coding: utf-8 -*-
"""Canario da saida sem texto do arquivo: o que o motor imprime (stdout e stderr) nunca leva
texto do PDF da pessoa (portador, estabelecimento, texto de excecao ou de warning/log de
biblioteca). Tudo pelo CLI em subprocesso, nos dois layouts (SCRIPTS vem do conftest)."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import gen_faturas_pdf
from conftest import SCRIPTS

SENT = "SENTINELA"
CLI = os.path.join(SCRIPTS, "ler_fatura.py")


def _rodar(args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def _driver(tmp_path, corpo, argv):
    """Roda `main(argv)` num subprocesso depois de `corpo` (troca de funcoes internas)."""
    prog = tmp_path / "driver.py"
    prog.write_text(
        f"import sys\nsys.path.insert(0, {SCRIPTS!r})\nimport ler_fatura\n"
        + textwrap.dedent(corpo)
        + f"\nsys.exit(ler_fatura.main({argv!r}))\n",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(prog)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def _sem_sentinela(r):
    assert SENT not in r.stdout, r.stdout
    assert SENT not in r.stderr, r.stderr


def _pdf_sentinela(tmp_path, monkeypatch):
    g = gen_faturas_pdf.GABARITO["itau"]
    novas = [(d, "SENTINELA PORTADOR", "SENTINELA LOJA" if i == 0 else e, p, m, v)
             for i, (d, _po, e, p, m, v) in enumerate(g["lancamentos"])]
    monkeypatch.setitem(gen_faturas_pdf.GABARITO, "itau", {**g, "lancamentos": novas})
    return gen_faturas_pdf.gerar("itau", str(tmp_path / "s.pdf"))


def _pdf_log(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    pdf = tmp_path / "w.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 9)
    c.drawString(40, 780, "BANCO EXEMPLO ITA S.A.")
    c._code.append("/SENTINELA_WARN 1 0 0 1 0 cm")  # operador cru que o pdfminer loga
    c.showPage()
    c.save()
    return str(pdf)


def test_resumo_nao_imprime_portador_nem_estabelecimento(tmp_path, monkeypatch):
    pdf = _pdf_sentinela(tmp_path, monkeypatch)
    r = _rodar([pdf, "--saida", str(tmp_path / "o")])
    assert r.returncode == 0, r.stdout + r.stderr
    _sem_sentinela(r)
    linha = [l for l in r.stdout.splitlines() if l.startswith("Portadores:")]
    assert linha and linha[0].split()[-1] == "1", r.stdout
    # o arquivo gerado continua com o dado (e la que ele deve estar)
    assert SENT in open(tmp_path / "o.csv", encoding="utf-8-sig").read()


def test_log_de_biblioteca_nao_vaza(tmp_path):
    r = _rodar([_pdf_log(tmp_path), "--saida", str(tmp_path / "o")])
    _sem_sentinela(r)


def test_log_de_biblioteca_nao_vaza_com_handler_do_ambiente(tmp_path):
    # ambiente que ja instalou handler na raiz (basicConfig): so logging.disable cala
    r = _driver(tmp_path, "import logging\nlogging.basicConfig()\n",
                [_pdf_log(tmp_path), "--saida", str(tmp_path / "o")])
    _sem_sentinela(r)


def test_excecao_na_extracao_nao_vaza(tmp_path):
    pdf = gen_faturas_pdf.gerar("itau", str(tmp_path / "a.pdf"))
    r = _driver(tmp_path, """
        def boom(*a, **k):
            raise ValueError('SENTINELA_EXC')
        ler_fatura._extrair_paginas = boom
    """, [pdf, "--saida", str(tmp_path / "o")])
    _sem_sentinela(r)
    assert "ValueError" in r.stdout


def test_excecao_no_pipeline_nao_vaza(tmp_path):
    pdf = gen_faturas_pdf.gerar("itau", str(tmp_path / "a.pdf"))
    r = _driver(tmp_path, """
        def boom(*a, **k):
            raise ValueError('SENTINELA_EXC')
        ler_fatura.detector.detectar = boom
    """, [pdf, "--saida", str(tmp_path / "o")])
    _sem_sentinela(r)
    assert "ValueError" in r.stdout


def test_excecao_no_lote_nao_vaza(tmp_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    gen_faturas_pdf.gerar("itau", str(pasta / "a.pdf"))
    gen_faturas_pdf.gerar("bradesco", str(pasta / "b.pdf"))
    for alvo in ("_extrair_paginas", "detectar"):
        r = _driver(tmp_path, f"""
            def boom(*a, **k):
                raise ValueError('SENTINELA_EXC')
            ler_fatura.lote.{alvo} = boom
        """, ["--lote", str(pasta), "--csv", str(tmp_path / "c.csv")])
        _sem_sentinela(r)
        assert "a.pdf" in r.stdout and "ValueError" in r.stdout


def test_warning_de_biblioteca_nao_vaza(tmp_path):
    pdf = gen_faturas_pdf.gerar("itau", str(tmp_path / "a.pdf"))
    r = _driver(tmp_path, """
        import warnings
        _orig = ler_fatura._extrair_paginas
        def com_aviso(*a, **k):
            warnings.warn('SENTINELA_W')
            return _orig(*a, **k)
        ler_fatura._extrair_paginas = com_aviso
    """, [pdf, "--saida", str(tmp_path / "o")])
    _sem_sentinela(r)
    assert "UserWarning" in r.stderr  # o texto fixo nomeia so a categoria
