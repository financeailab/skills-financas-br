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


# --- v0.1.2 (D3a, D3b, D4, D7, D8): excecao vira aviso, OFX sem fechamento, linha fisica ---

_CSV_BOM = "data;descricao;valor;banco\n05/01/2025;TAR PIX;-2,00;341\n"


def test_valor_gigante_vira_aviso_da_linha_e_nao_derruba(tmp_path, capsys):
    from scripts.auditar_tarifas import main
    gigante = "123456789012345678901234567"  # 27 digitos: o quantize do normalize levanta InvalidOperation
    (tmp_path / "a.csv").write_text(f"data;descricao;valor;banco\n05/01/2025;TAR PIX;{gigante};341\n05/01/2025;TAR PIX;-2,00;341\n", encoding="utf-8")
    assert main([str(tmp_path / "a.csv")]) == 0
    out, err = capsys.readouterr()
    assert "Total de tarifa no periodo: R$ 2.00" in out
    assert "aviso: a.csv: linha CSV 2 invalida ignorada (data ou valor ilegivel, ou coluna faltando)" in err
    assert gigante not in out + err
    ofx = f"<OFX>\n<STMTTRN>\n<DTPOSTED>20250110\n<TRNAMT>{gigante}\n<MEMO>TAR PIX\n</STMTTRN>\n</OFX>\n"
    assert ler_ofx(ofx) == ([], ["lancamento OFX 1 invalido ignorado (data ou valor ilegivel)"])


def test_arquivo_ilegivel_vira_aviso_e_nao_derruba_os_outros(tmp_path, capsys):
    from scripts.auditar_tarifas import main
    ruins = {
        "cr_solto": "data;descricao;valor;banco\n05/01/2025;TAR\rPIX;-2,00;341\n".encode("utf-8"),
        "campo_gigante": ("data;descricao;valor;banco\n05/01/2025;" + "A" * 131073 + ";-2,00;341\n").encode("utf-8"),
        "binario": bytes(range(256)) * 4,
    }
    for caso, bruto in ruins.items():
        pasta = tmp_path / caso
        pasta.mkdir()
        (pasta / "ruim.csv").write_bytes(bruto)
        (pasta / "bom.csv").write_text(_CSV_BOM, encoding="utf-8")
        assert main([str(pasta)]) == 0, caso
        out, err = capsys.readouterr()
        assert err == "aviso: ruim.csv: arquivo ilegivel ignorado (Error)\n", caso  # so a classe, sem a mensagem
        assert "Total de tarifa no periodo: R$ 2.00" in out, caso


_LANC_SEM_FECHO = "<STMTTRN>\n<DTPOSTED>20250110\n<TRNAMT>{}\n<MEMO>TAR PIX\n"


def test_ofx_sem_fechamento_nao_funde_lancamentos():
    ofx = "<OFX>\n<BANKTRANLIST>\n" + _LANC_SEM_FECHO.format("-7.31") + _LANC_SEM_FECHO.format("-2.21") + "</STMTTRN>\n</BANKTRANLIST>\n</OFX>\n"
    txns, avisos = ler_ofx(ofx)
    assert [t.valor for t in txns] == [Decimal("-7.31"), Decimal("-2.21")]
    assert avisos == ["1 lancamento(s) OFX sem </STMTTRN>, lido(s) ate o proximo"]


def test_ofx_sem_nenhum_fechamento_le_todos():
    corpo = "".join(_LANC_SEM_FECHO.format(v) for v in ("-1.00", "-2.00", "-3.00"))
    for fim in ("</BANKTRANLIST>\n</OFX>\n", ""):  # ultimo bloco antes do </BANKTRANLIST> e no fim do arquivo
        txns, avisos = ler_ofx("<OFX>\n<BANKTRANLIST>\n" + corpo + fim)
        assert [t.valor for t in txns] == [Decimal("-1.00"), Decimal("-2.00"), Decimal("-3.00")], fim
        assert avisos == ["3 lancamento(s) OFX sem </STMTTRN>, lido(s) ate o proximo"], fim


def test_ofx_fechado_com_tags_minusculas_nao_avisa():
    bloco = "<stmttrn>\n<dtposted>20250110\n<trnamt>{}\n<memo>TAR PIX\n</stmttrn>\n"
    ofx = "<ofx>\n<banktranlist>\n" + "".join(bloco.format(v) for v in ("-1.00", "-2.00", "-3.00")) + "</banktranlist>\n</ofx>\n"
    txns, avisos = ler_ofx(ofx)
    assert avisos == []
    assert [t.valor for t in txns] == [Decimal("-1.00"), Decimal("-2.00"), Decimal("-3.00")]


def test_aviso_de_leitura_diz_o_nome_sem_a_pasta(tmp_path):
    (tmp_path / "subdir.csv").mkdir()  # pasta com cara de extrato: o scan a lista e a leitura falha
    (tmp_path / "bom.csv").write_text(_CSV_BOM, encoding="utf-8")
    txns, avisos = ler_extratos([tmp_path])
    assert len(txns) == 1
    assert len(avisos) == 1 and avisos[0].startswith("nao foi possivel ler subdir.csv ("), avisos
    assert "/" not in avisos[0] and "\\" not in avisos[0], avisos


def test_aviso_cita_a_linha_fisica_do_registro():
    # 2 linhas em branco antes do cabecalho (linha 3) e um campo entre aspas com quebra (linhas 4 e 5)
    texto = '\n\ndata;descricao;valor;banco\n05/01/2025;"TAR\nPIX";-2,00;341\nXX;TAR PIX;-2,00;341\n'
    esperado = ["linha CSV 6 invalida ignorada (data ou valor ilegivel, ou coluna faltando)"]
    for variante in (texto, texto.replace("\n", "\r\n")):
        txns, avisos = ler_csv(variante)
        assert len(txns) == 1 and avisos == esperado, repr(variante[:6])


# --- v0.1.4 (D2, D8): lancamento sem fecho termina no agregado que o contem ou num irmao; dois bancos avisam ---

from datetime import date

_PIX_SEM_FECHO = (
    "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><BANKID>0341<ACCTID>1</BANKACCTFROM>\n<BANKTRANLIST>\n"
    "<STMTTRN><DTPOSTED>20250105<TRNAMT>-30.00<MEMO>TARIFA PACOTE SERVICOS</STMTTRN>\n"
    "<STMTTRN><DTPOSTED>20250110<TRNAMT>-5000.00<NAME>PIX ENVIADO FORNECEDOR\n"
)
_ESPERADO_D2 = [("TARIFA PACOTE SERVICOS", Decimal("-30.00")), ("PIX ENVIADO FORNECEDOR", Decimal("-5000.00"))]
_AVISO_SEM_FECHO = ["1 lancamento(s) OFX sem </STMTTRN>, lido(s) ate o proximo"]
# a lista da spec (D2), escrita aqui de novo: um terminador que falte na regex reprova
_TERMINADORES_D2 = (
    "</BANKTRANLIST>", "</STMTRS>", "</CCSTMTRS>", "</STMTTRNRS>", "</CCSTMTTRNRS>", "</BANKMSGSRSV1>",
    "</CREDITCARDMSGSRSV1>", "</OFX>", "<BANKTRANLISTP>", "<LEDGERBAL>", "<AVAILBAL>", "<CASHADVBALAMT>",
    "<INTRATE>", "<INTRATEPURCH>", "<INTRATECASH>", "<INTRATEXFER>", "<REWARDINFO>", "<BALLIST>", "<MKTGINFO>",
    "<BANKTRANLIST>", "<STMTRS>", "<CCSTMTRS>", "<STMTTRNRS>", "<CCSTMTTRNRS>", "<CREDITCARDMSGSRSV1>",
    "<INVSTMTMSGSRSV1>",
)


def test_ofx_sem_fecho_termina_em_cada_terminador_do_d2():
    for tag in _TERMINADORES_D2:
        for t in (tag, tag.lower()):
            txns, avisos = ler_ofx(_PIX_SEM_FECHO + t + "\n<MEMO>TARIFA MANUTENCAO CONTA\n")
            assert [(x.descricao, x.valor) for x in txns] == _ESPERADO_D2, t
            assert avisos == _AVISO_SEM_FECHO, t


def test_ofx_pendente_depois_do_lancamento_sem_fecho_fica_fora():
    for rs in ("STMTRS", "CCSTMTRS"):
        ofx = (_PIX_SEM_FECHO.replace("<STMTRS>", f"<{rs}>")
               + "<BANKTRANLISTP><STMTTRNP><DTTRAN>20250111<TRNAMT>-9.90<MEMO>TARIFA MANUTENCAO CONTA</STMTTRNP>"
               + f"</BANKTRANLISTP></{rs}></STMTTRNRS></BANKMSGSRSV1></OFX>\n")
        txns, avisos = ler_ofx(ofx)
        assert [(x.descricao, x.valor) for x in txns] == _ESPERADO_D2, rs
        assert avisos == _AVISO_SEM_FECHO, rs


def test_ofx_agregado_dentro_do_lancamento_nao_corta():
    internos = (
        "<PAYEE><NAME>BANCO X<ADDR1>RUA 1</PAYEE>",
        "<BANKACCTTO><BANKID>237<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTTO>",
        "<CCACCTTO><ACCTID>9</CCACCTTO>",
        "<CURRENCY><CURRATE>1.0<CURSYM>BRL</CURRENCY>",
        "<ORIGCURRENCY><CURRATE>1.0<CURSYM>BRL</ORIGCURRENCY>",
        "<IMAGEDATA><IMAGETYPE>STATEMENT<IMAGEREF>X<IMAGEREFTYPE>OPAQUE</IMAGEDATA>",
    )
    for interno in internos:
        for fecho in ("</STMTTRN>", ""):
            txns, _ = ler_ofx(f"<OFX><BANKTRANLIST><STMTTRN>{interno}<DTPOSTED>20250105<TRNAMT>-30.00"
                              f"<MEMO>TARIFA PACOTE SERVICOS{fecho}</BANKTRANLIST></OFX>")
            assert [(x.data, x.descricao, x.valor) for x in txns] == [
                (date(2025, 1, 5), "TARIFA PACOTE SERVICOS", Decimal("-30.00"))], (interno, fecho)


def test_ofx_com_dois_bancos_avisa_e_cartao_ou_ted_do_mesmo_arquivo_nao():
    def extrato(rs, conta, meio=""):
        return (f"<{rs}>{conta}<BANKTRANLIST><STMTTRN><DTPOSTED>20250105<TRNAMT>-30.00{meio}"
                f"<MEMO>TARIFA PACOTE SERVICOS</STMTTRN></BANKTRANLIST></{rs}>")
    c341 = "<BANKACCTFROM><BANKID>341<ACCTID>1</BANKACCTFROM>"
    txns, avisos = ler_ofx("<OFX>" + extrato("STMTRS", c341)
                           + extrato("STMTRS", "<BANKACCTFROM><BANKID>237<ACCTID>2</BANKACCTFROM>") + "</OFX>")
    assert [x.banco for x in txns] == ["341", "341"]
    assert avisos == ["mais de um banco no mesmo OFX; todos entram com o codigo do primeiro"]
    # comentario ou outro campo antes do BANKID: ainda e a conta do extrato
    for antes in ("<!-- conta -->", "<BRANCHID>1"):  # "0001" casaria o detector de agencia do exportar.cjs
        txns, avisos = ler_ofx("<OFX>" + extrato("STMTRS", c341) + extrato(
            "STMTRS", f"<BANKACCTFROM>{antes}<BANKID>237<ACCTID>2</BANKACCTFROM>") + "</OFX>")
        assert avisos == ["mais de um banco no mesmo OFX; todos entram com o codigo do primeiro"], antes
    txns, avisos = ler_ofx("<OFX>" + extrato("STMTRS", c341)
                           + extrato("CCSTMTRS", "<CCACCTFROM><ACCTID>3</CCACCTFROM>") + "</OFX>")
    assert [x.banco for x in txns] == ["341", "341"] and avisos == []
    # TED para outro banco: o BANKID do BANKACCTTO e o destino, nao o banco do extrato
    txns, avisos = ler_ofx("<OFX>" + extrato("STMTRS", c341, "<BANKACCTTO><BANKID>237<ACCTID>9</BANKACCTTO>")
                           + "</OFX>")
    assert [x.banco for x in txns] == ["341"] and avisos == []
