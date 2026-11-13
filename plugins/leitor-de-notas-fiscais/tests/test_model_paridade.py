from decimal import Decimal
from engine.model import Campo, Confianca, Fonte, DocumentoBase, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))


def test_base_endereco_e_inss_detalhe():
    d = DocumentoBase(modelo="NFSe", emitente_endereco=_c("Av X, 1 - SP"),
                      destinatario_endereco=_c("Av Y, 2 - SP"),
                      ret_inss_base=_c(Decimal("1000.00")), ret_inss_aliquota=_c(Decimal("11.00")))
    assert d.emitente_endereco.valor == "Av X, 1 - SP"
    assert d.destinatario_endereco.valor == "Av Y, 2 - SP"
    assert d.ret_inss_base.valor == Decimal("1000.00")
    assert d.ret_inss_aliquota.valor == Decimal("11.00")


def test_nfse_intermediario_e_valor_recebido():
    nf = NFSeServico(intermediario_doc=_c("11444777000161"), intermediario_nome=_c("Plataforma Y"),
                     valor_recebido=_c(Decimal("14943.31")))
    assert nf.intermediario_doc.valor == "11444777000161"
    assert nf.intermediario_nome.valor == "Plataforma Y"
    assert nf.valor_recebido.valor == Decimal("14943.31")


def test_defaults():
    assert DocumentoBase(modelo="X").emitente_endereco is None
    assert NFSeServico().intermediario_doc is None
    assert NFSeServico().valor_recebido is None
