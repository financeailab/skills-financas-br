from engine.batch import processar_extracoes


def test_dict_nao_nota_vira_excecao_fora_do_escopo():
    # boleto/recibo/etc nao sao mais processados: rejeicao limpa, nao crash nem lixo
    ex = {"tipo_documento": "boleto", "campos": {"valor": {"valor": "100,00"}}}
    res = processar_extracoes([("x.pdf", ex)])
    assert res["resumo"]["falhou"] == 1
    assert res["resumo"]["total"] == 0
    assert any("nota fiscal" in (e.get("motivo") or "").lower() for e in res["excecoes"])


def test_nfse_e_nfe_seguem_processando():
    # sanidade: o caminho de nota nao regrediu (dict minimo de NF-e)
    nfe = {"classe": "nfe", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
           "total_nota": {"valor": "100,00"}, "total_produtos": {"valor": "100,00"}}}
    res = processar_extracoes([("nfe.pdf", nfe)])
    assert res["resumo"]["total"] == 1
