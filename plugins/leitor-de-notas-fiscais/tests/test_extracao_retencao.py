from decimal import Decimal

from engine.extracao import montar_nfse_de_extracao


def test_extracao_pdf_traz_tipo_retencao_e_total_federal():
    extracao = {
        "iss_tipo_retencao": {"valor": "retido_tomador", "rotulo_exato": True},
        "iss_municipio_incidencia": {"valor": "3550308", "rotulo_exato": True},
        "ret_federal_total": {"valor": "1115.00", "rotulo_exato": True},
    }
    nf = montar_nfse_de_extracao(extracao)
    assert nf.iss_tipo_retencao.valor == "retido_tomador"
    assert nf.iss_municipio_incidencia.valor == "3550308"
    assert nf.ret_federal_total.valor == Decimal("1115.00")  # convertido p/ Decimal
