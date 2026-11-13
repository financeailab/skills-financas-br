from engine.batch import processar_extracoes
from engine.model import TomadorReferencia
from tests.fixtures_cruzamento import FIXTURES_CRUZAMENTO, NOSSO_CNPJ, NOSSO_MUN

REF = TomadorReferencia(cnpj=NOSSO_CNPJ, municipio_ibge=NOSSO_MUN)


def test_cruzamento_3_cenarios():
    res = processar_extracoes([(f["arquivo"], f["extracao"]) for f in FIXTURES_CRUZAMENTO], tomador_ref=REF)
    by = {x["arquivo_origem"]: x for x in res["linhas"]}
    # (a) recolhimento qualificado
    a = by["cruz-a-retido-nosso.pdf"]
    assert a["iss_recolher_tomador"] == "Sim" and a["status"] == "auto-aprovada"
    assert "recolher por guia" in (a["motivos"] or "")
    # (b) alerta §2 -> conferir (cai nas excecoes)
    b = by["cruz-b-alerta-p2.pdf"]
    assert b["alerta_retencao"] == "Sim" and b["status"] == "conferir"
    # (c) inconsistencia -> auto-aprovada com motivo
    c = by["cruz-c-inconsistente.pdf"]
    assert c["status"] == "auto-aprovada" and "outro municipio" in (c["motivos"] or "")
    assert res["resumo"]["conferir"] == 1   # so o (b)
