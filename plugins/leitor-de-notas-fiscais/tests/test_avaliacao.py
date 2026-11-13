from decimal import Decimal

from engine.avaliacao import avaliar_nfse, avaliar_nfe
from engine.model import Campo, Confianca, Fonte, NFSeServico, NFeProduto


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_avaliar_nfse_ok():
    nf = NFSeServico(
        chave_acesso=_c("3" * 50), emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("1000.00")), iss_base=_c(Decimal("1000.00")),
        iss_aliquota=_c(Decimal("5.00")), iss_valor=_c(Decimal("50.00")),
        iss_retido=_c("true"), valor_liquido=_c(Decimal("950.00")),
    )
    rel = avaliar_nfse(nf)
    assert rel["iss_ok"] and rel["liquido_ok"] and rel["cnpj_ok"]
    assert rel["score_documento"] == 1.0 and rel["banda"] == "ALTA"


def test_avaliar_nfse_inclui_pis_cofins_nas_retencoes():
    # liquido = 2000 - (iss 50 + pis 50 + cofins 50) = 1850
    nf = NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("2000.00")), iss_base=_c(Decimal("2000.00")),
        iss_aliquota=_c(Decimal("2.50")), iss_valor=_c(Decimal("50.00")),
        iss_retido=_c("true"),
        ret_pis=_c(Decimal("50.00")), ret_cofins=_c(Decimal("50.00")),
        valor_liquido=_c(Decimal("1850.00")),
    )
    rel = avaliar_nfse(nf)
    assert rel["liquido_ok"] is True  # so passa se PIS/COFINS entram na soma


def test_avaliar_nfe_ok():
    nf = NFeProduto(
        chave_acesso=_c("9" * 44), emitente_cnpj=_c("11222333000181"),
        total_produtos=_c(Decimal("200.00")), total_nota=_c(Decimal("200.00")),
    )
    rel = avaliar_nfe(nf)
    assert rel["total_ok"] and rel["cnpj_ok"] and rel["banda"] == "ALTA"


def test_avaliar_nfse_iss_nao_retido_nao_entra_no_liquido():
    # ISS nao retido: liquido = servicos (ISS pago pelo prestador, nao descontado)
    nf = NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("1000.00")), iss_base=_c(Decimal("1000.00")),
        iss_aliquota=_c(Decimal("5.00")), iss_valor=_c(Decimal("50.00")),
        iss_retido=_c("false"), valor_liquido=_c(Decimal("1000.00")),
    )
    rel = avaliar_nfse(nf)
    assert rel["iss_ok"] is True
    assert rel["liquido_ok"] is True   # 1000 - 0 (ISS nao retido) = 1000


def test_avaliar_nfse_sem_liquido_pula_invariante():
    # doc nao declara liquido -> invariante de liquido nao roda (nao penaliza)
    nf = NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("1000.00")), iss_base=_c(Decimal("1000.00")),
        iss_aliquota=_c(Decimal("5.00")), iss_valor=_c(Decimal("50.00")),
        iss_retido=_c("false"),
    )
    rel = avaliar_nfse(nf)
    assert rel["liquido_ok"] is None    # nao checado
    assert rel["banda"] == "ALTA"        # iss ok + cnpj ok dominam


def _campo_pdf(v, score):
    return Campo(valor=v, confianca=Confianca(score=score, fonte=Fonte.PDF))


def test_avaliar_nfse_respeita_confianca_pdf():
    # campo vindo de PDF (score 0.9) com invariantes fechando -> doc fica MEDIA/ALTA conforme o menor
    nf = NFSeServico(
        emitente_cnpj=_campo_pdf("11222333000181", 0.9),
        valor_servicos=_campo_pdf(Decimal("1000.00"), 0.9),
        iss_base=_campo_pdf(Decimal("1000.00"), 0.9),
        iss_aliquota=_campo_pdf(Decimal("5.00"), 0.9),
        iss_valor=_campo_pdf(Decimal("50.00"), 0.9),
        iss_retido=Campo(valor="true", confianca=Confianca(score=0.9, fonte=Fonte.PDF)),
        valor_liquido=_campo_pdf(Decimal("950.00"), 0.9),
    )
    rel = avaliar_nfse(nf)
    assert rel["iss_ok"] is True and rel["liquido_ok"] is True and rel["cnpj_ok"] is True
    assert rel["score_documento"] == 0.9 and rel["banda"] == "ALTA"


def test_avaliar_nfse_pdf_que_falha_invariante_vira_baixa():
    nf = NFSeServico(
        emitente_cnpj=_campo_pdf("11222333000181", 0.9),
        valor_servicos=_campo_pdf(Decimal("1000.00"), 0.9),
        iss_base=_campo_pdf(Decimal("1000.00"), 0.9),
        iss_aliquota=_campo_pdf(Decimal("5.00"), 0.9),
        iss_valor=_campo_pdf(Decimal("0.00"), 0.9),   # como o "ISSQN Apurado 0" do spike
        iss_retido=Campo(valor="true", confianca=Confianca(score=0.9, fonte=Fonte.PDF)),
        valor_liquido=_campo_pdf(Decimal("950.00"), 0.9),
    )
    rel = avaliar_nfse(nf)
    assert rel["iss_ok"] is False        # 1000 x 5% = 50, declarado 0
    assert rel["banda"] == "BAIXA"
