# -*- coding: utf-8 -*-
"""50 testes END-TO-END da Conciliacao Bancaria: exercitam os FLUXOS REAIS
(CLI conciliar.py: validar | conciliar | pasta | posicao + dispatcher ingest_extrato)
com fixtures temporarias, do jeito que o analista usa. Garantem que o produto inteiro
funciona, nao so as pecas.

CI-safe: casos que dependem de openpyxl/pdfplumber/Tesseract PULAM se a lib faltar
(o job de conciliacao roda stdlib-pura). OFX/CSV/TXT/HTML rodam sempre.

Rodar:  python tests/test_e2e.py
"""
import io
import json
import os
import sys
import tempfile
import shutil
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

import conciliar                                  # noqa: E402
from ingest_extrato import ingest_extrato, ocr_disponivel  # noqa: E402


def _has(mod):
    try:
        __import__(mod); return True
    except Exception:
        return False


HAS_XLSX = _has("openpyxl")
HAS_XLRD = _has("xlrd")
HAS_PDF = _has("pdfplumber")
HAS_OCR = ocr_disponivel()

casos = []
_tmps = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


# ---------------- helpers de fixture ----------------
def _tmp():
    d = tempfile.mkdtemp(prefix="e2e_"); _tmps.append(d); return d


def _w(path, content, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if binary else "w"
    with open(path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
        f.write(content)
    return path


def _ofx(linhas, saldo="0.00", banco="0341", acct="9", tipo="CHECKING", duas_contas=False):
    corpo = "\n".join(
        f"<STMTTRN><DTPOSTED>{d}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
        for i, (d, v, m) in enumerate(linhas, 1))
    extra = ""
    if duas_contas:
        extra = ("<STMTTRNRS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<ACCTID>8<ACCTTYPE>SAVINGS"
                 "</BANKACCTFROM><BANKTRANLIST><STMTTRN><DTPOSTED>20260105<TRNAMT>10.00<FITID>Z"
                 "<MEMO>OUTRA</STMTTRN></BANKTRANLIST></STMTRS></STMTTRNRS>")
    return (f"OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
            f"<BANKACCTFROM><BANKID>{banco}<ACCTID>{acct}<ACCTTYPE>{tipo}</BANKACCTFROM>"
            f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
            f"<LEDGERBAL><BALAMT>{saldo}<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS>"
            f"{extra}</BANKMSGSRSV1></OFX>")


_H = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _razao(linhas):
    """linhas: list de tuplas (data, valor[, contraparte, cnpj, historico, lote, doc])."""
    out = [_H]
    for t in linhas:
        data, valor = t[0], t[1]
        contr = t[2] if len(t) > 2 else ""
        cnpj = t[3] if len(t) > 3 else ""
        hist = t[4] if len(t) > 4 else ""
        lote = t[5] if len(t) > 5 else ""
        doc = t[6] if len(t) > 6 else ""
        out.append(f"{data};{valor};{doc};;{contr};{cnpj};{hist};{lote}")
    return "\n".join(out) + "\n"


def _run(argv):
    """Roda o CLI conciliar.py (suprime stdout) e devolve o exit code."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = conciliar.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc if rc is not None else 0


def _resumo(out):
    with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
        return json.load(f)


def _conciliar(linhas_ofx, linhas_razao, saldo_razao="0,00", saldo_ofx="0.00", extra=None):
    """Monta extrato OFX + razao e roda 'conciliar'. Retorna (rc, resumo, out_dir)."""
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx(linhas_ofx, saldo=saldo_ofx))
    raz = _w(os.path.join(d, "r.csv"), _razao(linhas_razao))
    out = os.path.join(d, "out")
    argv = ["conciliar", "--extrato", ofx, "--razao", raz, "--saldo-razao", saldo_razao, "--out", out]
    if extra:
        argv += extra
    rc = _run(argv)
    res = _resumo(out) if os.path.exists(os.path.join(out, "resumo.json")) else None
    return rc, res, out


# ============================================================================
# A. FLUXO conciliar (OFX + razao) — stdlib-safe, roda sempre
# ============================================================================
@caso("01 conciliar: tudo casa -> exit 0, resumo.json escrito")
def _():
    rc, res, _ = _conciliar([("20260102", "-100.00", "PAGTO A")], [("02/01/2026", "-100,00")])
    assert rc == 0 and res is not None, rc


@caso("02 conciliar: taxa 100% quando todos os lancamentos batem")
def _():
    _, res, _ = _conciliar([("20260102", "-100.00", "A"), ("20260103", "-50.00", "B")],
                           [("02/01/2026", "-100,00"), ("03/01/2026", "-50,00")])
    assert res["taxa_conciliacao_pct"] == 100.0, res["taxa_conciliacao_pct"]


@caso("03 conciliar: status CONCILIADO contado")
def _():
    _, res, _ = _conciliar([("20260102", "-100.00", "A")], [("02/01/2026", "-100,00")])
    assert res["contagem_por_status"].get("CONCILIADO") == 1, res["contagem_por_status"]


@caso("04 conciliar: debito so no banco -> PENDENTE_EXTRATO")
def _():
    _, res, _ = _conciliar([("20260102", "-9.90", "TARIFA PACOTE")], [("02/01/2026", "-100,00")])
    assert res["contagem_por_status"].get("PENDENTE_EXTRATO", 0) >= 1, res["contagem_por_status"]


@caso("05 conciliar: lancamento so no razao -> PENDENTE_RAZAO")
def _():
    _, res, _ = _conciliar([("20260102", "-100.00", "A")],
                           [("02/01/2026", "-100,00"), ("05/01/2026", "-430,00", "", "", "Cheque 5004")])
    assert res["contagem_por_status"].get("PENDENTE_RAZAO", 0) == 1, res["contagem_por_status"]


@caso("06 conciliar: diferenca de centavos c/ afinidade -> CONCILIADO_COM_DIFERENCA")
def _():
    _, res, _ = _conciliar([("20260102", "-100.07", "FORNEC ALFA")],
                           [("02/01/2026", "-100,00", "FORNEC ALFA")], extra=["--tolerancia", "0,10"])
    assert res["contagem_por_status"].get("CONCILIADO_COM_DIFERENCA") == 1, res["contagem_por_status"]


@caso("07 conciliar: diferenca SEM afinidade NAO casa (fica pendente)")
def _():
    _, res, _ = _conciliar([("20260102", "-8.40", "TARIFA AVULSA")],
                           [("02/01/2026", "-8.35", "DESPESA ESCRITORIO")])
    assert res["contagem_por_status"].get("CONCILIADO_COM_DIFERENCA", 0) == 0, res["contagem_por_status"]
    assert res["contagem_por_status"].get("PENDENTE_EXTRATO", 0) == 1, res["contagem_por_status"]


@caso("08 conciliar: lote conservador (mesma contraparte) -> CONCILIADO_LOTE")
def _():
    _, res, _ = _conciliar(
        [("20260116", "-78517.30", "LIQUIDACAO CONTRATO")],
        [("16/01/2026", "-55000,00", "BANCO EXEMPLO", "01233144000150"),
         ("16/01/2026", "-23517,30", "BANCO EXEMPLO", "01233144000150")])
    assert res["contagem_por_status"].get("CONCILIADO_LOTE") == 1, res["contagem_por_status"]


@caso("09 conciliar: lote multi-contraparte por remessa (coluna Lote)")
def _():
    _, res, _ = _conciliar(
        [("20260116", "-100.00", "SISPAG FORNECEDORES")],
        [("16/01/2026", "-60,00", "FORN A", "11111111000111", "", "SISPAG-9"),
         ("16/01/2026", "-40,00", "FORN B", "22222222000122", "", "SISPAG-9")])
    assert res["contagem_por_status"].get("CONCILIADO_LOTE") == 1, res["contagem_por_status"]


@caso("10 conciliar: debito SISPAG sem razao -> categoria LOTE_SISPAG")
def _():
    _, res, _ = _conciliar([("20260116", "-5000.00", "SISPAG FORNECEDORES")], [("02/01/2026", "-1,00")])
    assert "LOTE_SISPAG" in (res.get("pendencias_por_categoria") or {}), res.get("pendencias_por_categoria")


@caso("11 conciliar: controle_lote presente quando ha debito de lote pendente")
def _():
    _, res, _ = _conciliar([("20260116", "-5000.00", "SISPAG FORNECEDORES")],
                           [("16/01/2026", "-3000,00", "X"), ("16/01/2026", "-1800,00", "Y")])
    assert res.get("controle_lote") is not None, res.get("controle_lote")


@caso("12 conciliar: --saldo-extrato override (BALAMT=0) calcula amarracao")
def _():
    rc, res, _ = _conciliar([("20260102", "-100.00", "A")], [("02/01/2026", "-100,00")],
                            saldo_ofx="0,00", extra=["--saldo-extrato=-100,00"])
    assert res.get("amarracao") is not None, res.get("amarracao")


@caso("13 conciliar: BALAMT=0 sem override -> amarracao nao calculada, exit 0")
def _():
    rc, res, _ = _conciliar([("20260102", "-100.00", "A")], [("02/01/2026", "-100,00")], saldo_ofx="0,00")
    assert rc == 0 and res.get("amarracao") is None, (rc, res.get("amarracao"))


@caso("14 conciliar: amarracao FECHA (residuo 0) -> integridade_ok")
def _():
    # -100 casa (pend_raz=0); -9,90 tarifa fica pendente no extrato.
    # amarracao: saldo_razao(175) + pend_ext(-9,90) - pend_raz(0) = 165,10 == saldo_ext
    rc, res, _ = _conciliar([("20260102", "-100.00", "FORNEC"), ("20260105", "-9.90", "TARIFA")],
                            [("02/01/2026", "-100,00", "FORNEC")],
                            saldo_razao="175,00", saldo_ofx="165.10")
    assert res["integridade_ok"] is True, res.get("amarracao")


@caso("15 conciliar: amarracao NAO fecha -> exit 3")
def _():
    rc, res, _ = _conciliar([("20260102", "-100.00", "TARIFA")], [("02/01/2026", "-1,00")],
                            saldo_razao="999,00", saldo_ofx="50.00")
    assert rc == 3, rc


@caso("16 conciliar: OFX multi-conta -> validar reprova (exit 2)")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")], duas_contas=True))
    raz = _w(os.path.join(d, "r.csv"), _razao([("02/01/2026", "-100,00")]))
    rc = _run(["conciliar", "--extrato", ofx, "--razao", raz, "--saldo-razao", "0,00",
               "--out", os.path.join(d, "out")])
    assert rc == 2, rc


@caso("17 conciliar: classificacao RENDIMENTO (credito de rendimento)")
def _():
    _, res, _ = _conciliar([("20260131", "12.34", "RENDIMENTO APLIC")], [("02/01/2026", "-1,00")])
    assert "RENDIMENTO" in (res.get("pendencias_por_categoria") or {}), res.get("pendencias_por_categoria")


@caso("18 conciliar: classificacao PIX_ORFAO (credito pix sem id)")
def _():
    _, res, _ = _conciliar([("20260110", "500.00", "PIX RECEBIDO")], [("02/01/2026", "-1,00")])
    assert "PIX_ORFAO" in (res.get("pendencias_por_categoria") or {}), res.get("pendencias_por_categoria")


@caso("19 conciliar: classificacao TARIFA_IOF (debito tarifa)")
def _():
    _, res, _ = _conciliar([("20260105", "-30.00", "TARIFA MANUTENCAO CONTA")], [("02/01/2026", "-1,00")])
    assert "TARIFA_IOF" in (res.get("pendencias_por_categoria") or {}), res.get("pendencias_por_categoria")


@caso("20 conciliar: --janela casa lancamento defasado (D+2)")
def _():
    _, res, _ = _conciliar([("20260104", "-100.00", "FORNEC")], [("02/01/2026", "-100,00", "FORNEC")],
                           extra=["--janela", "3"])
    assert res["contagem_por_status"].get("CONCILIADO") == 1, res["contagem_por_status"]


@caso("21 conciliar: fora da janela NAO casa")
def _():
    _, res, _ = _conciliar([("20260120", "-100.00", "FORNEC")], [("02/01/2026", "-100,00", "FORNEC")],
                           extra=["--janela", "3"])
    assert res["contagem_por_status"].get("CONCILIADO", 0) == 0, res["contagem_por_status"]


@caso("22 conciliar: razao com linha ruim (subtotal) -> reprova com mensagem")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")]))
    raz = _w(os.path.join(d, "r.csv"), _H + "\n02/01/2026;-100,00;;;;;;\nSUBTOTAL;;;;;;;\n")
    rc = _run(["conciliar", "--extrato", ofx, "--razao", raz, "--saldo-razao", "0,00",
               "--out", os.path.join(d, "out")])
    assert rc == 2, rc


@caso("23 conciliar: extrato sem transacoes -> reprova")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([]))
    raz = _w(os.path.join(d, "r.csv"), _razao([("02/01/2026", "-100,00")]))
    rc = _run(["conciliar", "--extrato", ofx, "--razao", raz, "--saldo-razao", "0,00",
               "--out", os.path.join(d, "out")])
    assert rc == 2, rc


@caso("24 conciliar: resumo.json NAO vaza linha de transacao (so agregados)")
def _():
    _, res, _ = _conciliar([("20260102", "-100.00", "SEGREDO LTDA")], [("02/01/2026", "-100,00")])
    blob = json.dumps(res, ensure_ascii=False)
    assert "SEGREDO" not in blob and "lancamentos" not in res, "vazou dado bruto"


# ============================================================================
# B. FLUXO validar
# ============================================================================
@caso("25 validar: arquivos comparaveis -> exit 0")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")]))
    raz = _w(os.path.join(d, "r.csv"), _razao([("02/01/2026", "-100,00")]))
    assert _run(["validar", "--extrato", ofx, "--razao", raz]) == 0


@caso("26 validar: razao sem coluna Valor -> reprova (exit 2)")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")]))
    raz = _w(os.path.join(d, "r.csv"), "Data;Foo;Bar\n02/01/2026;x;y\n")
    assert _run(["validar", "--extrato", ofx, "--razao", raz]) == 2


@caso("27 validar: --col-* mapeia colunas fora do padrao")
def _():
    d = _tmp()
    ofx = _w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")]))
    raz = _w(os.path.join(d, "r.csv"), "Quando;Quanto\n02/01/2026;-100,00\n")
    assert _run(["validar", "--extrato", ofx, "--razao", raz, "--col-data", "Quando",
                 "--col-valor", "Quanto"]) == 0


@caso("28 validar: extrato inexistente -> reprova")
def _():
    d = _tmp()
    raz = _w(os.path.join(d, "r.csv"), _razao([("02/01/2026", "-100,00")]))
    assert _run(["validar", "--extrato", os.path.join(d, "nao_existe.ofx"), "--razao", raz]) == 2


# ============================================================================
# C. DISPATCHER ingest_extrato (lado banco multi-formato)
# ============================================================================
@caso("29 ingest: OFX -> OK com transacoes")
def _():
    d = _tmp()
    r = ingest_extrato(_w(os.path.join(d, "e.ofx"), _ofx([("20260102", "-100.00", "A")])))
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("30 ingest: CSV valor com sinal -> OK")
def _():
    d = _tmp()
    csv = "Data;Histórico;Valor (R$);Saldo (R$)\n02/01/2026;PAGTO;-100,00;0,00\n"
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("31 ingest: CSV credito/debito separados (Bradesco-like) -> OK")
def _():
    d = _tmp()
    csv = ("DATA;HISTÓRICO;DOCTO;CRÉDITO;DÉBITO;SALDO\n"
           "31/12/25;SALDO ANTERIOR;;;;\"1,00\"\n"
           "02/01/26;CARTAO;1;\"1.842,30\";;\n"
           "03/01/26;PAGTO;2;;\"850,00\";\n")
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    assert r.status == "OK" and len(r.transacoes) == 2, (r.status, len(r.transacoes))


@caso("32 ingest: CSV com newline dentro de campo (tolerante) nao quebra")
def _():
    d = _tmp()
    csv = 'Data;Valor\n02/01/2026;-100,00\n"linha\nquebrada";0\n'
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    assert r.status in ("OK", "ATENCAO", "MAPEAR_COLUNAS"), r.status   # nunca CORROMPIDO/crash


@caso("33 ingest: CSV header em INGLES (Mercado Pago-like) -> OK")
def _():
    d = _tmp()
    csv = ("INITIAL_BALANCE;CREDITS;DEBITS\n10;20;-5\n\n"
           "RELEASE_DATE;TRANSACTION_TYPE;TRANSACTION_NET_AMOUNT;PARTIAL_BALANCE\n"
           "01-01-2026;Pagamento;-74,08;100,00\n")
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("34 ingest: imagem (.png) com ocr=False -> PRECISA_OCR (fosso)")
def _():
    d = _tmp()
    r = ingest_extrato(_w(os.path.join(d, "p.png"), b"\x89PNG\r\n", binary=True))
    assert r.status == "PRECISA_OCR" and r.fonte == "imagem", (r.status, r.fonte)


@caso("35 ingest: extensao nao suportada -> CORROMPIDO (nao quebra)")
def _():
    d = _tmp()
    r = ingest_extrato(_w(os.path.join(d, "x.zip"), "lixo"))
    assert r.status == "CORROMPIDO", r.status


@caso("36 ingest: CSV serial Excel na data -> OK")
def _():
    d = _tmp()
    csv = "Data;Histórico;Valor;Saldo\n46023.5;PIX;100,00;100,00\n46024.5;PAGTO;30,00;70,00\n"
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    assert r.status == "OK" and len(r.transacoes) == 2, (r.status, len(r.transacoes))


@caso("37 ingest: CSV sem sinal + saldo -> sinal pelo delta (debito negativo)")
def _():
    d = _tmp()
    csv = ("Data;Histórico;Valor Lançamento;Saldo\n"
           ";SALDO ANTERIOR;;100,00\n02/01/2026;PAG FORNEC;30,00;70,00\n")
    r = ingest_extrato(_w(os.path.join(d, "x.csv"), csv))
    from decimal import Decimal
    assert r.transacoes and r.transacoes[0]["valor"] == Decimal("-30.00"), r.transacoes


@caso("38 ingest: TXT (delimitado) roteia p/ tabular")
def _():
    d = _tmp()
    r = ingest_extrato(_w(os.path.join(d, "x.txt"), "Data;Valor\n02/01/2026;-100,00\n"))
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("39 ingest: XLS disfarcado de HTML (estilo Banco Exemplo) via stdlib -> OK")
def _():
    d = _tmp()
    html = ("<html><body><table>"
            "<tr><td>Data</td><td>Histórico</td><td>Valor (R$)</td><td>Saldo (R$)</td></tr>"
            "<tr><td>02/01/2026</td><td>PAGTO</td><td>-100,00</td><td>0,00</td></tr>"
            "</table></body></html>")
    r = ingest_extrato(_w(os.path.join(d, "x.xls"), html))
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("40 ingest: XLSX -> OK [skip sem openpyxl]")
def _():
    if not HAS_XLSX:
        print("       [SKIP] openpyxl ausente"); return
    import openpyxl
    d = _tmp(); p = os.path.join(d, "x.xlsx")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Data", "Histórico", "Valor (R$)", "Saldo (R$)"])
    ws.append(["02/01/2026", "PAGTO", "-100,00", "0,00"])
    wb.save(p)
    r = ingest_extrato(p)
    assert r.status == "OK" and len(r.transacoes) == 1, (r.status, len(r.transacoes))


@caso("41 ingest: PDF-texto -> extrai [skip sem pdfplumber]")
def _():
    if not HAS_PDF:
        print("       [SKIP] pdfplumber ausente"); return
    # gera um PDF de texto simples via pypdfium2? Nao — usa reportlab se houver; senao skip.
    if not _has("reportlab"):
        print("       [SKIP] reportlab ausente (gerador de PDF de teste)"); return
    from reportlab.pdfgen import canvas
    d = _tmp(); p = os.path.join(d, "x.pdf")
    c = canvas.Canvas(p)
    c.drawString(50, 800, "Data Historico Valor")
    c.drawString(50, 780, "02/01/2026 PAGTO FORNEC -100,00")
    c.save()
    r = ingest_extrato(p)
    assert r.status in ("ATENCAO", "OK") and len(r.transacoes) >= 1, (r.status, len(r.transacoes))


@caso("42 ingest: PDF com bytes invalidos -> CORROMPIDO/PRECISA_OCR, nunca crash")
def _():
    d = _tmp()
    r = ingest_extrato(_w(os.path.join(d, "x.pdf"), b"%PDF-1.4 lixo nao e pdf", binary=True))
    assert r.status in ("CORROMPIDO", "PRECISA_OCR", "MAPEAR_COLUNAS"), r.status


# ============================================================================
# D. FLUXO pasta (jornada do analista)
# ============================================================================
def _pasta_run(estrutura, ocr=False):
    """estrutura: {subpasta: {arquivo: conteudo|bytes}}. Roda 'pasta'. Retorna (rc, resumo)."""
    base = _tmp()
    for sub, arqs in estrutura.items():
        for nome, cont in arqs.items():
            _w(os.path.join(base, sub, nome), cont, binary=isinstance(cont, bytes))
    out = os.path.join(base, "_out")
    argv = ["pasta", "--pasta", base, "--out", out]
    if ocr:
        argv.append("--ocr")
    rc = _run(argv)
    res = _resumo(out) if os.path.exists(os.path.join(out, "resumo.json")) else None
    return rc, res


@caso("43 pasta: 1 conta com extrato (sem razao) -> exit 0, so ingere")
def _():
    rc, res = _pasta_run({"001 - X": {"e.ofx": _ofx([("20260102", "-100.00", "A")])}})
    assert rc == 0 and res["resumo"]["contas"] == 1, res["resumo"]


@caso("44 pasta: multi-conta -> conta cada uma")
def _():
    rc, res = _pasta_run({
        "001 - X": {"e.ofx": _ofx([("20260102", "-100.00", "A")])},
        "002 - Y": {"e.csv": "Data;Valor\n02/01/2026;-50,00\n"}})
    assert res["resumo"]["contas"] == 2, res["resumo"]


@caso("45 pasta: preferencia de formato (OFX > CSV na mesma conta)")
def _():
    rc, res = _pasta_run({"001 - X": {
        "e.ofx": _ofx([("20260102", "-100.00", "A")]),
        "e.csv": "Data;Valor\n02/01/2026;-100,00\n"}})
    assert res["resumo"]["contas"] == 1, res["resumo"]
    assert res["contas"][0]["fonte"] == "ofx", res["contas"][0]


@caso("46 pasta: CONCILIA a conta quando ha razao.csv")
def _():
    rc, res = _pasta_run({"001 - X": {
        "e.ofx": _ofx([("20260102", "-100.00", "A"), ("20260103", "-50.00", "B")]),
        "razao.csv": _razao([("02/01/2026", "-100,00"), ("03/01/2026", "-50,00")])}})
    assert res["resumo"]["conciliadas"] == 1, res["resumo"]
    assert res["contas"][0]["taxa_pct"] == 100.0, res["contas"][0]


@caso("47 pasta: credito do banco sem razao -> conta credito_sem_ar (orienta AR)")
def _():
    rc, res = _pasta_run({"001 - X": {
        "e.ofx": _ofx([("20260102", "-100.00", "A"), ("20260104", "200.00", "PIX RECEBIDO")]),
        "razao.csv": _razao([("02/01/2026", "-100,00")])}})
    assert res["contas"][0]["credito_sem_ar"] == 1, res["contas"][0]


@caso("48 pasta: conta so com imagem -> precisa_acao (PRECISA_OCR)")
def _():
    rc, res = _pasta_run({"003 - Z": {"foto.png": b"\x89PNG\r\n"}})
    assert res["contas"][0]["precisa_acao"] is True, res["contas"][0]


@caso("49 pasta: resumo.json agregado nao vaza linhas de transacao")
def _():
    rc, res = _pasta_run({"001 - X": {
        "e.ofx": _ofx([("20260102", "-100.00", "FORNEC SECRETO")]),
        "razao.csv": _razao([("02/01/2026", "-100,00", "FORNEC SECRETO")])}})
    blob = json.dumps(res, ensure_ascii=False)
    assert "transacoes" not in blob and "SECRETO" not in blob, "vazou dado bruto"


@caso("50 pasta: pasta vazia -> exit 0, 0 contas, nao quebra")
def _():
    rc, res = _pasta_run({})
    assert rc == 0 and res["resumo"]["contas"] == 0, (rc, res)


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {type(e).__name__}: {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    for d in _tmps:
        shutil.rmtree(d, ignore_errors=True)
    print()
    print(f"  (libs: openpyxl={HAS_XLSX} xlrd={HAS_XLRD} pdfplumber={HAS_PDF} ocr={HAS_OCR})")
    if falhas:
        print(f"\n==> FALHOU ({len(falhas)}/{len(casos)}):\n  - " + "\n  - ".join(falhas)); return 1
    print(f"\n==> E2E OK: {len(casos)} testes end-to-end verdes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
