from decimal import Decimal
from engine.extracao import montar_nfse_de_extracao


def test_decimal_br_agora_converte():
    nf = montar_nfse_de_extracao({"valor_servicos": {"valor": "1.234,56", "rotulo_exato": True}})
    assert nf.valor_servicos.valor == Decimal("1234.56")   # antes virava None (sumia)


def test_decimal_ilegivel_sinaliza_nao_some():
    nf = montar_nfse_de_extracao({"valor_servicos": {"valor": "abc12def", "rotulo_exato": True}})
    # nao some em silencio: campo presente, confianca baixa, com motivo
    assert nf.valor_servicos is not None
    assert nf.valor_servicos.valor is None
    assert nf.valor_servicos.confianca.score <= 0.3
    assert nf.valor_servicos.confianca.motivo and "ileg" in nf.valor_servicos.confianca.motivo.lower()


def test_campo_ausente_continua_ausente():
    nf = montar_nfse_de_extracao({"valor_servicos": {"valor": "", "rotulo_exato": True}})
    assert nf.valor_servicos is None   # vazio = ausente legitimo, segue None
