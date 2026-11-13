from decimal import Decimal

from engine.cruzamento import cruzar_tomador
from engine.model import Campo, Confianca, Fonte, NFSeServico, TomadorReferencia


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def _nf(tipo=None, inc=None, dest=None, cod=None):
    return NFSeServico(
        iss_tipo_retencao=_c(tipo) if tipo else None,
        iss_municipio_incidencia=_c(inc) if inc else None,
        destinatario_doc=_c(dest) if dest else None,
        codigo_servico=_c(cod) if cod else None,
    )


REF = TomadorReferencia(cnpj="22.222.222/0001-22", municipio_ibge="3550308")


def test_retencao_confirmada_no_nosso_municipio():
    r = cruzar_tomador(_nf(tipo="retido_tomador", inc="3550308", dest="22222222000122"), REF)
    assert r["iss_obrigacao_recolhimento_tomador"] is True
    assert r["municipio_incidencia_confere"] is True
    assert r["enderecado_a_nos"] is True


def test_retido_mas_incidencia_em_outro_municipio_nao_recolhe():
    r = cruzar_tomador(_nf(tipo="retido_tomador", inc="3304557", dest="22222222000122"), REF)
    assert r["iss_obrigacao_recolhimento_tomador"] is False
    assert any("outro municipio" in m for m in r["motivos_tomador"])


def test_nota_nao_enderecada_a_nos():
    r = cruzar_tomador(_nf(tipo="nao_retido", dest="99999999000199"), REF)
    assert r["enderecado_a_nos"] is False
    assert any("endere" in m.lower() for m in r["motivos_tomador"])


def test_alerta_retencao_nao_destacada():
    # nao retido, incidencia no nosso municipio, servico 7.02 (construcao = obriga reter)
    r = cruzar_tomador(_nf(tipo="nao_retido", inc="3550308", dest="22222222000122", cod="0702"), REF)
    assert r["alerta_retencao_nao_destacada"] is True
    assert any("LC116" in m for m in r["motivos_tomador"])


def test_sem_alerta_quando_servico_nao_obriga():
    r = cruzar_tomador(_nf(tipo="nao_retido", inc="3550308", dest="22222222000122", cod="0101"), REF)
    assert r["alerta_retencao_nao_destacada"] is False


def test_incidencia_desconhecida_nao_afirma():
    r = cruzar_tomador(_nf(tipo="retido_tomador", dest="22222222000122"), REF)  # sem inc
    assert r["municipio_incidencia_confere"] is None
    assert r["iss_obrigacao_recolhimento_tomador"] is True  # best-effort: confia na nota


def test_intermediario_nao_recolhe_pelo_tomador():
    r = cruzar_tomador(_nf(tipo="retido_intermediario", inc="3550308", dest="22222222000122"), REF)
    assert r["iss_obrigacao_recolhimento_tomador"] is False
