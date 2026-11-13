from engine.batch import processar_extracoes


def test_lote_so_processa_nota_rejeita_o_resto():
    # Descope v1: so NFS-e/NF-e viram linha; recibo/invoice viram excecao (fora do escopo).
    extracoes = [
        ("nota1.pdf", {"classe": "nfse", "campos": {
            "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
            "valor_servicos": {"valor": "1000.00", "rotulo_exato": True},
            "iss_base": {"valor": "1000.00"}, "iss_aliquota": {"valor": "5.00"},
            "iss_valor": {"valor": "50.00", "rotulo_exato": True}}}),
        ("recibo.pdf", {"tipo_documento": {"valor": "recibo"}, "campos": {
            "emitente_cnpj": {"valor": "11222333000181"}, "valor_total": {"valor": "300.00"}}}),
        ("inv.pdf", {"tipo_documento": {"valor": "invoice_internacional"}, "campos": {
            "moeda": {"valor": "USD"}, "valor_origem": {"valor": "500.00"}, "emitente_nome": {"valor": "Acme"}}}),
    ]
    res = processar_extracoes(extracoes, perfil="generico")
    assert res["resumo"]["total"] == 1   # so a nota
    assert res["resumo"]["falhou"] == 2  # recibo + invoice rejeitados
    tipos = {l["tipo_documento"] for l in res["linhas"]}
    assert tipos == {"nfse"}
    assert "csv" in res and "resumo" in res and "excecoes" in res


def test_extracao_ruim_vira_excecao_nao_derruba():
    # A nota boa passa; entrada sem nota vira excecao limpa (nao derruba o lote).
    res = processar_extracoes([("x.pdf", {"campos": {}}), ("nota.pdf", {"classe": "nfse",
                              "campos": {"emitente_cnpj": {"valor": "11222333000181"},
                                         "valor_servicos": {"valor": "10.00"}}})])
    assert res["resumo"]["total"] >= 1   # a nota boa passa
