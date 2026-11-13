from decimal import Decimal
from pathlib import Path

from engine.parsers.xml_nfe import parse_nfe

FIX = Path(__file__).parent / "fixtures" / "nfe_exemplo.xml"


def test_parse_nfe_totais():
    nf = parse_nfe(FIX.read_text(encoding="utf-8"))
    assert nf.emitente_cnpj.valor == "11222333000181"
    assert nf.total_produtos.valor == Decimal("200.00")
    assert nf.total_nota.valor == Decimal("200.00")
    assert len([c for c in nf.chave_acesso.valor if c.isdigit()]) == 44
