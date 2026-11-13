from decimal import Decimal
from pathlib import Path

from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.model import Fonte

FIX = Path(__file__).parent / "fixtures" / "nfse_nacional_exemplo.xml"


def test_parse_nfse_campos_chave():
    nf = parse_nfse_nacional(FIX.read_text(encoding="utf-8"))
    assert nf.emitente_cnpj.valor == "11222333000181"
    assert nf.valor_servicos.valor == Decimal("1000.00")
    assert nf.iss_base.valor == Decimal("1000.00")
    assert nf.iss_aliquota.valor == Decimal("5.00")
    assert nf.iss_valor.valor == Decimal("50.00")
    assert nf.valor_liquido.valor == Decimal("950.00")
    # tudo de XML deterministico = confianca XML
    assert nf.valor_servicos.confianca.fonte == Fonte.XML


def test_parse_nfse_chave_50_digitos():
    nf = parse_nfse_nacional(FIX.read_text(encoding="utf-8"))
    assert nf.chave_acesso.valor is not None
    assert len([c for c in nf.chave_acesso.valor if c.isdigit()]) == 50
