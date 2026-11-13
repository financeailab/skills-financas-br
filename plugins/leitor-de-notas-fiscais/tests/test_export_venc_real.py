from decimal import Decimal
from engine.export.linha import montar_linha
from engine.model import Campo, Confianca, Fonte, NFSeServico, NFeProduto


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def _rel():
    return {"banda": "ALTA", "motivos": [], "score_documento": 0.9, "file_key": "k"}


def test_carga_nfse_preenche_vencimento():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("100.00")),
                     vencimento=_c("2026-05-30"))
    assert montar_linha(nf, _rel(), "n.pdf")["vencimento"] == "2026-05-30"


def test_carga_nfe_preenche_vencimento():
    nf = NFeProduto(total_nota=_c(Decimal("100.00")), vencimento=_c("2026-04-02"))
    assert montar_linha(nf, _rel(), "n.pdf")["vencimento"] == "2026-04-02"
