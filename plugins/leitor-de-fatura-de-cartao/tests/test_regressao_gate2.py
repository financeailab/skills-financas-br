# -*- coding: utf-8 -*-
"""Regressoes do Gate 2 da abertura (15/11): valor sem milhar no generico, encargos no consolidado do lote e
cabecalho com acento nos leitores itau e bradesco."""
from decimal import Decimal

import openpyxl
import pdfplumber

import gen_faturas_pdf as gpdf
import lote
from bancos import bradesco, generico, itau
from modelo import BAIXA_CONFIANCA, FaturaParsed, LAYOUT_DESCONHECIDO, Lancamento, OK, TOTAL_NAO_FECHA
from prova_total import validar as validar_total

NL = chr(10)


def _gen(*linhas):
    return generico.parse([{"texto": NL.join(linhas), "words": []}])


def test_generico_le_valor_sem_separador_de_milhar_inteiro_e_com_sinal():
    f = _gen("05/01/2026 Loja Alfa R$ 1234,56", "06/01/2026 Loja Beta R$ -1234,56", "07/01/2026 Loja Gama 1.234,56")
    assert [(l.estabelecimento, l.valor) for l in f.lancamentos] == [
        ("Loja Alfa", Decimal("1234.56")), ("Loja Beta", Decimal("-1234.56")), ("Loja Gama", Decimal("1234.56"))]


def test_generico_le_sinal_mais_explicito():
    f = _gen("05/01/2026 Loja Alfa +1.234,56", "06/01/2026 Loja Beta R$ +123,45", "07/01/2026 Loja Gama 10,00")
    assert [(l.estabelecimento, l.valor) for l in f.lancamentos] == [
        ("Loja Alfa", Decimal("1234.56")), ("Loja Beta", Decimal("123.45")), ("Loja Gama", Decimal("10.00"))]


def test_generico_le_valor_colado_no_texto_inteiro():
    f = _gen("05/01/2026 Unidade Centro89,90", "06/01/2026 Loja1234,56", "07/01/2026 Loja:12,34",
             "08/01/2026 Loja.....12,34", "09/01/2026 Loja(12,34)", "10/01/2026 Loja USD12,34")
    assert [l.valor for l in f.lancamentos] == [Decimal("89.90"), Decimal("1234.56"), Decimal("12.34"),
                                                 Decimal("12.34"), Decimal("-12.34"), Decimal("12.34")]
    assert f.lancamentos[0].estabelecimento == "Unidade Centro"


def test_generico_le_menos_tipografico_e_meia_risca_como_negativo():
    f = _gen("05/01/2026 Loja Alfa R$ −37,50", "06/01/2026 Loja Beta –37,50")
    assert [l.valor for l in f.lancamentos] == [Decimal("-37.50"), Decimal("-37.50")]


def test_generico_nao_comeca_no_meio_de_um_numero():
    assert _gen("05/01/2026 Loja X 12.34,56", "06/01/2026 Loja X 1234.567,89", "07/01/2026 Loja X 12,3").lancamentos == []


def _paginas_com_acento(path):
    with pdfplumber.open(path) as pdf:
        pags = [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]
    assert "CARTAO CORPORATIVO" in pags[0]["texto"]
    for p in pags:
        p["texto"] = p["texto"].replace("CARTAO", "CARTÃO")
    return pags


def test_itau_aceita_cabecalho_com_acento(tmp_path):
    f = validar_total(itau.parse(_paginas_com_acento(gpdf.gerar("itau", str(tmp_path / "i.pdf")))))
    assert f.lancamentos and f.total_fatura is not None and f.veredicto == OK  # a prova fecha, nao so "nao recusou"


def test_bradesco_aceita_cabecalho_com_acento(tmp_path):
    f = validar_total(bradesco.parse(_paginas_com_acento(gpdf.gerar("bradesco", str(tmp_path / "b.pdf")))))
    assert f.lancamentos and f.total_fatura is not None and f.veredicto == OK


def test_consolidado_soma_o_mesmo_que_as_faturas(tmp_path):
    gpdf.gerar("itau", str(tmp_path / "a.pdf"))
    gpdf.gerar("bradesco", str(tmp_path / "b.pdf"))
    processadas, _, _ = lote.processar_pasta(tmp_path)
    esperado = sum((f.total_calculado for _, f in processadas), Decimal("0.00"))
    assert all(f.encargos for _, f in processadas)

    csv_out = tmp_path / "c.csv"
    lote.exportar_csv_consolidado(processadas, csv_out)
    linhas = csv_out.read_text(encoding="utf-8-sig").splitlines()[1:]
    assert sum(Decimal(l.split(";")[6]) for l in linhas) == esperado

    xlsx_out = tmp_path / "c.xlsx"
    lote.exportar_xlsx_consolidado(processadas, lote.resumo_agregado(processadas, [], []), xlsx_out)
    ws = openpyxl.load_workbook(xlsx_out)["Lancamentos"]
    soma = sum(Decimal(str(r[6])) for r in ws.iter_rows(min_row=2, values_only=True))
    assert soma.quantize(Decimal("0.01")) == esperado


def test_generico_sinal_antes_da_moeda():
    f = _gen("05/01/2026 Estorno R$ - 1234,56", "06/01/2026 Estorno -R$ 1234,56", "07/01/2026 Loja X - R$ 12,34")
    assert [l.valor for l in f.lancamentos] == [Decimal("-1234.56"), Decimal("-1234.56"), Decimal("12.34")]
    assert f.lancamentos[0].estabelecimento == "Estorno" and f.lancamentos[1].estabelecimento == "Estorno"


def test_generico_sinal_e_parentese_colados_em_digito_como_antes():
    f = _gen("05/01/2026 Loja24-12,34", "06/01/2026 Loja24(12,34)")
    assert [l.valor for l in f.lancamentos] == [Decimal("-12.34"), Decimal("-12.34")]


def _itau(*linhas):
    cab = ["BANCO EXEMPLO ITA S.A.", "FATURA CARTAO CORPORATIVO", "Vencimento: 10/02/2026", "Portador: FULANO"]
    return validar_total(itau.parse([{"texto": NL.join(cab + list(linhas)), "words": []}]))


def test_itau_compra_e_estorno_com_sinal_lidos():
    f = _itau("05/01/2026 Loja A R$ 100,00", "06/01/2026 Loja B R$ +200,00", "07/01/2026 Estorno B R$ - 200,00",
              "Total desta fatura R$ 100,00")
    assert [l.valor for l in f.lancamentos] == [Decimal("100.00"), Decimal("200.00"), Decimal("-200.00")]
    assert f.veredicto == OK


def test_linha_com_data_nao_lida_impede_ok_mesmo_com_a_soma_fechando():
    f = _itau("05/01/2026 Loja A R$ 100,00", "06/01/2026 Loja B sem valor legivel", "Total desta fatura R$ 100,00")
    assert f.total_calculado == f.total_fatura
    assert f.veredicto == BAIXA_CONFIANCA and "1 linha(s) com data nao lida(s)" in f.aviso


def test_rede_de_seguranca_vale_para_qualquer_leitor():
    from datetime import date
    f = FaturaParsed(lancamentos=[Lancamento(date(2026, 1, 5), "Loja", Decimal("10.00"))],
                     total_fatura=Decimal("10.00"), linhas_nao_lidas=2)
    assert validar_total(f).veredicto == BAIXA_CONFIANCA and f.aviso.startswith("2 linha(s)")


def test_lote_arquivo_ilegivel_vira_excecao_e_nao_derruba(tmp_path, monkeypatch):
    gpdf.gerar("itau", str(tmp_path / "a.pdf"))
    gpdf.gerar("bradesco", str(tmp_path / "b.pdf"))
    gpdf.gerar_generico_reconhecivel(str(tmp_path / "c.pdf"))
    original = lote._hash_arquivo

    def hash_falha(p):
        if p.name == "b.pdf":
            raise PermissionError("sem permissao")
        return original(p)

    monkeypatch.setattr(lote, "_hash_arquivo", hash_falha)
    processadas, duplicatas, _ = lote.processar_pasta(tmp_path)
    assert [p.name for p, _ in processadas] == ["a.pdf", "b.pdf", "c.pdf"] and duplicatas == []
    assert processadas[1][1].aviso == "nao consegui ler o arquivo (PermissionError)"
    assert processadas[1][1].veredicto == LAYOUT_DESCONHECIDO  # o default do dataclass e OK: aqui nao pode ser

    _, _, excedentes = lote.processar_pasta(tmp_path, limite=1)
    assert [p.name for p in excedentes] == ["b.pdf", "c.pdf"]  # o arquivo ilegivel tambem respeita o limite


def test_itau_menos_colado_na_moeda_com_valor_ja_negativo():
    f = _itau("05/01/2026 Loja A R$ 122,34", "06/01/2026 Estorno B -R$ -12,34", "07/01/2026 Estorno C -R$ (10,00)",
              "Total desta fatura R$ 100,00")
    assert [l.valor for l in f.lancamentos] == [Decimal("122.34"), Decimal("-12.34"), Decimal("-10.00")]
    assert f.veredicto == OK


def test_generico_hifen_do_nome_colado_na_moeda_nao_vira_sinal():
    assert [l.valor for l in _gen("05/01/2026 Loja-R$ 3,00").lancamentos] == [Decimal("3.00")]


def test_generico_conta_linha_com_data_sem_valor():
    f = validar_total(_gen("05/01/2026 Loja A 10,00", "06/01/2026 Loja B sem valor"))
    assert f.linhas_nao_lidas == 1 and "1 linha(s) com data nao lida(s)" in f.aviso


def test_bradesco_conta_linha_com_data_sem_valor(tmp_path):
    path = gpdf.gerar("bradesco", str(tmp_path / "b.pdf"))
    with pdfplumber.open(path) as pdf:
        pags = [{"texto": pg.extract_text() or "", "words": pg.extract_words()} for pg in pdf.pages]
    data = next(w for w in pags[0]["words"] if w["text"] == "03/01/2026")
    pags[0]["words"].append(dict(data, top=data["top"] + 500, bottom=data["bottom"] + 500))  # linha so com a data
    f = validar_total(bradesco.parse(pags))
    assert f.linhas_nao_lidas == 1 and f.veredicto == BAIXA_CONFIANCA


def test_nota_da_linha_nao_lida_entra_tambem_quando_o_total_nao_fecha():
    f = _itau("05/01/2026 Loja A R$ 100,00", "06/01/2026 Loja B sem valor legivel", "Total desta fatura R$ 150,00")
    assert f.veredicto == TOTAL_NAO_FECHA and "1 linha(s) com data nao lida(s)" in f.aviso
    assert f.aviso.startswith("total nao fecha")  # a nota soma ao aviso da prova, nao o troca


def test_valor_ou_data_ilegivel_tambem_conta():
    f = _itau("05/01/2026 Loja A R$ 100,00", "06/01/2026 Loja B R$ 1,2,3", "Total desta fatura R$ 100,00")
    assert f.linhas_nao_lidas == 1 and f.veredicto == BAIXA_CONFIANCA
    assert _gen("05/01/2026 Loja A 10,00", "31/02/2026 Loja B 10,00").linhas_nao_lidas == 1
