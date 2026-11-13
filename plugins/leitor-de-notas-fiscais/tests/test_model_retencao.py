from decimal import Decimal

from engine.model import Campo, Confianca, Fonte, DocumentoBase, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_nfse_carrega_tipo_retencao_e_municipio_incidencia():
    nf = NFSeServico(
        iss_tipo_retencao=_c("retido_tomador"),
        iss_municipio_incidencia=_c("3550308"),
    )
    assert nf.iss_tipo_retencao.valor == "retido_tomador"
    assert nf.iss_municipio_incidencia.valor == "3550308"


def test_base_carrega_ret_federal_total():
    doc = DocumentoBase(modelo="NFSe", ret_federal_total=_c(Decimal("1115.00")))
    assert doc.ret_federal_total.valor == Decimal("1115.00")


def test_campos_novos_sao_opcionais():
    nf = NFSeServico()
    assert nf.iss_tipo_retencao is None
    assert nf.iss_municipio_incidencia is None
    assert nf.ret_federal_total is None
