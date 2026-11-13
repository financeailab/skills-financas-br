from engine.model import (
    DocumentoBase, DocumentoFiscalBase, NFSeServico, NFeProduto, TipoDocumento,
)


def test_base_renomeada_com_alias_de_compat():
    assert DocumentoFiscalBase is DocumentoBase  # alias mantido


def test_nota_fiscal_marca_is_documento_fiscal_true():
    assert NFSeServico().is_documento_fiscal is True
    assert NFSeServico().tipo_documento == TipoDocumento.NFSE.value
    assert NFeProduto().tipo_documento == TipoDocumento.NFE.value


def test_base_aceita_tipo_e_flag():
    d = DocumentoBase(modelo="X", tipo_documento="recibo", is_documento_fiscal=False)
    assert d.tipo_documento == "recibo"
    assert d.is_documento_fiscal is False
