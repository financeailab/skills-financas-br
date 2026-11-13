from engine.batch import processar_extracoes
from tests.fixtures_status_natureza import NFSE_PDF_CANCELADA


def test_nfse_cancelada_vira_conferir_com_motivo():
    l = processar_extracoes([("c.pdf", NFSE_PDF_CANCELADA)])["linhas"][0]
    assert l["status"] == "conferir"
    assert "cancelad" in (l.get("motivos") or "").lower()
    assert l.get("cancelada") == "Sim"


def test_nota_nao_cancelada_segue_normal():
    ex = {"classe": "nfse", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
          "valor_servicos": {"valor": "1000,00"}, "iss_valor": {"valor": "50,00"},
          "iss_base": {"valor": "1000,00"}, "iss_aliquota": {"valor": "5,00"}}}
    l = processar_extracoes([("n.pdf", ex)])["linhas"][0]
    assert l.get("cancelada") in (None, "", )


def test_nfe_cancelada_vira_conferir_com_motivo():
    ex = {"classe": "nfe", "cancelada": True, "campos": {
        "emitente_cnpj": {"valor": "11222333000181"},
        "total_nota": {"valor": "500,00"}, "total_produtos": {"valor": "500,00"}}}
    l = processar_extracoes([("c.pdf", ex)])["linhas"][0]
    assert l["status"] == "conferir"
    assert "cancelad" in (l.get("motivos") or "").lower()
    assert l.get("cancelada") == "Sim"
