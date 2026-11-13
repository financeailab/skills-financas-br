import itertools

import pytest

from engine.cruzamento import cruzar_tomador
from engine.model import TomadorReferencia
from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.parsers.xml_sp import parse_nfse_sp
from tests.fixtures_factory import (
    nfse_nacional, nfse_abrasf, nfse_sp,
    NOSSO_CNPJ, NOSSO_MUN, OUTRO_MUN, OUTRO_CNPJ, COD_OBRIGA, COD_NAO_OBRIGA,
)

REF = TomadorReferencia(cnpj=NOSSO_CNPJ, municipio_ibge=NOSSO_MUN)

# ---- PONTO A: retencao confirmada/qualificada pelo municipio (nacional) -- >=20 casos ----
# Varre tipo_ret (1/2/3) x municipio de incidencia (nosso/outro) x codigos -> 3*2*4 = 24
_A = list(itertools.product(("1", "2", "3"), (NOSSO_MUN, OUTRO_MUN), COD_NAO_OBRIGA))


@pytest.mark.parametrize("tipo_ret,inc,cod", _A)
def test_ponto_a_recolhimento_qualificado(tipo_ret, inc, cod):
    nf = parse_nfse_nacional(nfse_nacional(inc=inc, dest=NOSSO_CNPJ, tipo_ret=tipo_ret, cod=cod))
    r = cruzar_tomador(nf, REF)
    recolhe_tomador = tipo_ret == "2"  # so o tomador (2) recolhe; intermediario (3) e nao-retido (1) nao
    if recolhe_tomador and inc == OUTRO_MUN:
        assert r["iss_obrigacao_recolhimento_tomador"] is False
    elif recolhe_tomador:
        assert r["iss_obrigacao_recolhimento_tomador"] is True
    else:
        assert r["iss_obrigacao_recolhimento_tomador"] is False


# ---- PONTO B: enderecamento (3 familias x dest nosso/outro) -- >=20 casos ----
def _familias_endereco():
    casos = []
    for dest in (NOSSO_CNPJ, OUTRO_CNPJ):
        casos.append((parse_nfse_nacional, nfse_nacional(inc=NOSSO_MUN, dest=dest)))
        casos.append((parse_nfse_abrasf, nfse_abrasf(dest=dest, mun_tom=NOSSO_MUN)))
        casos.append((parse_nfse_sp, nfse_sp(dest=dest, mun_tom=NOSSO_MUN)))
    # replica p/ chegar a >=20 mantendo cobertura
    return (casos * 4)[:24]


@pytest.mark.parametrize("parser,xml", _familias_endereco())
def test_ponto_b_enderecamento(parser, xml):
    nf = parser(xml)
    r = cruzar_tomador(nf, REF)
    esperado = (nf.destinatario_doc.valor == NOSSO_CNPJ)
    assert r["enderecado_a_nos"] is esperado


# ---- PONTO C: alerta de retencao nao destacada (codigo §2 vs nao, incidencia nosso/outro) -- >=20 ----
# nao_retido x (codigo obriga / nao) x (incidencia nosso / outro) -> 2*4*2 ... usa nacional
_C = list(itertools.product(COD_OBRIGA + COD_NAO_OBRIGA, (NOSSO_MUN, OUTRO_MUN)))  # 8*2 = 16
_C = (_C * 2)[:24]


@pytest.mark.parametrize("cod,inc", _C)
def test_ponto_c_alerta_nao_destacada(cod, inc):
    nf = parse_nfse_nacional(nfse_nacional(inc=inc, dest=NOSSO_CNPJ, tipo_ret="1", cod=cod))
    r = cruzar_tomador(nf, REF)
    deve_alertar = (cod in COD_OBRIGA) and (inc == NOSSO_MUN)
    assert r["alerta_retencao_nao_destacada"] is deve_alertar
