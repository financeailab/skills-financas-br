from engine.extracao import montar_nfse_de_extracao


def test_extracao_nfse_venc_e_simples():
    nf = montar_nfse_de_extracao({
        "valor_servicos": {"valor": "15000.00", "rotulo_exato": True},
        "vencimento": {"valor": "2026-05-30", "rotulo_exato": True},
        "simples_nacional": {"valor": "true"},
    })
    assert nf.vencimento.valor == "2026-05-30"
    assert nf.simples_nacional is True


def test_extracao_sem_simples_fica_false():
    nf = montar_nfse_de_extracao({"valor_servicos": {"valor": "100.00"}})
    assert nf.simples_nacional is False
