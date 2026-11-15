# -*- coding: utf-8 -*-
"""ingest_ofx.py: parse OFX 1.x SGML e 2.x XML, multi-arquivo = multi-conta,
dedup por (conta_id, FITID) (invariante #4 da SPEC §8), mais o teste de ACEITE
REVERSO: o OFX emitido pelo conversor-extrato precisa ser lido por este motor
(SPEC-00 §9)."""
import os
import sys
from decimal import Decimal

import pytest

import gen_vectors as gv
from ingest_ofx import ingest_extratos, parse_ofx_text
from conftest import CONVERSOR_ENGINE


def _grava(tmp_path, nome, conteudo):
    p = tmp_path / nome
    p.write_text(conteudo, encoding="utf-8")
    return str(p)


def test_parse_ofx_text_simples_sgml():
    ext = parse_ofx_text(gv.ofx_conta_a())
    assert ext.banco == "341"
    assert ext.agencia == "1234"
    assert ext.conta == "11111-1"
    assert len(ext.transacoes) == 16
    assert ext.saldo_final == Decimal("58000.00")
    assert str(ext.data_saldo) == "2026-07-19"
    t0 = ext.transacoes[0]
    assert t0["fitid"] == "CCA0001"
    assert t0["valor"] == Decimal("15000.00")
    assert t0["descricao"] == "PIX RECEBIDO CLIENTE ACME LTDA"
    assert str(t0["data"]) == "2026-05-26"


def test_parse_ofx_text_xml_2x():
    ext = parse_ofx_text(gv.ofx_conta_xml_2x())
    assert ext.conta == "77777-7"
    assert len(ext.transacoes) == 1
    assert ext.transacoes[0]["valor"] == Decimal("250.00")
    # entidade XML decodificada (achado do Gate 2): SAL&#193;RIO vira SALÁRIO
    ext_ent = parse_ofx_text(gv.ofx_conta_xml_2x().replace(
        ext.transacoes[0]["descricao"], "SAL&#193;RIO &amp; CIA", 1))
    assert ext_ent.transacoes[0]["descricao"] == "SALÁRIO & CIA"
    # "&" cru do SGML sem ";" fica como esta (Gate 2, passe 3): nada de JOSE®INA ou TAR©SERV
    for cru in ("PAG JOSE&REGINA LTDA", "TAR&COPYSERV", "PAG TED M&LTDA"):
        ext_cru = parse_ofx_text(gv.ofx_conta_xml_2x().replace(ext.transacoes[0]["descricao"], cru, 1))
        assert ext_cru.transacoes[0]["descricao"] == cru
    assert ext.saldo_final == Decimal("250.00")


def test_ingest_multi_arquivo_multi_conta(tmp_path):
    pa = _grava(tmp_path, "conta_a.ofx", gv.ofx_conta_a())
    pb = _grava(tmp_path, "conta_b.ofx", gv.ofx_conta_b())

    res = ingest_extratos([pa, pb])

    assert len(res.lancamentos) == gv.total_transacoes_realizadas()
    contas_ids = {l["conta_id"] for l in res.lancamentos}
    # conta_id qualificado por banco, rotulo BANKID/ACCTID (achado Codex P1)
    assert contas_ids == {"341/1234/11111-1", "001/5678/22222-2"}
    assert set(res.contas.keys()) == {"341/1234/11111-1", "001/5678/22222-2"}
    assert res.contas["341/1234/11111-1"].saldo_final == Decimal(gv.SALDO_FINAL_CONTA_A)
    assert res.contas["001/5678/22222-2"].saldo_final == Decimal(gv.SALDO_FINAL_CONTA_B)
    assert str(res.contas["341/1234/11111-1"].data_saldo) == "2026-07-19"


def test_ingest_dedup_mesmo_arquivo_2x(tmp_path):
    pa = _grava(tmp_path, "conta_a.ofx", gv.ofx_conta_a())

    res_1x = ingest_extratos([pa])
    res_2x = ingest_extratos([pa, pa])

    assert len(res_2x.lancamentos) == len(res_1x.lancamentos)

    # sem FITID nao ha como saber se e repetido: entra sempre, em quantos arquivos vier (achado do Gate 2)
    sem_fitid = _ofx_saldo("9", "100.00", "20260731", "").replace("<FITID>", "")
    arquivos = [_grava(tmp_path, f"sf{i}.ofx", sem_fitid) for i in range(3)]
    assert len(ingest_extratos(arquivos).lancamentos) == 3


def test_ingest_pasta_varre_ofx_e_ignora_outros(tmp_path):
    _grava(tmp_path, "conta_a.ofx", gv.ofx_conta_a())
    _grava(tmp_path, "leia-me.txt", "nao e extrato")

    res = ingest_extratos([str(tmp_path)])

    assert len(res.lancamentos) == 16
    assert len(res.arquivos_ignorados) == 1
    assert res.arquivos_ignorados[0].endswith("leia-me.txt")


def test_ingest_pasta_vazia_retorna_zero_lancamentos(tmp_path):
    res = ingest_extratos([str(tmp_path)])
    assert res.lancamentos == []


def test_ingest_conta_sem_ledgerbal_fica_sem_saldo(tmp_path):
    p = _grava(tmp_path, "sem_saldo.ofx", gv.ofx_sem_ledgerbal())
    res = ingest_extratos([p])
    conta = res.contas["237/0001/99999-9"]
    assert conta.saldo_final is None
    assert conta.data_saldo is None


def test_bancos_diferentes_mesmo_acctid_nao_fundem_contas(tmp_path):
    """Achado Codex P1: chave de conta so por ACCTID funde contas de bancos
    diferentes (LEDGERBAL de um suprime o do outro; FITID coincidente descarta
    lancamento valido). A chave tem que ser qualificada por banco (BANKID+ACCTID),
    inclusive no dedup."""
    ofx_itau, ofx_bradesco = gv.ofx_mesmo_acctid_bancos_diferentes()
    pi = _grava(tmp_path, "itau.ofx", ofx_itau)
    pb = _grava(tmp_path, "bradesco.ofx", ofx_bradesco)

    res = ingest_extratos([pi, pb])

    # as 2 contas aparecem separadas (nao fundem), com rotulo legivel BANKID/ACCTID
    assert len(res.contas) == 2
    assert set(res.contas.keys()) == {"341/0001/12345-6", "237/0002/12345-6"}

    # os 2 LEDGERBALs sobrevivem (nenhum suprime o outro) e somam no saldo inicial
    assert res.contas["341/0001/12345-6"].saldo_final == Decimal("100.00")
    assert res.contas["237/0002/12345-6"].saldo_final == Decimal("200.00")

    # nenhum lancamento descartado: o FITID DUP001 existe nos 2 bancos e sao
    # lancamentos DIFERENTES (dedup e por conta qualificada, nao cross-banco)
    assert len(res.lancamentos) == 3
    fitids_por_conta = {}
    for l in res.lancamentos:
        fitids_por_conta.setdefault(l["conta_id"], set()).add(l["fitid"])
    assert "DUP001" in fitids_por_conta["341/0001/12345-6"]
    assert "DUP001" in fitids_por_conta["237/0002/12345-6"]

    # mesmo banco e mesmo ACCTID em agencias diferentes tambem nao fundem (achado do Gate 2)
    pa1 = _grava(tmp_path, "ag1.ofx", ofx_itau)
    pa2 = _grava(tmp_path, "ag2.ofx", ofx_itau.replace("<BRANCHID>0001", "<BRANCHID>0009")
                 .replace("<BALAMT>100.00", "<BALAMT>200.00"))
    res_ag = ingest_extratos([pa1, pa2])
    assert set(res_ag.contas) == {"341/0001/12345-6", "341/0009/12345-6"}
    assert sum(c.saldo_final for c in res_ag.contas.values()) == Decimal("300.00")

    # so BANKID x so BRANCHID com o mesmo valor: a posicao na chave separa as contas (Gate 2, passe 2)
    so_banco = _grava(tmp_path, "so-banco.ofx", ofx_itau.replace("<BRANCHID>0001</BRANCHID>", "")
                      .replace("<BANKID>341", "<BANKID>0341"))
    so_ag = _grava(tmp_path, "so-ag.ofx", ofx_itau.replace("<BANKID>341</BANKID>", "")
                   .replace("<BRANCHID>0001", "<BRANCHID>0341").replace("<BALAMT>100.00", "<BALAMT>200.00"))
    for ordem in ([so_banco, so_ag], [so_ag, so_banco]):
        r = ingest_extratos(ordem)
        assert set(r.contas) == {"0341//12345-6", "/0341/12345-6"}, ordem
        assert sum(c.saldo_final for c in r.contas.values()) == Decimal("300.00")
        assert len(r.lancamentos) == 4  # 2 por conta, inclusive os de FITID coincidente

    # e o dedup continua valendo DENTRO da mesma conta qualificada
    res_2x = ingest_extratos([pi, pi, pb])
    assert len(res_2x.lancamentos) == 3


def test_aceite_reverso_conversor_extrato_emite_e_nos_lemos(tmp_path):
    """Promessa do produto (SPEC-00 §9): o OFX que o Conversor de Extrato emite
    precisa ser lido por este motor sem perda."""
    if not os.path.isdir(CONVERSOR_ENGINE):
        pytest.skip("o Conversor de Extrato nao esta neste repositorio (so no monorepo)")
    sys.path.insert(0, CONVERSOR_ENGINE)
    from modelo import ExtratoParsed, Lancamento          # noqa: E402
    from emit_ofx import emit                              # noqa: E402
    import datetime as dt

    extrato = ExtratoParsed(
        banco="341", banco_nome="itau", agencia="1234", conta="56789-0",
        saldo_inicial=Decimal("1000.00"),
        saldo_final=Decimal("1180.50"),
        periodo=(dt.date(2026, 1, 5), dt.date(2026, 1, 20)),
        lancamentos=[
            Lancamento(dt.date(2026, 1, 5), Decimal("500.00"), "PIX recebido Fulano"),
            Lancamento(dt.date(2026, 1, 10), Decimal("-300.00"), "Boleto pago"),
            Lancamento(dt.date(2026, 1, 15), Decimal("30.50"), "Rendimento poupanca"),
            Lancamento(dt.date(2026, 1, 20), Decimal("-50.00"), "Tarifa manutencao"),
        ],
    )
    ofx_texto = emit(extrato)
    p = tmp_path / "emitido_pelo_conversor.ofx"
    p.write_text(ofx_texto, encoding="utf-8")

    res = ingest_extratos([str(p)])

    assert len(res.lancamentos) == len(extrato.lancamentos)
    soma = sum((l["valor"] for l in res.lancamentos), Decimal("0.00"))
    assert abs(soma - extrato.total) <= Decimal("0.01")
    conta = res.contas["341/1234/56789-0"]
    assert conta.saldo_final == extrato.saldo_final
    assert conta.banco == extrato.banco
    assert conta.agencia == extrato.agencia


def _ofx_saldo(acct, balamt, dtasof, fitid):
    return (f"OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>{acct}"
            f"</BANKACCTFROM>\n<BANKTRANLIST><STMTTRN><DTPOSTED>{dtasof}<TRNAMT>-10.00<FITID>{fitid}<MEMO>X"
            f"</STMTTRN></BANKTRANLIST>\n<LEDGERBAL><BALAMT>{balamt}<DTASOF>{dtasof}</LEDGERBAL>"
            f"</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n")


def test_saldo_mais_recente_ilegivel_nao_herda_o_saldo_antigo(tmp_path):
    """Dois OFX da mesma conta: o de julho com saldo legivel, o de agosto com BALAMT ilegivel.
    Nas duas ordens de leitura, a conta fica sem saldo (vira SALDO_ESTIMADO no DFC), com a data de agosto."""
    velho = _grava(tmp_path, "a-julho.ofx", _ofx_saldo("9", "500.00", "20260731", "J1"))
    novo = _grava(tmp_path, "b-agosto.ofx", _ofx_saldo("9", "ILEGIVEL", "20260831", "A1"))
    for ordem in ([velho, novo], [novo, velho]):
        conta = ingest_extratos(ordem).contas["001//9"]
        assert conta.saldo_final is None, ordem
        assert str(conta.data_saldo) == "2026-08-31"
    # BALAMT ilegivel e DTASOF ilegivel: sem data nao da para ordenar, entao o saldo antigo tambem nao vale
    sem_data = _grava(tmp_path, "c-sem-data.ofx",
                      _ofx_saldo("9", "ILEGIVEL", "20260831", "S1").replace("<DTASOF>20260831", "<DTASOF>XX"))
    for ordem in ([velho, sem_data], [sem_data, velho]):
        assert ingest_extratos(ordem).contas["001//9"].saldo_final is None, ordem
    # BALAMT vazio no mais recente vale como ilegivel (achado do Gate 2)
    vazio = _grava(tmp_path, "d-vazio.ofx", _ofx_saldo("9", "", "20260831", "V1"))
    for ordem in ([velho, vazio], [vazio, velho]):
        assert ingest_extratos(ordem).contas["001//9"].saldo_final is None, ordem


def test_saldo_legivel_mais_recente_vence_o_ilegivel_antigo(tmp_path):
    velho = _grava(tmp_path, "a-julho.ofx", _ofx_saldo("9", "ILEGIVEL", "20260731", "J1"))
    novo = _grava(tmp_path, "b-agosto.ofx", _ofx_saldo("9", "700.00", "20260831", "A1"))
    for ordem in ([velho, novo], [novo, velho]):
        assert ingest_extratos(ordem).contas["001//9"].saldo_final == Decimal("700.00"), ordem


def test_ofx_com_duas_contas_no_mesmo_arquivo_e_recusado(tmp_path):
    """Achado do Gate 2: o parser e de uma conta por arquivo; com duas, os lancamentos da 2a iam para a 1a."""
    from recusa import Recusa
    um = _ofx_saldo("9", "100.00", "20260731", "A1")
    dois = um.replace("</STMTRS>", "</STMTRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>8</BANKACCTFROM>"
                      "<LEDGERBAL><BALAMT>200.00<DTASOF>20260731</LEDGERBAL></STMTRS>", 1)
    p = _grava(tmp_path, "duas.ofx", dois)
    with pytest.raises(Recusa) as exc:
        ingest_extratos([p])
    assert "mais de uma conta" in str(exc.value) and "duas.ofx" not in str(exc.value)


def test_extrato_fora_de_reais_e_recusado(tmp_path):
    """Achado do Gate 2: USD entrava somado como real. A mensagem nao repete a moeda do arquivo."""
    from recusa import Recusa
    p = _grava(tmp_path, "usd.ofx", _ofx_saldo("9", "200.00", "20260731", "U1").replace(
        "<STMTRS>", "<STMTRS><CURDEF>XYZSENTINELA", 1))
    with pytest.raises(Recusa) as exc:
        ingest_extratos([p])
    assert "BRL" in str(exc.value) and "SENTINELA" not in str(exc.value)


def test_conta_e_cartao_no_mesmo_arquivo_e_recusado(tmp_path):
    """Gate 2, passe 3: CCSTMTRS (cartao) passava a trava e a compra do cartao virava debito da conta."""
    from recusa import Recusa
    um = _ofx_saldo("9", "100.00", "20260731", "A1")
    com_cartao = um.replace("</STMTRS>", "</STMTRS><CCSTMTRS><CCACCTFROM><ACCTID>CARTAO1</CCACCTFROM>"
                            "<BANKTRANLIST><STMTTRN><DTPOSTED>20260731<TRNAMT>-999.00<FITID>C1<MEMO>X"
                            "</STMTTRN></BANKTRANLIST></CCSTMTRS>", 1)
    with pytest.raises(Recusa):
        ingest_extratos([_grava(tmp_path, "conta-cartao.ofx", com_cartao)])


def test_mesmo_arquivo_pela_pasta_e_pelo_caminho_le_uma_vez(tmp_path):
    """Gate 2, passe 3: sem FITID nao ha dedup; o mesmo arquivo alcancado duas vezes contava em dobro."""
    pasta = tmp_path / "extratos"
    pasta.mkdir()
    p = _grava(pasta, "sf.ofx", _ofx_saldo("9", "100.00", "20260731", "").replace("<FITID>", ""))
    res = ingest_extratos([str(pasta), p, os.path.join(str(pasta), ".", "sf.ofx")])
    assert len(res.lancamentos) == 1 and len(res.arquivos_lidos) == 1


def test_lancamento_ilegivel_e_contado_por_conta(tmp_path):
    """Gate 2, passe 3: STMTTRN sem data, ou com valor ilegivel, era descartado sem aviso."""
    txt = _ofx_saldo("9", "100.00", "20260731", "A1").replace(
        "</BANKTRANLIST>", "<STMTTRN><DTPOSTED>20260731<TRNAMT>1,5.00<FITID>A2<MEMO>Y</STMTTRN>"
        "<STMTTRN><TRNAMT>-5.00<FITID>A3<MEMO>Z</STMTTRN></BANKTRANLIST>", 1)
    res = ingest_extratos([_grava(tmp_path, "a.ofx", txt)])
    assert len(res.lancamentos) == 1
    assert res.ilegiveis == {"001//9": 2}
