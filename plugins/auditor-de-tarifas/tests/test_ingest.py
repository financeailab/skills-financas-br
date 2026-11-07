# -*- coding: utf-8 -*-
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gen_extrato_tarifas import LANCAMENTOS, escreve_fixtures, gerar_csv, gerar_ofx
from scripts.engine.ingest import ler_arquivo, ler_csv, ler_extratos, ler_ofx


def _por_banco_arquivo(banco, arquivo):
    return [l for l in LANCAMENTOS if l[0] == banco and l[5] == arquivo]


def test_ler_ofx_extrai_todas_as_txns_do_banco():
    esperado = _por_banco_arquivo("341", "ofx")
    txns, avisos = ler_ofx(gerar_ofx("341"))
    assert avisos == []
    assert len(txns) == len(esperado)
    assert all(t.banco == "341" for t in txns)


def test_ler_ofx_datas_e_valores_corretos():
    txns, _ = ler_ofx(gerar_ofx("341"))
    por_desc = {t.descricao: t for t in txns}
    tarifa = por_desc["TAR MANUTENCAO CESTA SERVICOS"]
    # ha 2 lancamentos com essa descricao (dez/24 e jan/25); pega qualquer um e confere valor
    assert tarifa.valor in (Decimal("-25.00"), Decimal("-29.90"))
    assert por_desc["TED 50000,00 PAGAMENTO FORNECEDOR"].valor == Decimal("-50000.00")


def test_ler_csv_extrai_txns_do_banco():
    esperado = _por_banco_arquivo("237", "csv")
    txns, avisos = ler_csv(gerar_csv("237"))
    assert avisos == []
    assert len(txns) == len(esperado)
    assert all(t.banco == "237" for t in txns)
    valores = {t.descricao: t.valor for t in txns}
    assert valores["TAR MANUTENCAO"] == Decimal("-19.90")
    assert valores["TAR PIX"] == Decimal("-2.00")


def test_ler_extratos_combina_ofx_e_csv(tmp_path):
    ofx_path, csv_path = escreve_fixtures(tmp_path)
    txns, avisos = ler_extratos([ofx_path, csv_path])
    assert avisos == []
    assert len(txns) == len(LANCAMENTOS)


def test_ler_extratos_aceita_diretorio(tmp_path):
    escreve_fixtures(tmp_path)
    txns, avisos = ler_extratos([tmp_path])
    assert avisos == []
    assert len(txns) == len(LANCAMENTOS)


def test_arquivo_invalido_nao_derruba(tmp_path):
    ruim = tmp_path / "extrato_corrompido.csv"
    ruim.write_text("", encoding="utf-8")
    txns, avisos = ler_arquivo(ruim)
    assert txns == []
    assert len(avisos) >= 1


def test_arquivo_inexistente_nao_derruba(tmp_path):
    txns, avisos = ler_arquivo(tmp_path / "nao_existe.ofx")
    assert txns == []
    assert len(avisos) == 1


def test_formato_nao_suportado_avisa_sem_derrubar(tmp_path):
    pdf_fake = tmp_path / "extrato.pdf"
    pdf_fake.write_text("qualquer coisa", encoding="utf-8")
    txns, avisos = ler_arquivo(pdf_fake)
    assert txns == []
    assert "F1" in avisos[0] or "nao suportado" in avisos[0]


# --- Bug 1: decode de encoding BR (cp1252/latin-1) antes de corromper acentos ---

def test_csv_cp1252_preserva_acentos_e_classifica(tmp_path):
    from scripts.engine.matcher import classifica
    # extrato BR gravado em cp1252, com cabecalho e descricao acentuados
    csv_path = tmp_path / "extrato_cp1252.csv"
    conteudo = "data;Histórico;valor;banco\n05/01/2025;TAR MANUTENÇÃO CESTA;-29,90;341\n"
    csv_path.write_bytes(conteudo.encode("cp1252"))
    txns, avisos = ler_arquivo(csv_path)
    assert avisos == []
    assert len(txns) == 1
    # o acento sobreviveu ao decode -> o matcher casa MANUTENCAO (antes falhava)
    assert classifica(txns[0].descricao) == "manutencao"
    assert txns[0].valor == Decimal("-29.90")


def test_ofx_cp1252_preserva_acentos(tmp_path):
    from scripts.engine.matcher import classifica
    ofx_path = tmp_path / "extrato_cp1252.ofx"
    bloco = (
        "OFXHEADER:100\n<OFX>\n<BANKTRANLIST>\n<STMTTRN>\n"
        "<TRNTYPE>DEBIT\n<DTPOSTED>20250110120000[-3:GMT]\n<TRNAMT>-3.90\n"
        "<MEMO>TAR MANUTENÇÃO CONTA\n</STMTTRN>\n</BANKTRANLIST>\n</OFX>\n"
    )
    ofx_path.write_bytes(bloco.encode("cp1252"))
    txns, avisos = ler_arquivo(ofx_path)
    assert avisos == []
    assert len(txns) == 1
    assert classifica(txns[0].descricao) == "manutencao"


# --- Bug 5: OFX vazio/sem lancamentos avisa (nao confunde export ruim com conta limpa) ---

def test_ofx_vazio_avisa():
    txns, avisos = ler_ofx("")
    assert txns == []
    assert len(avisos) >= 1


def test_ofx_sem_stmttrn_avisa():
    ofx = "OFXHEADER:100\n<OFX>\n<BANKTRANLIST>\n</BANKTRANLIST>\n</OFX>\n"
    txns, avisos = ler_ofx(ofx)
    assert txns == []
    assert len(avisos) >= 1


# --- Bug 6: scan de diretorio ignora o CSV de saida do proprio auditor ---

def test_scan_dir_ignora_saida_classificada(tmp_path):
    # os 2 fixtures + um CSV classificado (header do nosso --saida) no mesmo dir
    escreve_fixtures(tmp_path)
    classificado = tmp_path / "classificado.csv"
    classificado.write_text(
        "data,descricao,valor,banco,tipo\n"
        "2025-01-05,TAR MANUTENCAO,-29.90,341,manutencao\n",
        encoding="utf-8",
    )
    txns, _ = ler_extratos([tmp_path])
    # so as txns dos 2 fixtures entram; o classificado e pulado (senao duplicaria)
    assert len(txns) == len(LANCAMENTOS)


def test_ler_csv_aceita_sufixo_itau():
    # Alargamento declarado (spec Ponytail E3 §2.1): antes, "123,45-" levantava ValueError
    # em parse_valor e a linha virava aviso "linha CSV invalida ignorada" (ingest.py:131-135).
    # Com a canonica unida, o sufixo '-' e aceito e a linha entra como Txn negativa.
    texto = "data;descricao;valor;banco\n19/09/2026;TAR MANUTENCAO CESTA;123,45-;341\n"
    txns, avisos = ler_csv(texto)
    assert avisos == [], avisos
    assert len(txns) == 1, txns
    assert txns[0].valor == Decimal("-123.45")


def test_aviso_diz_arquivo_e_posicao_nunca_o_texto_do_extrato(tmp_path):
    # o aviso vai pro stderr que o Claude le (revisao do registry, issue #434)
    csv_txt = "data;descricao;valor;banco\n05/01/2025;TAR PIX;JOAO SILVA;341\nJOAO SILVA;TAR PIX;-2,00;341\n05/01/2025;TAR PIX\n"
    bloco = "<STMTTRN>\n<DTPOSTED>20250110\n<TRNAMT>{}\n<MEMO>TAR PIX\n</STMTTRN>\n"
    ofx_txt = "<OFX>\n" + bloco.format("JOAO SILVA") + bloco.format("-2.00") + bloco.replace("<TRNAMT>{}\n", "") + "</OFX>\n"
    csv_av = [f"linha CSV {n} invalida ignorada (data ou valor ilegivel, ou coluna faltando)" for n in (2, 3, 4)]
    ofx_av = ["lancamento OFX 1 invalido ignorado (data ou valor ilegivel)",
              "lancamento OFX 3 incompleto ignorado (faltou data/valor/descricao)"]
    assert ler_csv(csv_txt)[1] == csv_av
    txns, avisos = ler_ofx(ofx_txt)
    assert avisos == ofx_av and len(txns) == 1
    (tmp_path / "ruim.csv").write_text(csv_txt, encoding="utf-8")
    (tmp_path / "ruim.ofx").write_text(ofx_txt, encoding="utf-8")
    assert ler_arquivo(tmp_path / "ruim.csv")[1] == [f"ruim.csv: {a}" for a in csv_av]
    assert ler_arquivo(tmp_path / "ruim.ofx")[1] == [f"ruim.ofx: {a}" for a in ofx_av]
