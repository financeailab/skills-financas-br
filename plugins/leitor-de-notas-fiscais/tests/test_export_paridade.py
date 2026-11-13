from decimal import Decimal
from engine.export.linha import montar_linha
from engine.export.csv_generico import COLUNAS
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def test_colunas_paridade_existem():
    for col in ("emitente_endereco", "destinatario_endereco", "intermediario_doc",
                "intermediario_nome", "ret_inss_base", "ret_inss_aliquota", "valor_recebido"):
        assert col in COLUNAS


def test_linha_paridade_preenche():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("4483.00")),
                     emitente_endereco=_c("Av X, 1"), intermediario_doc=_c("11444777000161"),
                     valor_recebido=_c(Decimal("14943.31")))
    rel = {"banda": "ALTA", "motivos": [], "score_documento": 0.9, "file_key": "k"}
    linha = montar_linha(nf, rel, "n.pdf")
    assert linha["emitente_endereco"] == "Av X, 1"
    assert linha["intermediario_doc"] == "11444777000161"
    assert linha["valor_recebido"] == Decimal("14943.31")
    assert linha["valor_total"] == Decimal("4483.00")        # fiscal != recebido
