"""Achado 4 do Gate 2: NFS-e sem valor de servico legivel nao se auto-aprova (so CNPJ + Simples saia a 0,9)."""
from __future__ import annotations

from engine.batch import processar_extracoes


def _linha(campos, **meta):
    ex = {"classe": "nfse", "campos": {k: {"valor": v, "rotulo_exato": True} for k, v in campos.items()}, **meta}
    return processar_extracoes([("a.pdf", ex)])["linhas"][0]


def test_so_cnpj_e_simples_nao_se_auto_aprova():
    ln = _linha({"emitente_cnpj": "11222333000181"}, simples_nacional=True)
    assert ln["status"] == "conferir" and ln["confianca_nota"] <= 0.3
    assert "valor do servico" in ln["motivos"].lower()


def test_valor_ilegivel_tambem_nao_se_auto_aprova():
    ln = _linha({"emitente_cnpj": "11222333000181", "valor_servicos": "??"}, simples_nacional=True)
    assert ln["status"] == "conferir"


def test_com_valor_e_sem_iss_no_simples_segue_auto_aprovada():
    ln = _linha({"emitente_cnpj": "11222333000181", "valor_servicos": "100,00"}, simples_nacional=True)
    assert ln["status"] == "auto-aprovada" and ln["valor_total"] is not None
