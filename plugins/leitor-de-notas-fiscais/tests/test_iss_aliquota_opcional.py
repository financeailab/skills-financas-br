# -*- coding: utf-8 -*-
"""D3: NFS-e nacional sem pAliqAplic no XML = ISS nao conferivel (informativo, nao rebaixa).
So o nacional; ABRASF, SP e extracao de PDF seguem a regra de sempre."""
from __future__ import annotations

from pathlib import Path

from engine.avaliacao import avaliar_nfse
from engine.batch import processar_extracoes, processar_lote
from engine.dispatch import parsear

FIX = Path(__file__).parent / "fixtures"
NACIONAL = (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")
ABRASF = (FIX / "nfse_abrasf_exemplo.xml").read_text(encoding="utf-8")
SEM_ALIQ = NACIONAL.replace("<pAliqAplic>5.00</pAliqAplic>", "")
INFO = "Aliquota de ISS nao veio no XML: ISS nao conferido"


def test_nacional_sem_aliquota_nao_rebaixa_e_nao_confere():
    assert "pAliqAplic" not in SEM_ALIQ
    r = processar_lote([("n.xml", SEM_ALIQ)])
    assert r["linhas"][0]["status"] == "auto-aprovada"
    assert INFO in r["linhas"][0]["motivos"]
    assert "ISS nao fecha" not in r["linhas"][0]["motivos"]
    fam, modelo = parsear(SEM_ALIQ)
    assert avaliar_nfse(modelo, aliquota_opcional=True)["iss_ok"] is None


def test_nacional_com_aliquota_certa_segue_igual():
    r = processar_lote([("n.xml", NACIONAL)])
    assert r["linhas"][0]["status"] == "auto-aprovada" and INFO not in r["linhas"][0]["motivos"]
    fam, modelo = parsear(NACIONAL)
    assert avaliar_nfse(modelo, aliquota_opcional=True)["iss_ok"] is True


def test_nacional_com_aliquota_errada_segue_nao_fecha():
    r = processar_lote([("n.xml", NACIONAL.replace("5.00</pAliqAplic>", "3.00</pAliqAplic>"))])
    assert r["linhas"][0]["status"] != "auto-aprovada"
    assert "ISS nao fecha" in r["linhas"][0]["motivos"] and INFO not in r["linhas"][0]["motivos"]


def test_nacional_aliquota_zero_declarada_segue_a_regra():
    r = processar_lote([("n.xml", NACIONAL.replace("5.00</pAliqAplic>", "0.00</pAliqAplic>"))])
    assert "ISS nao fecha" in r["linhas"][0]["motivos"]  # 0 declarado != ausente


def test_abrasf_sem_aliquota_segue_nao_fecha():
    sem = ABRASF.replace("<Aliquota>5.00</Aliquota>", "")
    assert sem != ABRASF
    r = processar_lote([("a.xml", sem)])
    assert r["linhas"][0]["status"] != "auto-aprovada"
    assert "ISS nao fecha" in r["linhas"][0]["motivos"] and INFO not in r["linhas"][0]["motivos"]


def test_extracao_pdf_sem_aliquota_segue_nao_fecha():
    ex = {"classe": "nfse", "campos": {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "valor_servicos": {"valor": "5000.00", "rotulo_exato": True},
        "iss_base": {"valor": "5000.00", "rotulo_exato": True},
        "iss_valor": {"valor": "250.00", "rotulo_exato": True}}}
    r = processar_extracoes([("d.pdf", ex)])
    assert "ISS nao fecha" in r["linhas"][0]["motivos"] and INFO not in r["linhas"][0]["motivos"]


def test_nacional_simples_sem_aliquota_nao_duplica_o_aviso_de_iss():
    fam, modelo = parsear(SEM_ALIQ)
    r = avaliar_nfse(modelo.model_copy(update={"simples_nacional": True}), aliquota_opcional=True)
    assert INFO not in r["motivos"]
    assert any(m.startswith("Simples Nacional") for m in r["motivos"])
