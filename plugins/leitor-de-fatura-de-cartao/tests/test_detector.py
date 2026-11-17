# -*- coding: utf-8 -*-
"""Testa o detector de layout contra os fixtures gerados (itau/bradesco/generico)."""
import os

import pdfplumber

import gen_faturas_pdf as gpdf
from detector import detectar


def _paginas(path):
    with pdfplumber.open(path) as pdf:
        return [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]


def test_detecta_itau(tmp_path):
    path = gpdf.gerar("itau", str(tmp_path / "itau.pdf"))
    assert detectar(_paginas(path)) == "itau"


def test_detecta_bradesco(tmp_path):
    path = gpdf.gerar("bradesco", str(tmp_path / "bradesco.pdf"))
    assert detectar(_paginas(path)) == "bradesco"


def test_detecta_generico_quando_sem_assinatura_conhecida(tmp_path):
    path = gpdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    assert detectar(_paginas(path)) == "generico"


def test_detecta_generico_para_pdf_ilegivel(tmp_path):
    path = gpdf.gerar_generico_ilegivel(str(tmp_path / "ilegivel.pdf"))
    assert detectar(_paginas(path)) == "generico"
