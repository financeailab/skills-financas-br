from engine.normalizacao import (
    RET_NAO, RET_TOMADOR, RET_INTERMEDIARIO,
    tipo_retencao_iss, tipo_retencao_de_booleano, retido_por_tipo,
)


def test_tpretissqn_mapeia_tabela_nacional():
    assert tipo_retencao_iss("1") == RET_NAO
    assert tipo_retencao_iss("2") == RET_TOMADOR
    assert tipo_retencao_iss("3") == RET_INTERMEDIARIO
    assert tipo_retencao_iss(" 2 ") == RET_TOMADOR  # tolerante a espaco


def test_tpretissqn_desconhecido_ou_ausente_vira_none():
    assert tipo_retencao_iss(None) is None
    assert tipo_retencao_iss("9") is None
    assert tipo_retencao_iss("") is None


def test_tipo_de_booleano():
    assert tipo_retencao_de_booleano(True) == RET_TOMADOR
    assert tipo_retencao_de_booleano(False) == RET_NAO


def test_retido_por_tipo():
    assert retido_por_tipo(RET_TOMADOR) is True
    assert retido_por_tipo(RET_INTERMEDIARIO) is True
    assert retido_por_tipo(RET_NAO) is False
    assert retido_por_tipo(None) is None
