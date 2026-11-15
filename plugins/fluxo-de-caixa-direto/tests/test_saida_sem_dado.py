# -*- coding: utf-8 -*-
"""Canario da saida sem texto do arquivo (docs/decisions/saida-sem-dado.md): o que o agente le
(stdout e stderr do CLI) nunca leva texto do arquivo da pessoa. Roda o CLI de verdade, como
processo, para passar pelo ponto de entrada (_TEMPLATE_MAIN)."""
import json
import os
import re
import subprocess
import sys
import zipfile

import pytest

from conftest import SCRIPTS

CLI = os.path.join(SCRIPTS, "fluxo_caixa.py")
S = "SENTINELA"

OFX = """OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>123</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><DTPOSTED>20260701<TRNAMT>-10.00<FITID>1<MEMO>PAGAMENTO FORNECEDOR</STMTTRN>
<STMTTRN><DTPOSTED>20260702<TRNAMT>{trnamt}<FITID>2<MEMO>OUTRO</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>{balamt}<DTASOF>20260701</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def _ofx(tmp_path, balamt="100.00", trnamt="5.00"):
    p = tmp_path / "extrato.ofx"
    p.write_text(OFX.format(balamt=balamt, trnamt=trnamt), encoding="utf-8")
    return str(p)


def _roda(tmp_path, *args, pre=""):
    if pre:
        cmd = [sys.executable, "-c", pre + "\nimport runpy\n"
               f"runpy.run_path({CLI!r}, run_name='__main__')", *args]
    else:
        cmd = [sys.executable, CLI, *args]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([SCRIPTS, os.path.join(SCRIPTS, "engine")])}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(tmp_path), env=env, stdin=subprocess.DEVNULL, timeout=60)
    saida = r.stdout + r.stderr
    assert S not in saida, saida
    return r.returncode, saida


def _csv(tmp_path, nome, texto):
    p = tmp_path / nome
    p.write_text(texto, encoding="utf-8")
    return str(p)


def test_balamt_ilegivel_nao_derruba_e_vira_saldo_estimado(tmp_path):
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path, balamt=S), "--json", "--saida", "out")
    assert rc == 0, saida
    dados = json.loads((tmp_path / "out" / "fluxo-de-caixa.json").read_text(encoding="utf-8"))
    assert "SALDO_ESTIMADO" in {a["tipo"] for a in dados["alertas"]}


def test_trnamt_ilegivel_e_ignorado(tmp_path):
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path, trnamt=S), "--json", "--saida", "out")
    assert rc == 0, saida
    assert "1 lancamento(s)" in saida
    assert "1 lancamento(s) ignorado(s) por data ou valor ilegivel" in saida  # nunca some calado
    dados = json.loads((tmp_path / "out" / "fluxo-de-caixa.json").read_text(encoding="utf-8"))
    assert "LANCAMENTO_ILEGIVEL" in {a["tipo"] for a in dados["alertas"]}


def test_todos_os_lancamentos_ilegiveis_dizem_quantos(tmp_path):
    """Gate 2, passe 4: com todos ilegiveis, o erro dizia "nenhum lancamento lido" e a contagem sumia."""
    p = tmp_path / "extrato.ofx"
    p.write_text(OFX.format(balamt="100.00", trnamt=S).replace("<TRNAMT>-10.00", f"<TRNAMT>{S}"),
                 encoding="utf-8")
    rc, saida = _roda(tmp_path, "--extratos", str(p), "--saida", "out")
    assert rc == 3
    assert "2 ignorado(s) por data ou valor ilegivel" in saida


def test_cabecalho_do_csv_nao_sai(tmp_path):
    pagar = _csv(tmp_path, "pagar.csv", f"{S}_COL;outra\nx;y\n")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--pagar", pagar, "--saida", "out")
    assert rc == 2
    assert "vencimento, valor" in saida and "2 coluna(s)" in saida


def test_celula_de_vencimento_e_nome_do_arquivo_nao_saem(tmp_path):
    os.makedirs(tmp_path / S)
    _csv(tmp_path, os.path.join(S, "pagar.csv"), f"fornecedor;vencimento;valor\nACME;{S};10,00\n")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--pagar", os.path.join(S, "pagar.csv"),
                      "--saida", "out")
    assert rc == 2
    assert "linha 2 do arquivo de titulos a pagar: vencimento ilegivel" in saida


def test_celula_de_valor_nao_sai(tmp_path):
    receber = _csv(tmp_path, "receber.csv", f"cliente;vencimento;valor\nACME;10/08/2026;{S}\n")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--receber", receber, "--saida", "out")
    assert rc == 2
    assert "linha 2 do arquivo de titulos a receber: valor ilegivel" in saida


def test_xlsx_corrompido_nao_sai(tmp_path):
    (tmp_path / "pagar.xlsx").write_text(S * 50, encoding="utf-8")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--pagar", "pagar.xlsx", "--saida", "out")
    assert rc == 2
    assert "nao consegui ler o arquivo de titulos a pagar" in saida


def test_warning_do_openpyxl_nao_leva_o_nome_definido(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["fornecedor", "vencimento", "valor"])
    ws.append(["ACME", "10/08/2026", "10,00"])
    bruto = tmp_path / "bruto.xlsx"
    wb.save(bruto)
    # nome definido invalido (achado do Gate 1A): o openpyxl avisa com o texto dele no stderr
    with zipfile.ZipFile(bruto) as zin, zipfile.ZipFile(tmp_path / "pagar.xlsx", "w") as zout:
        for item in zin.infolist():
            dados = zin.read(item.filename)
            if item.filename == "xl/workbook.xml":
                # sem lxml (CI do Python 3.10) o openpyxl grava "<definedNames />", com espaco (Gate 2, passe 3)
                dados, n = re.subn(rb"<definedNames\s*/>", b'<definedNames><definedName name="_xlnm.Print_Area" '
                                   b'localSheetId="0">' + S.encode() + b"_CONTRAPARTE</definedName></definedNames>", dados)
                assert n == 1
            zout.writestr(item, dados)
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--pagar", "pagar.xlsx", "--json", "--saida", "out")
    assert rc == 0, saida
    assert "detalhe omitido" in saida  # o warning existiu e saiu com texto fixo


def test_dicionario_ilegivel_nao_sai(tmp_path):
    (tmp_path / "dic.csv").write_bytes(b"categoria,keyword\nFornecedores," + S.encode() + b"\xe9\xff\n")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--dicionario", "dic.csv", "--saida", "out")
    assert rc == 2
    assert "dicionario de categorias ilegivel" in saida


def test_excecao_inesperada_cai_no_template(tmp_path):
    pre = ("import dfc\n"
           "def _explode(*a, **k):\n"
           f"    raise RuntimeError({S!r})\n"
           "dfc.montar = _explode")
    rc, saida = _roda(tmp_path, "--extratos", _ofx(tmp_path), "--saida", "out", pre=pre)
    assert rc == 2
    assert "erro inesperado" in saida
