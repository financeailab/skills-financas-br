# -*- coding: utf-8 -*-
"""ingest_erp.py: perfis de coluna `generico` e `omie`, CSV e XLSX, status
em-aberto vs baixado (SPEC-00 §4)."""
import csv
from decimal import Decimal

import pytest

import gen_vectors as gv
from ingest_erp import ler_titulos


def _escreve_csv(path, linhas, campos):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in linhas:
            w.writerow(r)


def test_generico_titulo_em_aberto(tmp_path):
    p = tmp_path / "pagar.csv"
    _escreve_csv(p, [{"fornecedor": "ACME", "documento": "1", "vencimento": "10/08/2026",
                       "valor": "500,00", "status": "aberto"}],
                 ["fornecedor", "documento", "vencimento", "valor", "status"])
    titulos = ler_titulos(str(p), perfil="generico", tipo="pagar")
    assert len(titulos) == 1
    t = titulos[0]
    assert t["em_aberto"] is True
    assert t["valor"] == Decimal("500.00")
    assert str(t["vencimento"]) == "2026-08-10"
    assert t["contraparte"] == "ACME"
    assert t["tipo"] == "pagar"


@pytest.mark.parametrize("status,esperado", [
    ("pago", False), ("baixado", False), ("liquidado", False),
    ("recebido", False), ("cancelado", False),
    ("aberto", True), ("pendente", True), ("a pagar", True), ("a receber", True),
    ("", True),
    ("quitado", True),  # status desconhecido -> default em_aberto=True (Decisao D4)
])
def test_generico_status_em_aberto_vs_baixado(tmp_path, status, esperado):
    p = tmp_path / "titulos.csv"
    _escreve_csv(p, [{"cliente": "X", "documento": "1", "vencimento": "01/09/2026",
                       "valor": "100,00", "status": status}],
                 ["cliente", "documento", "vencimento", "valor", "status"])
    titulos = ler_titulos(str(p), perfil="generico", tipo="receber")
    assert titulos[0]["em_aberto"] is esperado


@pytest.mark.parametrize("status,esperado", [
    ("A vencer", True), ("Vencido", True), ("Pago", False), ("Recebido", False),
    ("Cancelado", False), ("Liquidado", False), ("Baixado", False),  # mesma lista fechada do generico
])
def test_omie_mapeamento_colunas_e_status(tmp_path, status, esperado):
    p = tmp_path / "omie.csv"
    _escreve_csv(p, [{"Fornecedor": "Omie Fornecedor LTDA", "Número Doc.": "NF-9",
                       "Vencimento": "15/09/2026", "Valor Doc.": "1.250,90", "Status": status}],
                 ["Fornecedor", "Número Doc.", "Vencimento", "Valor Doc.", "Status"])
    titulos = ler_titulos(str(p), perfil="omie", tipo="pagar")
    assert len(titulos) == 1
    t = titulos[0]
    assert t["em_aberto"] is esperado
    assert t["valor"] == Decimal("1250.90")
    assert t["documento"] == "NF-9"
    assert t["contraparte"] == "Omie Fornecedor LTDA"


def test_xlsx_le_igual_ao_csv(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    linhas = [{"fornecedor": "ACME", "documento": "1", "vencimento": "10/08/2026",
               "valor": "500,00", "status": "aberto"}]
    campos = ["fornecedor", "documento", "vencimento", "valor", "status"]
    csv_path = tmp_path / "pagar.csv"
    _escreve_csv(csv_path, linhas, campos)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(campos)
    ws.append([linhas[0][c] for c in campos])
    xlsx_path = tmp_path / "pagar.xlsx"
    wb.save(xlsx_path)

    t_csv = ler_titulos(str(csv_path), perfil="generico", tipo="pagar")
    t_xlsx = ler_titulos(str(xlsx_path), perfil="generico", tipo="pagar")
    assert t_csv[0]["valor"] == t_xlsx[0]["valor"]
    assert t_csv[0]["vencimento"] == t_xlsx[0]["vencimento"]
    assert t_csv[0]["em_aberto"] == t_xlsx[0]["em_aberto"]


def test_coluna_obrigatoria_faltando_mensagem_pt_br(tmp_path):
    p = tmp_path / "pagar.csv"
    _escreve_csv(p, [{"fornecedor": "ACME", "valor": "500,00"}], ["fornecedor", "valor"])
    with pytest.raises(ValueError) as exc:
        ler_titulos(str(p), perfil="generico", tipo="pagar")
    msg = str(exc.value)
    assert "vencimento" in msg
    assert "generico" in msg.lower()


def test_valor_sempre_positivo_no_titulo(tmp_path):
    p = tmp_path / "pagar.csv"
    _escreve_csv(p, [{"fornecedor": "ACME", "documento": "1", "vencimento": "10/08/2026",
                       "valor": "-500,00", "status": "aberto"}],
                 ["fornecedor", "documento", "vencimento", "valor", "status"])
    titulos = ler_titulos(str(p), perfil="generico", tipo="pagar")
    assert titulos[0]["valor"] == Decimal("500.00")


def test_perfil_desconhecido_levanta_erro(tmp_path):
    p = tmp_path / "pagar.csv"
    _escreve_csv(p, [{"fornecedor": "ACME", "valor": "1,00", "vencimento": "01/01/2026"}],
                 ["fornecedor", "valor", "vencimento"])
    with pytest.raises(ValueError):
        ler_titulos(str(p), perfil="sap-magico", tipo="pagar")


def test_gabarito_titulos_pagar_e_receber(tmp_path):
    pagar_p = tmp_path / "pagar.csv"
    receber_p = tmp_path / "receber.csv"
    _escreve_csv(pagar_p, gv.titulos_pagar_generico(),
                 ["fornecedor", "documento", "vencimento", "valor", "status"])
    _escreve_csv(receber_p, gv.titulos_receber_generico(),
                 ["cliente", "documento", "vencimento", "valor", "status"])

    pagar = ler_titulos(str(pagar_p), perfil="generico", tipo="pagar")
    receber = ler_titulos(str(receber_p), perfil="generico", tipo="receber")

    assert len(pagar) == 4
    assert len(receber) == 3
    por_doc_pagar = {t["documento"]: t for t in pagar}
    assert por_doc_pagar["NF-0999"]["em_aberto"] is False   # ja pago
    assert por_doc_pagar["NF-1002"]["em_aberto"] is True    # vencido mas em aberto
    assert por_doc_pagar["NF-2000"]["valor"] == Decimal("80000.00")
    por_doc_receber = {t["documento"]: t for t in receber}
    assert por_doc_receber["NF-R502"]["em_aberto"] is False  # ja recebido
    assert por_doc_receber["NF-R501"]["em_aberto"] is True   # vencido mas em aberto


def test_xlsx_sem_dimension_nao_perde_a_coluna_status(tmp_path):
    """Gate 2, passe 3: sem <dimension> o openpyxl corta a celula vazia do fim da 1a linha; a coluna
    status sumia do cabecalho logico e o titulo pago entrava na projecao."""
    import re
    import zipfile
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["fornecedor", "documento", "vencimento", "valor", "status"])
    ws.append(["ACME", "1", "10/08/2026", "100,00", None])
    ws.append(["BETA", "2", "10/08/2026", "200,00", "pago"])
    bruto = tmp_path / "bruto.xlsx"
    wb.save(bruto)
    with zipfile.ZipFile(bruto) as zin, zipfile.ZipFile(tmp_path / "pagar.xlsx", "w") as zout:
        for item in zin.infolist():
            dados = zin.read(item.filename)
            if item.filename.startswith("xl/worksheets/"):
                dados, n = re.subn(rb"<dimension[^>]*/>", b"", dados)
                assert n == 1
            zout.writestr(item, dados)
    titulos = ler_titulos(str(tmp_path / "pagar.xlsx"), perfil="generico", tipo="pagar")
    assert [t["em_aberto"] for t in titulos] == [True, False]


def test_xlsx_valor_numerico_com_tres_casas_nao_vira_milhar(tmp_path):
    """Gate 2, passe 3: a celula numerica 2.345 lida como texto BR virava 2345,00."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["fornecedor", "vencimento", "valor"])
    ws.append(["ACME", "10/08/2026", 2.345])
    ws.append(["BETA", "10/08/2026", 1500])
    p = tmp_path / "pagar.xlsx"
    wb.save(p)
    assert [t["valor"] for t in ler_titulos(str(p), perfil="generico", tipo="pagar")] == [
        Decimal("2.35"), Decimal("1500.00")]
