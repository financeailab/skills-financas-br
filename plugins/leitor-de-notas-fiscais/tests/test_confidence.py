from engine.confidence import score_campo, banda, score_documento
from engine.model import Fonte


def test_xml_e_alta():
    assert score_campo(fonte=Fonte.XML) == 1.0
    assert banda(1.0) == "ALTA"


def test_pdf_alias_exato_invariante_ok():
    s = score_campo(fonte=Fonte.PDF, alias_exato=True, invariante_ok=True, dv_ok=True)
    assert 0.85 <= s <= 0.95
    assert banda(s) == "ALTA"


def test_pdf_inferido():
    s = score_campo(fonte=Fonte.PDF, alias_exato=False, invariante_ok=True)
    assert 0.6 <= s < 0.85
    assert banda(s) == "MEDIA"


def test_so_invariante():
    s = score_campo(fonte=Fonte.INVARIANTE)
    assert s <= 0.5
    assert banda(s) == "BAIXA"


def test_falha_invariante_derruba():
    s = score_campo(fonte=Fonte.XML, invariante_ok=False)
    assert s <= 0.3
    assert banda(s) == "BAIXA"


def test_documento_pior_campo_critico_domina():
    # um campo critico baixo derruba o doc inteiro
    assert score_documento([1.0, 1.0, 0.3]) == 0.3
    assert score_documento([1.0, 1.0]) == 1.0


def test_inferido_score_atual():
    # documenta o comportamento atual: INFERIDO cai no else -> 0.5 -> BAIXA
    s = score_campo(fonte=Fonte.INFERIDO)
    assert s == 0.5
    assert banda(s) == "BAIXA"
