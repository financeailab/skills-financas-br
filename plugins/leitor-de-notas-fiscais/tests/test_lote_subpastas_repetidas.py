"""Pasta com subpastas e nota repetida no lote (Review Focus do plano do B-rec do Leitor)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import ler_notas
from engine.batch import MOTIVO_REPETIDA, _repetida, processar_lote

FIX = Path(__file__).parent / "fixtures"
NFE = (FIX / "nfe_exemplo.xml").read_bytes()
NAC = (FIX / "nfse_nacional_exemplo.xml").read_bytes()
SP = (FIX / "nfse_sp_exemplo.xml").read_bytes()


def _resumo(tmp_path, pasta):
    out = tmp_path / "out"
    assert ler_notas.main(["processar", "--entrada", str(pasta), "--out", str(out)]) == 0
    return json.loads((out / "resumo.json").read_text(encoding="utf-8"))


def test_pasta_le_subpastas_como_o_zip(tmp_path):
    pasta = tmp_path / "notas"
    (pasta / "fornecedor-a").mkdir(parents=True)
    (pasta / "fornecedor-b" / "2026-03").mkdir(parents=True)
    (pasta / "fornecedor-a" / "n1.xml").write_bytes(NFE)
    (pasta / "fornecedor-b" / "2026-03" / "n2.xml").write_bytes(NAC)
    (pasta / "n3.XML").write_bytes(SP)
    (pasta / "fornecedor-a" / "n1 (1).xml").write_bytes(NFE)  # a mesma nota baixada de novo
    (pasta / "leia.txt").write_text("nao e nota", encoding="utf-8")
    r = _resumo(tmp_path, pasta)
    assert r["recebidas"] == 4 and r["total"] == 3 and r["repetidas"] == 1 and r["fora_do_limite"] == 0
    import openpyxl  # a aba Resumo da planilha mostra as repetidas, para a conta fechar sem o excecoes.csv
    ws = openpyxl.load_workbook(tmp_path / "out" / "carga.xlsx")["Resumo"]
    assert {ws.cell(row=k, column=1).value: ws.cell(row=k, column=2).value for k in range(3, 12)}["Repetidas"] == 1


def _linhas_csv(texto):
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


def test_mesma_nota_duas_vezes_entra_uma_vez_na_carga():
    res = processar_lote([("nota.xml", NFE), ("nota (1).xml", NFE)])
    assert len(res["linhas"]) == 1 and res["resumo"]["total"] == 1 and res["resumo"]["repetidas"] == 1
    assert len(_linhas_csv(res["csv"])) == 2  # cabecalho + 1 nota
    rep = [e for e in res["excecoes"] if e["motivo"] == MOTIVO_REPETIDA]
    assert [e["arquivo_origem"] for e in rep] == ["nota (1).xml"]
    for perfil in ("omie", "contaazul"):  # os perfis de ERP nao tem coluna de status: so a ausencia protege
        assert len(_linhas_csv(processar_lote([("a.xml", NFE), ("b.xml", NFE)], perfil=perfil)["csv"])) == 2


def test_nota_sem_chave_de_acesso_repetida_pela_reserva():
    res = processar_lote([("sp.xml", SP), ("sp (1).xml", SP)])
    assert res["resumo"]["repetidas"] == 1 and len(res["linhas"]) == 1
    assert res["linhas"][0]["chave_arquivo"].startswith("NFSE_")


def test_extracoes_repetidas_saem_da_carga_com_chave_ou_numero():
    import copy
    from engine.batch import processar_extracoes
    from tests.fixtures_cruzamento import CRUZ_RETIDO_NOSSO as C

    def ex(**extra):
        e = copy.deepcopy(C["extracao"])
        e["campos"].update({k: {"valor": v} for k, v in extra.items()})
        return e

    def repetidas(e):
        return processar_extracoes([("a.pdf", e), ("a (1).pdf", e)])["resumo"]["repetidas"]

    assert repetidas(ex(chave_acesso="3" * 50)) == 1
    assert repetidas(ex(emitente_cnpj="11222333000181", numero="123")) == 1
    # sem chave e sem numero (como a extracao do exemplo) a repetida nao e reconhecida: limite dito na SKILL
    assert repetidas(ex(emitente_cnpj="11222333000181")) == 0


def test_reserva_sem_cnpj_ou_numero_nao_conta_como_repetida():
    vistas = set()
    assert not _repetida({"chave_arquivo": "NFSE_____"}, vistas)
    assert not _repetida({"chave_arquivo": "NFSE_____"}, vistas)
    assert not _repetida({"chave_arquivo": "NFSE__3550308_11222333000181__202603"}, vistas)
    assert not _repetida({"chave_arquivo": "NFSE__3550308_11222333000181__202603"}, vistas)


def test_reserva_repete_so_na_mesma_familia_e_no_mesmo_mes():
    vistas = set()
    k = "NFSE___11222333000181_123_202603"
    assert not _repetida({"chave_arquivo": k, "familia": "nfse_abrasf"}, vistas)
    assert not _repetida({"chave_arquivo": k, "familia": "nfse_sp"}, vistas)
    assert not _repetida({"chave_arquivo": k[:-2] + "04", "familia": "nfse_sp"}, vistas)  # mesmo prestador e numero, outro mes
    assert _repetida({"chave_arquivo": k, "familia": "nfse_sp"}, vistas)


def test_notas_diferentes_nao_sao_repetidas():
    res = processar_lote([("nfe.xml", NFE), ("nac.xml", NAC), ("sp.xml", SP)])
    assert res["resumo"]["repetidas"] == 0 and res["resumo"]["total"] == 3


def test_danfe_sem_chave_com_series_diferentes_nao_e_repetida():
    """Achado 1 do Gate 2: mesmo fornecedor, numero e mes com serie diferente sao notas diferentes."""
    from engine.batch import processar_extracoes

    def ex(serie):
        campos = {"emitente_cnpj": "11222333000181", "numero": "123", "data_emissao": "2026-03-10",
                  "total_produtos": "100,00", "total_nota": "100,00"}
        if serie:
            campos["serie"] = serie
        return {"classe": "nfe", "campos": {k: {"valor": v} for k, v in campos.items()}}

    r = processar_extracoes([("a.pdf", ex("1")), ("b.pdf", ex("2"))])
    assert r["resumo"]["total"] == 2 and r["resumo"]["repetidas"] == 0
    assert len({ln["chave_arquivo"] for ln in r["linhas"]}) == 2
    assert processar_extracoes([("a.pdf", ex("1")), ("b.pdf", ex("1"))])["resumo"]["repetidas"] == 1  # mesma serie: repetida
    assert processar_extracoes([("a.pdf", ex(None)), ("b.pdf", ex(None))])["resumo"]["repetidas"] == 1  # sem serie: como antes
