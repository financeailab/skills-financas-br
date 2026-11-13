from decimal import Decimal
import pytest
from engine.export.csv_generico import COLUNAS
from engine.export.linha import montar_linha
from engine.model import Campo, Confianca, Fonte, NFSeServico, NFeProduto


def _c(v): return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))
_REL = {"banda": "ALTA", "motivos": [], "score_documento": 0.9, "file_key": "k", "familia": "x"}

_MODELOS = [
    NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("100.00"))),
    NFeProduto(total_nota=_c(Decimal("100.00"))),
]


@pytest.mark.parametrize("modelo", _MODELOS)
def test_toda_coluna_tem_origem(modelo):
    linha = montar_linha(modelo, _REL, "doc.pdf")
    faltando = [c for c in COLUNAS if c not in linha]
    assert not faltando, f"colunas sem origem em montar_linha p/ {type(modelo).__name__}: {faltando}"
