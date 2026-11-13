from decimal import Decimal
from pathlib import Path

from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.model import Fonte

FIX = Path(__file__).parent / "fixtures" / "nfse_abrasf_exemplo.xml"


def test_parse_abrasf_campos():
    nf = parse_nfse_abrasf(FIX.read_text(encoding="utf-8"))
    assert nf.numero.valor == "123"
    assert nf.codigo_verificacao.valor == "ABC12345"
    assert nf.emitente_cnpj.valor == "11222333000181"
    assert nf.emitente_nome.valor == "PRESTADOR EXEMPLO LTDA"
    assert nf.codigo_servico.valor == "0702"
    assert nf.valor_servicos.valor == Decimal("1000.00")
    assert nf.iss_base.valor == Decimal("1000.00")
    assert nf.iss_aliquota.valor == Decimal("5.00")
    assert nf.iss_valor.valor == Decimal("50.00")
    assert nf.valor_liquido.valor == Decimal("950.00")
    assert nf.iss_retido.valor == "true"
    assert nf.valor_servicos.confianca.fonte == Fonte.XML
