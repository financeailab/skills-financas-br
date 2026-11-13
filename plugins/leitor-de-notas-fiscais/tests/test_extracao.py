from decimal import Decimal

from engine.extracao import montar_nfse_de_extracao
from engine.model import Fonte


def test_montar_nfse_pdf_rotulo_exato():
    ext = {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "valor_servicos": {"valor": "1000.00", "rotulo_exato": True},
        "iss_base": {"valor": "1000.00", "rotulo_exato": True},
        "iss_aliquota": {"valor": "5.00", "rotulo_exato": True},
        "iss_valor": {"valor": "50.00", "rotulo_exato": True},
        "iss_retido": {"valor": "true", "rotulo_exato": True},
        "valor_liquido": {"valor": "950.00", "rotulo_exato": True},
    }
    nf = montar_nfse_de_extracao(ext)
    assert nf.valor_servicos.valor == Decimal("1000.00")
    assert nf.valor_servicos.confianca.fonte == Fonte.PDF
    assert nf.valor_servicos.confianca.score == 0.9   # PDF + rotulo exato
    assert nf.iss_retido.valor == "true"


def test_montar_nfse_pdf_inferido_e_ausente():
    ext = {
        "valor_servicos": {"valor": "1000.00", "rotulo_exato": False},  # inferido
        "iss_valor": {"valor": None, "rotulo_exato": False},            # ausente
    }
    nf = montar_nfse_de_extracao(ext)
    assert nf.valor_servicos.confianca.score == 0.7   # PDF inferido
    assert nf.iss_valor is None                         # valor ausente -> campo None


def test_montar_nfe_pdf():
    from engine.extracao import montar_nfe_de_extracao
    ext = {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "total_produtos": {"valor": "500.00", "rotulo_exato": True},
        "total_nota": {"valor": "500.00", "rotulo_exato": True},
    }
    nf = montar_nfe_de_extracao(ext)
    assert nf.modelo == "NFe"
    assert nf.total_nota.valor == Decimal("500.00")
    assert nf.total_nota.confianca.score == 0.9
    assert nf.total_nota.confianca.fonte == Fonte.PDF
