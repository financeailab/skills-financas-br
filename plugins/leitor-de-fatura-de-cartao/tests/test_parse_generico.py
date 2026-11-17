# -*- coding: utf-8 -*-
"""Testa o parser generico (melhor-esforco) contra os 2 fixtures de layout desconhecido."""
import pdfplumber

import gen_faturas_pdf as gpdf
from bancos import generico


def _paginas(path):
    with pdfplumber.open(path) as pdf:
        return [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]


def test_generico_le_lancamentos_best_effort(tmp_path):
    path = gpdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    r = generico.parse(_paginas(path))
    assert r.emissor == "generico"
    assert len(r.lancamentos) == 4
    assert r.lancamentos[0].estabelecimento == "Restaurante Sabor Caseiro"
    from decimal import Decimal
    assert r.lancamentos[0].valor == Decimal("89.90")
    assert r.veredicto != "LAYOUT DESCONHECIDO"


def test_generico_estorno_contabil_parenteses_capturado(tmp_path):
    """Achado Codex pre-PR: estorno na forma contabil ('R$ (37,50)') era pulado em
    silencio pela regex de valor. Tem que virar lancamento com valor NEGATIVO."""
    from decimal import Decimal
    path = gpdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    r = generico.parse(_paginas(path))
    estornos = [l for l in r.lancamentos if l.valor < 0]
    assert len(estornos) == 1
    assert estornos[0].valor == Decimal("-37.50")
    assert "Estorno" in estornos[0].estabelecimento


def test_generico_nao_extrai_total_nem_portador(tmp_path):
    path = gpdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    r = generico.parse(_paginas(path))
    assert r.total_fatura is None
    assert all(l.portador == "" for l in r.lancamentos)
    assert all(l.parcela is None for l in r.lancamentos)


def test_generico_layout_desconhecido_quando_nada_reconhecivel(tmp_path):
    path = gpdf.gerar_generico_ilegivel(str(tmp_path / "ilegivel.pdf"))
    r = generico.parse(_paginas(path))
    assert r.veredicto == "LAYOUT DESCONHECIDO"
    assert r.aviso != ""
    assert r.lancamentos == []


def test_generico_ordem_cronologica(tmp_path):
    path = gpdf.gerar_generico_reconhecivel(str(tmp_path / "generico.pdf"))
    r = generico.parse(_paginas(path))
    datas = [l.data for l in r.lancamentos]
    assert datas == sorted(datas)
