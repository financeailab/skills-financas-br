from decimal import Decimal

from engine.avaliacao import avaliar_nfse
from engine.model import Campo, Confianca, Fonte, NFSeServico, TomadorReferencia


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def _nf(tipo, inc, dest, cod=None):
    return NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("10000.00")),
        iss_base=_c(Decimal("10000.00")), iss_aliquota=_c(Decimal("5.00")), iss_valor=_c(Decimal("500.00")),
        iss_tipo_retencao=_c(tipo), iss_municipio_incidencia=_c(inc),
        destinatario_doc=_c(dest), codigo_servico=_c(cod) if cod else None,
    )


REF = TomadorReferencia(cnpj="22222222000122", municipio_ibge="3550308")


def test_sem_tomador_mantem_comportamento_plan06():
    r = avaliar_nfse(_nf("retido_tomador", "3550308", "22222222000122"))
    assert r["iss_obrigacao_recolhimento_tomador"] is True
    assert "enderecado_a_nos" not in r  # so aparece quando ha contexto


def test_com_tomador_qualifica_e_adiciona_chaves():
    r = avaliar_nfse(_nf("retido_tomador", "3304557", "22222222000122"), tomador_ref=REF)
    # incidencia em outro municipio -> nao recolhe, apesar de a nota dizer retido
    assert r["iss_obrigacao_recolhimento_tomador"] is False
    assert r["municipio_incidencia_confere"] is False
    assert r["enderecado_a_nos"] is True
    assert any("outro municipio" in m for m in r["motivos"])


def test_com_tomador_alerta_nao_destacada_entra_nos_motivos():
    r = avaliar_nfse(_nf("nao_retido", "3550308", "22222222000122", cod="0702"), tomador_ref=REF)
    assert r["alerta_retencao_nao_destacada"] is True
    assert any("LC116" in m for m in r["motivos"])
