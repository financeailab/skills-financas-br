from decimal import Decimal
from pathlib import Path

from engine.parsers.xml_sp import parse_nfse_sp

FIX = Path(__file__).parent / "fixtures" / "nfse_sp_exemplo.xml"


def test_parse_sp_campos_e_normalizacao():
    nf = parse_nfse_sp(FIX.read_text(encoding="utf-8"))
    assert nf.numero.valor == "123"
    assert nf.codigo_verificacao.valor == "ABCD1234"
    assert nf.emitente_cnpj.valor == "11222333000181"
    assert nf.emitente_nome.valor == "PRESTADOR EXEMPLO LTDA"
    assert nf.codigo_servico.valor == "07498"
    assert nf.valor_servicos.valor == Decimal("1000.00")
    # base cai no fallback ValorServicos
    assert nf.iss_base.valor == Decimal("1000.00")
    # aliquota normalizada de fracao 0.05 -> 5.00
    assert nf.iss_aliquota.valor == Decimal("5.00")
    assert nf.iss_valor.valor == Decimal("50.00")
    assert nf.iss_retido.valor == "false"
    # SP nao emite liquido nesta fixture
    assert nf.valor_liquido.valor is None
