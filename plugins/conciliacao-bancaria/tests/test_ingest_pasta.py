# -*- coding: utf-8 -*-
"""Orquestracao de PASTA (SPEC-01 preferencia de formato + SPEC-04 'varre a pasta').

ingest_pasta varre a pasta, ingere cada extrato e devolve POR CONTA a melhor leitura:
quando a mesma conta vem em varios formatos (OFX + CSV + PDF), escolhe o melhor
(OFX > CSV/XLSX > PDF > OCR) e marca os outros como redundantes — nao conta 2x.
Imagem/escaneado vira conta que 'precisa_acao'. Antifragil: nunca quebra.

Rodar:  python tests/test_ingest_pasta.py
"""
import os
import sys
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from ingest_extrato import ingest_pasta   # noqa: E402
import conciliar                          # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


_OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>0341<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><DTPOSTED>20260102<TRNAMT>-100.00<FITID>1<MEMO>PAGTO FORNEC</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>-100.00<DTASOF>20260131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""

_CSV = "Data;Valor;Historico\n02/01/2026;-100,00;PAGTO FORNEC\n"


def _monta_pasta():
    base = tempfile.mkdtemp(prefix="conc_pasta_")
    # conta A: MESMA conta em 2 formatos (OFX + CSV) -> deve preferir OFX
    a = os.path.join(base, "001 - Banco X"); os.makedirs(a)
    open(os.path.join(a, "extrato.ofx"), "w", encoding="utf-8").write(_OFX)
    open(os.path.join(a, "extrato.csv"), "w", encoding="utf-8").write(_CSV)
    # conta B: so CSV -> OK
    b = os.path.join(base, "002 - Banco Y"); os.makedirs(b)
    open(os.path.join(b, "extrato.csv"), "w", encoding="utf-8").write(_CSV)
    # conta C: so imagem -> precisa OCR (precisa_acao)
    c = os.path.join(base, "003 - Banco Z"); os.makedirs(c)
    open(os.path.join(c, "print.png"), "wb").write(b"\x89PNG\r\n\x1a\n")
    # lixo AppleDouble deve ser ignorado
    open(os.path.join(a, "._extrato.ofx"), "w").write("junk")
    return base


@caso("ingest_pasta agrupa por conta e escolhe o melhor formato (OFX > CSV)")
def _():
    base = _monta_pasta()
    try:
        r = ingest_pasta(base)
        contas = {tuple(c["chave"]) if isinstance(c["chave"], list) else c["chave"]: c for c in r["contas"]}
        assert len(r["contas"]) == 3, [c["arquivo"] for c in r["contas"]]
        # conta A: preferiu OFX, 2 formatos, CSV redundante
        ca = [c for c in r["contas"] if "Banco X" in c["arquivo"]][0]
        assert ca["fonte"] == "ofx", ca
        assert ca["n_formatos"] == 2, ca
        assert ca["n_txns"] == 1 and not ca["precisa_acao"], ca
        csv_a = [a for a in r["arquivos"] if "Banco X" in a["arquivo"] and a["fonte"] == "csv"][0]
        assert csv_a["papel"] == "redundante", csv_a
    finally:
        shutil.rmtree(base, ignore_errors=True)


@caso("conta so com imagem -> precisa_acao (PRECISA_OCR)")
def _():
    base = _monta_pasta()
    try:
        r = ingest_pasta(base)
        cc = [c for c in r["contas"] if "Banco Z" in c["arquivo"]][0]
        assert cc["status"] == "PRECISA_OCR" and cc["precisa_acao"], cc
    finally:
        shutil.rmtree(base, ignore_errors=True)


@caso("resumo agrega contas/arquivos/txns e ignora lixo ._")
def _():
    base = _monta_pasta()
    try:
        r = ingest_pasta(base)
        res = r["resumo"]
        assert res["contas"] == 3, res
        assert res["contas_ok"] == 2 and res["contas_acao"] == 1, res
        assert res["txns"] == 2, res                       # OFX(1) + CSV(1); o CSV redundante da A nao soma
        assert all("._" not in a["arquivo"] for a in r["arquivos"]), r["arquivos"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


@caso("pasta vazia -> 0 contas, nao quebra")
def _():
    base = tempfile.mkdtemp(prefix="conc_vazia_")
    try:
        r = ingest_pasta(base)
        assert r["contas"] == [] and r["resumo"].get("contas", 0) == 0, r
    finally:
        shutil.rmtree(base, ignore_errors=True)


@caso("CLI conciliar.py pasta: roda, escreve resumo.json agregado, exit 0")
def _():
    import json
    base = _monta_pasta()
    out = tempfile.mkdtemp(prefix="conc_out_")
    try:
        rc = conciliar.cmd_pasta(base, out)
        assert rc == 0, rc
        with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
            r = json.load(f)
        assert r["resumo"]["contas"] == 3, r["resumo"]
        # resumo.json e AGREGADO: nenhuma chave 'transacoes' (linha bruta) deve vazar
        assert "transacoes" not in json.dumps(r), "resumo.json nao pode conter linhas de transacao"
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)


_OFX3 = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>0341<ACCTID>9<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><DTPOSTED>20260102<TRNAMT>-100.00<FITID>1<MEMO>PAGTO A</STMTTRN>
<STMTTRN><DTPOSTED>20260103<TRNAMT>-50.00<FITID>2<MEMO>PAGTO B</STMTTRN>
<STMTTRN><DTPOSTED>20260104<TRNAMT>200.00<FITID>3<MEMO>PIX RECEBIDO</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>0,00<DTASOF>20260131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


@caso("CLI pasta CONCILIA a conta vs razao.csv (1/conta) + conta credito-sem-AR (SPEC-03/04)")
def _():
    import json
    base = tempfile.mkdtemp(prefix="conc_rec_")
    a = os.path.join(base, "001 - Banco X"); os.makedirs(a)
    open(os.path.join(a, "extrato.ofx"), "w", encoding="utf-8").write(_OFX3)
    open(os.path.join(a, "razao.csv"), "w", encoding="utf-8").write(
        "Data;Valor;Historico\n02/01/2026;-100,00;A\n03/01/2026;-50,00;B\n")
    out = tempfile.mkdtemp(prefix="conc_recout_")
    try:
        rc = conciliar.cmd_pasta(base, out)
        assert rc == 0, rc
        r = json.load(open(os.path.join(out, "resumo.json"), encoding="utf-8"))
        assert r["resumo"]["conciliadas"] == 1, r["resumo"]
        c = r["contas"][0]
        assert c["tem_razao"] and c["n_razao"] == 2, c
        assert c["conciliados"] == 2 and c["pendente_extrato"] == 1, c   # 2 pagtos casam; +200 sobra
        assert c["credito_sem_ar"] == 1, c                                # o credito +200 = lance AR
        assert "transacoes" not in json.dumps(r), "resumo.json nao pode conter linhas"
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> INGEST_PASTA OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
