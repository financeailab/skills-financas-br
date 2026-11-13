from engine.batch import processar_extracoes
from engine.extracao import montar_nfse_de_extracao
from engine.avaliacao import avaliar_nfse


def test_valor_servicos_ilegivel_nao_auto_aprova_e_vira_excecao():
    # CNPJ + ISS validos, mas valor_servicos ILEGIVEL -> NAO pode auto-aprovar
    ex = {"classe": "nfse", "campos": {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "iss_base": {"valor": "1000.00"}, "iss_aliquota": {"valor": "5.00"},
        "iss_valor": {"valor": "50.00", "rotulo_exato": True},
        "valor_servicos": {"valor": "abc", "rotulo_exato": True}}}
    nf = montar_nfse_de_extracao(ex["campos"])
    r = avaliar_nfse(nf)
    assert r["banda"] != "ALTA"
    assert any("ileg" in m.lower() for m in r["motivos"])
    # ponta a ponta: cai nas excecoes
    res = processar_extracoes([("nota.pdf", ex)])
    assert res["resumo"]["auto_aprovadas"] == 0
    assert res["resumo"]["conferir"] == 1
    assert len(res["excecoes"]) >= 1
