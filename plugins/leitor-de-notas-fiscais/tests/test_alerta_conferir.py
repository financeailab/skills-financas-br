from engine.batch import processar_extracoes
from engine.model import TomadorReferencia

NOSSO = "11444777000161"; NOSSO_MUN = "3550308"; OUTRO_MUN = "3304557"
REF = TomadorReferencia(cnpj=NOSSO, municipio_ibge=NOSSO_MUN)


def _nfse(tipo, mun, cod):
    return {"classe": "nfse", "campos": {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "valor_servicos": {"valor": "10000.00", "rotulo_exato": True},
        "iss_base": {"valor": "10000.00", "rotulo_exato": True},
        "iss_aliquota": {"valor": "5.00", "rotulo_exato": True},
        "iss_valor": {"valor": "500.00", "rotulo_exato": True},
        "iss_tipo_retencao": {"valor": tipo, "rotulo_exato": True},
        "iss_municipio_incidencia": {"valor": mun, "rotulo_exato": True},
        "codigo_servico": {"valor": cod, "rotulo_exato": True},
        "destinatario_doc": {"valor": NOSSO, "rotulo_exato": True}}}


def test_alerta_paragrafo2_vira_conferir_e_excecao():
    # nao retido + servico 0702 (construcao = LC116 §2) + incidencia no nosso municipio
    res = processar_extracoes([("b.pdf", _nfse("nao_retido", NOSSO_MUN, "0702"))], tomador_ref=REF)
    l = res["linhas"][0]
    assert l["alerta_retencao"] == "Sim"
    assert l["status"] == "conferir"                     # NAO auto-aprova (decisao do owner)
    assert res["resumo"]["conferir"] == 1
    assert any("§2" in e.get("motivo", "") or "LC116" in e.get("motivo", "") for e in res["excecoes"])


def test_inconsistencia_e_recolhimento_seguem_auto_aprovados():
    # (a) recolhimento e (c) inconsistencia ficam auto-aprovados com o motivo (decisao do owner)
    res = processar_extracoes([
        ("a.pdf", _nfse("retido_tomador", NOSSO_MUN, "0101")),
        ("c.pdf", _nfse("retido_tomador", OUTRO_MUN, "0101")),
    ], tomador_ref=REF)
    by = {x["arquivo_origem"]: x for x in res["linhas"]}
    assert by["a.pdf"]["status"] == "auto-aprovada" and by["a.pdf"]["iss_recolher_tomador"] == "Sim"
    assert by["c.pdf"]["status"] == "auto-aprovada"
    assert "outro municipio" in (by["c.pdf"]["motivos"] or "")
