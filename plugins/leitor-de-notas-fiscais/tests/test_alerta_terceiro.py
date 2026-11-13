from engine.batch import processar_extracoes
from engine.model import TomadorReferencia

NOSSO = "11444777000161"; OUTRO_CNPJ = "99999999000191"; NOSSO_MUN = "3550308"
REF = TomadorReferencia(cnpj=NOSSO, municipio_ibge=NOSSO_MUN)


def _nfse(dest):
    return {"classe": "nfse", "campos": {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "valor_servicos": {"valor": "10000.00", "rotulo_exato": True},
        "iss_base": {"valor": "10000.00"},
        "iss_aliquota": {"valor": "5.00"},
        "iss_valor": {"valor": "500.00", "rotulo_exato": True},
        "iss_tipo_retencao": {"valor": "nao_retido", "rotulo_exato": True},
        "iss_municipio_incidencia": {"valor": NOSSO_MUN, "rotulo_exato": True},
        "codigo_servico": {"valor": "0702", "rotulo_exato": True},
        "destinatario_doc": {"valor": dest, "rotulo_exato": True}}}


def test_alerta_p2_de_nota_de_terceiro_nao_rebaixa():
    # enderecada a OUTRO CNPJ -> o §2 nao e nosso -> NAO rebaixa por §2
    res = processar_extracoes([("terceiro.pdf", _nfse(OUTRO_CNPJ))], tomador_ref=REF)
    assert res["linhas"][0]["status"] == "auto-aprovada"


def test_alerta_p2_da_nossa_nota_rebaixa():
    res = processar_extracoes([("nossa.pdf", _nfse(NOSSO))], tomador_ref=REF)
    assert res["linhas"][0]["status"] == "conferir"
