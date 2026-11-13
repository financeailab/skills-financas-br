import io
from decimal import Decimal

import openpyxl

from engine.export.xlsx import exportar_xlsx


def _wb(linhas, resumo):
    return openpyxl.load_workbook(io.BytesIO(exportar_xlsx(linhas, resumo)))


LINHAS = [
    {"arquivo_origem": "a.xml", "fornecedor_nome": "Forn A", "fornecedor_cnpj": "11222333000181",
     "tipo_documento": "nfe", "data_emissao": "2026-03-01", "vencimento": "2026-03-14",
     "valor_total": Decimal("1234.56"), "valor_liquido": Decimal("1234.56"), "ret_federal_total": None,
     "natureza_operacao": "VENDA", "cancelada": "", "status": "auto-aprovada",
     "confianca_nota": Decimal("1.0"), "motivos": ""},
    {"arquivo_origem": "b.pdf", "fornecedor_nome": "Forn B", "fornecedor_cnpj": "11222333000181",
     "tipo_documento": "nfse", "data_emissao": "2026-03-02", "vencimento": "", "valor_total": Decimal("700.00"),
     "valor_liquido": Decimal("656.95"), "ret_federal_total": Decimal("43.05"), "natureza_operacao": "",
     "cancelada": "Sim", "status": "conferir", "confianca_nota": Decimal("0.4"),
     "motivos": "Nota CANCELADA: nao pagar / nao lancar"},
]
RESUMO = {"total": 2, "auto_aprovadas": 1, "conferir": 1, "falhou": 0, "por_tipo": {"nfe": 1, "nfse": 1}}


def test_tem_3_abas():
    wb = _wb(LINHAS, RESUMO)
    assert wb.sheetnames == ["Carga", "Conferir", "Resumo"]


def test_cabecalho_esmeralda_bold_freeze_autofilter():
    ws = _wb(LINHAS, RESUMO)["Carga"]
    c = ws["A1"]
    assert c.fill.fgColor.rgb.endswith("047857")
    assert c.font.bold and c.font.color.rgb.endswith("FFFFFF")
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None


def test_status_colorido():
    ws = _wb(LINHAS, RESUMO)["Carga"]
    col = list(__import__("engine.export.xlsx", fromlist=["COLUNAS_XLSX"]).COLUNAS_XLSX).index("status") + 1
    # linha 2 = auto (wash E7F6EF); linha 3 = conferir (ambar FEF3C7)
    assert ws.cell(row=2, column=col).fill.fgColor.rgb.endswith("E7F6EF")
    assert ws.cell(row=3, column=col).fill.fgColor.rgb.endswith("FEF3C7")


def test_valor_moeda_e_data_nativos():
    ws = _wb(LINHAS, RESUMO)["Carga"]
    import engine.export.xlsx as X
    cval = list(X.COLUNAS_XLSX).index("valor_total") + 1
    cdata = list(X.COLUNAS_XLSX).index("vencimento") + 1
    vcell = ws.cell(row=2, column=cval)
    assert isinstance(vcell.value, (int, float)) and abs(vcell.value - 1234.56) < 0.01
    assert "R$" in vcell.number_format
    import datetime
    assert isinstance(ws.cell(row=2, column=cdata).value, datetime.date)


def test_conferir_so_excecoes():
    ws = _wb(LINHAS, RESUMO)["Conferir"]
    # 1 cabecalho + 1 linha (so a status=conferir)
    assert ws.max_row == 2
    assert "CANCELADA" in str(ws.cell(row=2, column=list(__import__("engine.export.xlsx", fromlist=["COLUNAS_XLSX"]).COLUNAS_XLSX).index("motivos") + 1).value)


def test_resumo_tem_totais():
    ws = _wb(LINHAS, RESUMO)["Resumo"]
    txt = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "2" in txt and "auto" in txt.lower() and "conferir" in txt.lower()


def test_cancelada_vermelho():
    ws = _wb(LINHAS, RESUMO)["Carga"]
    import engine.export.xlsx as X
    ccanc = list(X.COLUNAS_XLSX).index("cancelada") + 1
    # linha 3 = cancelada "Sim" -> vermelho FEE2E2
    assert ws.cell(row=3, column=ccanc).fill.fgColor.rgb.endswith("FEE2E2")


def test_resumo_usa_por_familia_no_lote_xml():
    import io, openpyxl
    from engine.export.xlsx import exportar_xlsx
    resumo = {"total": 3, "auto_aprovadas": 3, "conferir": 0, "falhou": 0, "por_familia": {"nfe": 2, "nfse_sp": 1}}
    wb = openpyxl.load_workbook(io.BytesIO(exportar_xlsx([], resumo)))
    txt = "\n".join(str(c.value) for row in wb["Resumo"].iter_rows() for c in row if c.value is not None)
    assert "nfe" in txt and "nfse_sp" in txt


def test_confianca_color_scale_e_percent():
    ws = _wb(LINHAS, RESUMO)["Carga"]
    import engine.export.xlsx as X
    cconf = list(X.COLUNAS_XLSX).index("confianca_nota") + 1
    cell = ws.cell(row=2, column=cconf)
    assert isinstance(cell.value, (int, float)) and abs(cell.value - 1.0) < 0.001
    assert "%" in cell.number_format
    # color scale registrada na coluna de confianca
    assert any(ws.conditional_formatting)
