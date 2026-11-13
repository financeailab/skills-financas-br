from engine.dispatch import processar
from engine.parsers.xml_nfe import parse_nfe
from tests.fixtures_status_natureza import NFE_DEVOLUCAO, NFE_VENDA


def test_devolucao_captura_natureza_e_sinaliza_sem_inverter():
    nf = parse_nfe(NFE_DEVOLUCAO)
    assert nf.natureza_operacao.valor == "DEVOLUCAO DE MERCADORIA"
    rel = processar(NFE_DEVOLUCAO)
    assert rel["banda"] == "ALTA"  # total fecha; o flag NAO rebaixa o score
    assert rel.get("forcar_conferir") is True
    assert any("devolu" in m.lower() for m in rel["motivos"])


def test_venda_normal_nao_sinaliza():
    rel = processar(NFE_VENDA)
    assert rel.get("forcar_conferir") is False
    assert not any("devolu" in m.lower() for m in rel["motivos"])
