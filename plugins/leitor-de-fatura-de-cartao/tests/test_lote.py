# -*- coding: utf-8 -*-
"""Testes do modo lote (lote.py): consolidacao, resumo, excecoes, dedupe por hash,
limite de arquivos por lote (invariantes (e) e (f) do SPEC-00 §10)."""
import shutil

import gen_faturas_pdf as gpdf
import lote


def _montar_pasta(tmp_path, com_duplicata=False):
    pasta = tmp_path / "faturas"
    pasta.mkdir()
    gpdf.gerar("itau", str(pasta / "itau.pdf"))
    gpdf.gerar("bradesco", str(pasta / "bradesco.pdf"))
    gpdf.gerar("itau", str(pasta / "itau_furado.pdf"), furado=True)
    if com_duplicata:
        shutil.copyfile(pasta / "itau.pdf", pasta / "itau_copia.pdf")
    return pasta


def test_processar_pasta_consolida_as_faturas(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)

    assert len(processadas) == 3
    assert duplicatas == []
    assert excedentes == []
    nomes = sorted(p.name for p, _ in processadas)
    assert nomes == ["bradesco.pdf", "itau.pdf", "itau_furado.pdf"]


def test_processar_pasta_marca_veredicto_por_arquivo(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, _, _ = lote.processar_pasta(pasta)
    por_nome = {p.name: fatura.veredicto for p, fatura in processadas}

    assert por_nome["itau.pdf"] == "OK"
    assert por_nome["bradesco.pdf"] == "OK"
    assert por_nome["itau_furado.pdf"] == "TOTAL NAO FECHA"


def test_resumo_agregado_conta_por_veredicto(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)
    resumo = lote.resumo_agregado(processadas, duplicatas, excedentes)

    assert resumo["total_arquivos"] == 3
    assert resumo["processadas"] == 3
    assert resumo["por_veredicto"]["OK"] == 2
    assert resumo["por_veredicto"]["TOTAL NAO FECHA"] == 1


def test_listar_excecoes_so_traz_o_que_nao_e_ok(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, _, _ = lote.processar_pasta(pasta)
    excecoes = lote.listar_excecoes(processadas)

    assert len(excecoes) == 1
    nome, veredicto, aviso = excecoes[0]
    assert nome == "itau_furado.pdf"
    assert veredicto == "TOTAL NAO FECHA"
    assert aviso != ""


def test_dedupe_por_hash_mesmo_arquivo_2x_nao_duplica(tmp_path):
    """Invariante (f): mesmo PDF (conteudo identico) processado 2x no lote nao
    duplica no consolidado nem na contagem do resumo."""
    pasta = _montar_pasta(tmp_path, com_duplicata=True)
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)

    assert len(processadas) == 3  # itau_copia.pdf NAO entra como um 4o processado
    assert len(duplicatas) == 1
    assert duplicatas[0].name == "itau_copia.pdf"

    resumo = lote.resumo_agregado(processadas, duplicatas, excedentes)
    assert resumo["duplicatas"] == 1
    assert resumo["total_arquivos"] == 4  # 3 processadas + 1 duplicata, contabilizado sem sumir


def test_limite_do_lote_gera_excedentes(tmp_path):
    """Invariante (e): lote respeita um limite maximo; o que passar vira excedente
    (nao processado, o operador divide o lote)."""
    pasta = _montar_pasta(tmp_path)
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta, limite=2)

    assert len(processadas) == 2
    assert len(excedentes) == 1
    assert duplicatas == []


def test_exportar_csv_consolidado_tem_uma_linha_por_lancamento_e_por_encargo(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, _, _ = lote.processar_pasta(pasta)
    out_csv = tmp_path / "consolidado.csv"
    lote.exportar_csv_consolidado(processadas, str(out_csv))

    texto = out_csv.read_text(encoding="utf-8-sig")
    linhas = [l for l in texto.splitlines() if l]
    total_lancamentos = sum(len(fatura.lancamentos) + len(fatura.encargos) for _, fatura in processadas)
    assert len(linhas) == 1 + total_lancamentos  # cabecalho + 1 linha por lancamento e por encargo
    assert "arquivo;veredicto_fatura;data;portador" in linhas[0]
    # a fatura furada ainda contribui seus lancamentos reais (honestidade: nao esconde dado)
    assert any("itau_furado.pdf" in l for l in linhas)
    assert any("TOTAL NAO FECHA" in l for l in linhas)


def _gerar_pdf_que_quebra_o_parse(path):
    """PDF NATIVO legivel, com o cabecalho tipo-Itau (o detector despacha pro parser
    itau), mas com uma DATA INVALIDA (31/02) na linha de lancamento -> parse_data
    levanta ValueError DENTRO do parser. Achado Codex pre-PR: essa excecao interna
    derrubava o lote inteiro com stacktrace (so a extracao do PDF era protegida)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 9)
    y = 780
    for txt in (
        "BANCO EXEMPLO ITA S.A.",
        "FATURA CARTAO CORPORATIVO",
        "Portador: FULANO QUALQUER",
        "31/02/2026 Loja Fantasma R$ 10,00",  # 31 de fevereiro: parse_data explode
    ):
        c.drawString(40, y, txt)
        y -= 14
    c.showPage()
    c.save()


def test_lote_nao_aborta_quando_um_arquivo_quebra_o_parse(tmp_path):
    """Invariante do lote (achado Codex pre-PR): um arquivo que estoura excecao
    INTERNA (deteccao/parse/prova) nao pode impedir os demais; ele entra sinalizado
    nas excecoes, igual ao caminho single-file."""
    pasta = tmp_path / "faturas"
    pasta.mkdir()
    gpdf.gerar("itau", str(pasta / "itau.pdf"))
    _gerar_pdf_que_quebra_o_parse(pasta / "quebrada.pdf")

    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)

    assert len(processadas) == 2  # a valida NAO foi abortada pela quebrada
    por_nome = {p.name: fatura for p, fatura in processadas}
    assert por_nome["itau.pdf"].veredicto == "OK"
    assert por_nome["quebrada.pdf"].veredicto == "LAYOUT DESCONHECIDO"
    assert por_nome["quebrada.pdf"].aviso != ""
    assert por_nome["quebrada.pdf"].lancamentos == []  # nunca inventa lancamento

    excecoes = lote.listar_excecoes(processadas)
    assert [n for n, _, _ in excecoes] == ["quebrada.pdf"]


def test_exportar_xlsx_consolidado_gera_arquivo_com_2_abas(tmp_path):
    pasta = _montar_pasta(tmp_path)
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)
    resumo = lote.resumo_agregado(processadas, duplicatas, excedentes)
    out_xlsx = tmp_path / "consolidado.xlsx"
    lote.exportar_xlsx_consolidado(processadas, resumo, str(out_xlsx))

    import openpyxl
    wb = openpyxl.load_workbook(str(out_xlsx))
    assert set(wb.sheetnames) == {"Lancamentos", "Resumo"}
