# -*- coding: utf-8 -*-
"""Correcoes de abertura da Conciliacao (spec 2026-11-08-conciliacao-correcoes-gate2-design.md, D1 a D10).

Cada caso e uma entrada da tabela "Decisao" da spec, com dado 100% ficticio. A falha antes da
correcao e o que prova que o caso trava o defeito.

Rodar:  python tests/test_correcoes_abertura.py
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from ingest_extrato import ingest_extrato, ingest_tabular_rows, _pdf_text_to_txns   # noqa: E402
import posicao                                                                      # noqa: E402
import conciliar                                                                    # noqa: E402
from reconcile import match_banco, resumo_privado                                   # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _eq(got, want):
    assert got == want, f"obtido {got!r}, esperado {want!r}"


# ---------------------------------------------------------------- D1: valor de PDF truncado
def _pdf_valor(trecho):
    """Valor da 1a transacao de uma linha de extrato em texto de PDF."""
    t = _pdf_text_to_txns(f"01/01/2026 PAGAMENTO {trecho}")
    assert len(t) == 1, t
    return t[0]["valor"]


@caso("D1 PDF: inteiro sem milhar com sufixo Itau (1234,56-) = -1234.56, nao -234.56")
def _():
    _eq(_pdf_valor("1234,56-"), Decimal("-1234.56"))


@caso("D1 PDF: milhar com ponto, centena e milhoes continuam iguais")
def _():
    _eq(_pdf_valor("1.234,56-"), Decimal("-1234.56"))
    _eq(_pdf_valor("234,56"), Decimal("234.56"))
    _eq(_pdf_valor("12.345.678,90"), Decimal("12345678.90"))


@caso("D1 PDF: 1 e 7+ digitos inteiros; a descricao nao leva o valor de volta")
def _():
    _eq(_pdf_valor("5,00"), Decimal("5.00"))
    _eq(_pdf_valor("1234567,89"), Decimal("1234567.89"))
    t = _pdf_text_to_txns("01/01/2026 TARIFA CESTA 1234,56-")
    assert "1234" not in t[0]["descricao"] and "56" not in t[0]["descricao"], t[0]["descricao"]

# ---------------------------------------------------------------- D2: data invalida nao herda a anterior
@caso("D2 CSV: 01/01 A, 31/02 B, vazio C -> A e C (C em 01/01), B descartada e contada como ignorada")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "ext.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("Data;Historico;Valor\n01/01/2026;A;-10,00\n31/02/2026;B;-20,00\n;C;-30,00\n")
        r = ingest_extrato(p)
    _eq([(t["data"], t["valor"]) for t in r.transacoes],
        [(date(2026, 1, 1), Decimal("-10.00")), (date(2026, 1, 1), Decimal("-30.00"))])
    _eq(r.n_ignoradas, 1)


@caso("D2 tabular: data vazia na 1a linha (sem anterior) segue descartada; a seguinte entra")
def _():
    r = ingest_tabular_rows([["Data", "Historico", "Valor"],
                             ["", "A", "-10,00"],
                             ["02/01/2026", "B", "-20,00"]])
    _eq([(t["data"], t["valor"]) for t in r["transacoes"]], [(date(2026, 1, 2), Decimal("-20.00"))])
    _eq(r["n_ignoradas"], 1)


# ---------------------------------------------------------------- D4: o saldo da so o sinal, a magnitude e do arquivo
CAB4 = ["Data", "Historico", "Valor", "Saldo"]


@caso("D4 saldo 1000,00 -> 1100,01 com lancamento de 100,00: valor 100.00 (nao 100.01), ATENCAO, aviso com 1")
def _():
    r = ingest_tabular_rows([CAB4,
                             ["01/01/2026", "Saldo anterior", "", "1.000,00"],
                             ["02/01/2026", "PAGAMENTO", "100,00", "1.100,01"],
                             ["03/01/2026", "TARIFA", "10,00", "1.090,01"]])
    _eq([t["valor"] for t in r["transacoes"]], [Decimal("100.00"), Decimal("-10.00")])
    _eq(r["status"], "ATENCAO")
    _eq(r["aviso"], "1 lancamento(s) com diferenca de centavo entre valor e saldo (confira)")


@caso("D4 saldo que cai 100,01 contra lancamento de 100,00: -100.00; delta exato nao avisa")
def _():
    r = ingest_tabular_rows([CAB4,
                             ["01/01/2026", "Saldo anterior", "", "1.000,00"],
                             ["02/01/2026", "PAGAMENTO", "100,00", "899,99"],
                             ["03/01/2026", "DEPOSITO", "50,00", "949,99"]])
    _eq([t["valor"] for t in r["transacoes"]], [Decimal("-100.00"), Decimal("50.00")])
    _eq(r["aviso"], "1 lancamento(s) com diferenca de centavo entre valor e saldo (confira)")
    r = ingest_tabular_rows([CAB4,
                             ["01/01/2026", "Saldo anterior", "", "1.000,00"],
                             ["02/01/2026", "PAGAMENTO", "100,00", "900,00"]])
    _eq([t["valor"] for t in r["transacoes"]], [Decimal("-100.00")])
    _eq((r["status"], r["aviso"]), ("OK", ""))


# ---------------------------------------------------------------- D5 e D6: posicao (conta repetida e moeda)
CLI = os.path.join(SCRIPTS, "conciliar.py")


def _ofx(banco="001", agencia="1", conta="123", saldo="1000.00", dtasof="20260131", curdef="BRL"):
    """OFX minimo de conta corrente (dado ficticio). conta="" omite o ACCTID; curdef="" omite o CURDEF."""
    cur = f"<CURDEF>{curdef}" if curdef else ""
    acct = f"<ACCTID>{conta}" if conta else ""
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>" + cur
            + f"<BANKACCTFROM><BANKID>{banco}<BRANCHID>{agencia}{acct}<ACCTTYPE>CHECKING</BANKACCTFROM>"
            "<BANKTRANLIST>\n<STMTTRN><DTPOSTED>20260102<TRNAMT>-10.00<FITID>F1<MEMO>TESTE</STMTTRN>\n"
            f"</BANKTRANLIST><LEDGERBAL><BALAMT>{saldo}<DTASOF>{dtasof}</LEDGERBAL>"
            "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")


def _pasta(d, arquivos):
    pasta = os.path.join(d, "ofx")
    os.makedirs(pasta)
    for nome, conteudo in arquivos.items():
        with open(os.path.join(pasta, nome), "w", encoding="utf-8", newline="") as f:
            f.write(conteudo)
    return pasta


def _cons(arquivos, minimo=None):
    with tempfile.TemporaryDirectory() as d:
        return posicao.consolidar_extratos(posicao.varrer_pasta(_pasta(d, arquivos)), saldo_minimo=minimo)


def _posicao_cli(arquivos, minimo="1500"):
    """Roda `conciliar.py posicao`; devolve (linhas do stdout, resumo.json)."""
    with tempfile.TemporaryDirectory() as d:
        pasta, out = _pasta(d, arquivos), os.path.join(d, "res")
        r = subprocess.run([sys.executable, CLI, "posicao", "--pasta", pasta, "--saldo-minimo", minimo, "--out", out],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stderr)
        with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
            return r.stdout.splitlines(), json.load(f)


@caso("D5 dois OFX iguais da mesma conta (001/1/123, saldo 1000): total 1000, 1 fora (repetida), minimo 1500 = ABAIXO")
def _():
    cons = _cons({"a.ofx": _ofx(), "b.ofx": _ofx()}, Decimal("1500"))
    _eq(cons.total_caixa, Decimal("1000.00"))
    _eq([(c.arquivo, c.entra_no_caixa, c.motivo_fora) for c in cons.contas],
        [("a.ofx", True, ""), ("b.ofx", False, "repetida")])
    _eq((cons.n_caixa, cons.n_repetidas, cons.n_repetidas_conflito, cons.abaixo), (1, 1, 0, True))
    linhas, res = _posicao_cli({"a.ofx": _ofx(), "b.ofx": _ofx()})
    assert "TOTAL EM CAIXA: R$ 1.000,00" in linhas, linhas
    assert "STATUS: ABAIXO DO MINIMO (deficit R$ 500,00)" in linhas, linhas
    _eq((res["total_caixa"], res["n_contas_no_caixa"], res["n_repetidas_fora"]), ("1000.00", 1, 1))
    _eq([c["motivo_fora"] for c in res["contas"]], ["", "repetida"])


@caso("D5 duas exportacoes com datas diferentes: entra a de data_saldo mais recente, qualquer que seja a ordem do arquivo")
def _():
    antiga, nova = _ofx(saldo="1000.00", dtasof="20260131"), _ofx(saldo="1200.00", dtasof="20260228")
    for arquivos in ({"a.ofx": antiga, "b.ofx": nova}, {"a.ofx": nova, "b.ofx": antiga}):
        cons = _cons(arquivos)
        _eq(cons.total_caixa, Decimal("1200.00"))
        _eq(sorted(c.motivo_fora for c in cons.contas), ["", "repetida"])
        _eq([c.saldo_final for c in cons.contas if c.entra_no_caixa], [Decimal("1200.00")])


@caso("D5 empate de data com saldos diferentes: nenhuma entra, motivo fixo e linha [!] no stdout")
def _():
    arquivos = {"a.ofx": _ofx(saldo="1000.00"), "b.ofx": _ofx(saldo="900.00"), "c.ofx": _ofx(conta="456", saldo="50.00")}
    cons = _cons(arquivos)
    _eq(cons.total_caixa, Decimal("50.00"))
    _eq([c.motivo_fora for c in cons.contas], ["repetida com saldos diferentes", "repetida com saldos diferentes", ""])
    _eq(cons.n_repetidas_conflito, 1)
    linhas, res = _posicao_cli(arquivos)
    assert "[!] 1 conta(s) repetida(s) com saldos diferentes" in linhas, linhas
    _eq(res["n_repetidas_saldos_diferentes"], 1)


@caso("D5 conta vazia nao agrupa; mesma conta em bancos diferentes tambem nao")
def _():
    cons = _cons({"a.ofx": _ofx(conta=""), "b.ofx": _ofx(conta="")})
    _eq((cons.n_caixa, cons.total_caixa), (2, Decimal("2000.00")))
    cons = _cons({"a.ofx": _ofx(banco="001"), "b.ofx": _ofx(banco="237")})
    _eq((cons.n_caixa, cons.total_caixa), (2, Decimal("2000.00")))


@caso("D6 BRL 1000 + USD 1000: total 1000, a conta em dolar fica fora com motivo moeda e o stdout avisa")
def _():
    arquivos = {"a.ofx": _ofx(conta="123"), "b.ofx": _ofx(conta="456", curdef="USD")}
    cons = _cons(arquivos)
    _eq(cons.total_caixa, Decimal("1000.00"))
    _eq([(c.moeda, c.entra_no_caixa, c.motivo_fora) for c in cons.contas],
        [("BRL", True, ""), ("USD", False, "moeda")])
    _eq((cons.n_outra_moeda, cons.n_sem_saldo), (1, 0))
    linhas, res = _posicao_cli(arquivos)
    assert "[i] 1 conta(s) em outra moeda fora do caixa: USD" in linhas, linhas
    _eq([(c["moeda"], c["motivo_fora"]) for c in res["contas"]], [("BRL", ""), ("USD", "moeda")])
    _eq(res["n_outra_moeda_fora"], 1)


@caso("D6 CURDEF ausente vira BRL e entra; CURDEF mal formado nao tira a conta do caixa (a saida mostra ?)")
def _():
    cons = _cons({"a.ofx": _ofx(curdef=""), "b.ofx": _ofx(conta="456", curdef="X1")})
    _eq((cons.n_caixa, cons.n_outra_moeda), (2, 0))
    _eq([posicao.moeda_saida(c.moeda) for c in cons.contas], ["BRL", "?"])



# ---------------------------------------------------------------- D7: pasta nao concilia extrato multiconta
def _bloco_conta(conta, valor):
    return ("<STMTTRNRS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<BRANCHID>1"
            f"<ACCTID>{conta}<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST>\n"
            f"<STMTTRN><DTPOSTED>20260102<TRNAMT>{valor}<FITID>F{conta}<MEMO>TESTE</STMTTRN>\n"
            "</BANKTRANLIST><LEDGERBAL><BALAMT>500.00<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS>")


RAZAO_D7 = "Data;Valor;Documento;Contraparte\n02/01/2026;-100,00;;FORNECEDOR ALFA\n"


@caso("D7 pasta: OFX com 2 contas + razao nao concilia (sem taxa_pct, multiconta 2, linha [!]); a conta de 1 conta segue")
def _():
    ofx2 = "OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1>" + _bloco_conta("111", "-100.00") + _bloco_conta("222", "-30.00") + "</BANKMSGSRSV1></OFX>"
    ofx1 = "OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1>" + _bloco_conta("333", "-100.00") + "</BANKMSGSRSV1></OFX>"
    with tempfile.TemporaryDirectory() as d:
        for sub, ofx in (("conta_dupla", ofx2), ("conta_unica", ofx1)):
            os.makedirs(os.path.join(d, sub))
            for nome, conteudo in (("extrato.ofx", ofx), ("razao.csv", RAZAO_D7)):
                with open(os.path.join(d, sub, nome), "w", encoding="utf-8", newline="") as f:
                    f.write(conteudo)
        out = os.path.join(d, "res")
        r = subprocess.run([sys.executable, CLI, "pasta", "--pasta", d, "--out", out],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stderr)
        with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
            res = json.load(f)
        assert not os.path.exists(os.path.join(d, "conta_dupla", "conciliacao.xlsx"))   # relatorio so da conta conciliada
    por = {c["conta"]: c for c in res["contas"]}
    dupla, unica = por["conta_dupla"], por["conta_unica"]
    assert "taxa_pct" not in dupla, dupla
    _eq((dupla["multiconta"], dupla["tem_razao"], dupla["precisa_acao"]), (2, False, True))
    assert "taxa_pct" in unica and "multiconta" not in unica, unica
    _eq((res["resumo"]["conciliadas"], res["resumo"]["ingeridas"], res["resumo"]["precisa_acao"]), (1, 1, 1))
    assert "extrato p/ acao: 1" in r.stdout, r.stdout                    # Gate 2: o agregado conta a multiconta
    assert "conta(s) com extrato que precisa de acao" not in r.stdout, r.stdout   # sem causa de OCR/layout falsa
    assert "  [!] extrato com mais de uma conta em: conta_dupla" in r.stdout.splitlines(), r.stdout



# ---------------------------------------------------------------- D9 (1:1): so a PROVA de par errado recusa
D = date(2026, 3, 16)
E1 = "E" + "1" * 31        # E2E do Pix ficticio (E + 31 caracteres)
E2 = "E" + "2" * 31
A, B = "11111111000111", "22222222000122"     # CNPJs de raizes diferentes
A_FIL = "11111111000211"                       # mesma raiz de A (outra filial)
CPF = "12345678901"
CONF_CNPJ = "conferir: CPF/CNPJ do banco diferente do razao"


def _ext(v, nome="", cnpj=None, ident=None, d=D):
    return {"data": d, "valor": Decimal(v), "doc": None, "descricao": nome, "contraparte": nome,
            "cpf_cnpj": cnpj, "identificador": ident}


def _raz(v, nome="", cnpj=None, ident=None, lote=None, d=D):
    return {"data": d, "valor": Decimal(v), "doc": None, "identificador": ident, "contraparte": nome,
            "cpf_cnpj": cnpj, "descricao": nome, "lote": lote}


def _lanc(ext, raz, **kw):
    """(lancamentos do extrato na ordem, Conciliacao)."""
    c = match_banco(ext, raz, **kw)
    return [l for l in c.lancamentos if l.lado == "EXTRATO"], c


def _status(ext, raz, **kw):
    ls, c = _lanc(ext, raz, **kw)
    return [l.status for l in ls], c.contagem


@caso("D9 1:1: extrato -100 (E111, Alfa) contra unico titulo -100 (E222, Beta): E2E contra outro E2E, os dois pendentes")
def _():
    st, cont = _status([_ext("-100.00", "Fornecedor Alfa", ident=E1)], [_raz("-100.00", "Fornecedor Beta", ident=E2)])
    _eq(st, ["PENDENTE_EXTRATO"])
    _eq(cont.get("PENDENTE_RAZAO"), 1)


@caso("D9 1:1: mesmo E2E concilia; lado sem identificador ou E2E contra NSU no razao segue como hoje (sem marca)")
def _():
    for ident_raz in (E1, None, "123456"):
        ls, _c = _lanc([_ext("-100.00", ident=E1)], [_raz("-100.00", ident=ident_raz)])
        _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ()))
    ls, _c = _lanc([_ext("-100.00", ident=None)], [_raz("-100.00", ident=E2)])
    _eq(ls[0].status, "CONCILIADO")


@caso("D9 1:1: prova = CNPJ do banco e o de OUTRO titulo do razao (consumido ou nao): o par recusa e fica pendente")
def _():
    raz = [_raz("-100.00", "Fornecedor Alfa", cnpj=B), _raz("-33.00", "Fornecedor Alfa", cnpj=A)]
    st, cont = _status([_ext("-100.00", "Fornecedor Alfa", cnpj=A)], raz)
    _eq(st, ["PENDENTE_EXTRATO"])
    _eq(cont.get("PENDENTE_RAZAO"), 2)
    # o titulo do CNPJ A ja foi consumido pelo 1o extrato e ainda assim prova
    st, _c = _status([_ext("-33.00", cnpj=A), _ext("-100.00", "Fornecedor Alfa", cnpj=A)], raz)
    _eq(st, ["CONCILIADO", "PENDENTE_EXTRATO"])


@caso("D9 1:1: divergencia sem prova (CNPJ do banco que nao esta no razao) casa e marca conferir cpf_cnpj; conta como conciliado")
def _():
    ls, c = _lanc([_ext("-100.00", "Fornecedor Alfa", cnpj=A)], [_raz("-100.00", "Fornecedor Alfa", cnpj=B)])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ("cpf_cnpj",)))
    r = resumo_privado(c)
    _eq((r["conferir_cpf_cnpj"], r["taxa_conciliacao_pct"]), (1, 100.0))
    _eq(conciliar._rotulo_conferir(ls[0]), ("CONFERIR", CONF_CNPJ))
    ls, _c = _lanc([_ext("-100.00", cnpj=CPF)], [_raz("-100.00", cnpj=B)])       # CPF contra CNPJ: diverge
    _eq(ls[0].conferir, ("cpf_cnpj",))


@caso("D9 1:1: CNPJ de 14 digitos com a mesma raiz de 8 (matriz e filial) casa sem marca; igual ou vazio tambem")
def _():
    for cnpj_raz in (A_FIL, A, None):
        ls, c = _lanc([_ext("-100.00", cnpj=A)], [_raz("-100.00", cnpj=cnpj_raz)])
        _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ()))
        _eq(resumo_privado(c)["conferir_cpf_cnpj"], 0)


@caso("D9 1:1: o candidato com prova sai da disputa; o limpo (mesmo de afinidade menor) e o par")
def _():
    # sem a regra os dois empatam em afinidade e o FIFO escolheria o titulo 0 (que contradiz o E2E)
    ls, _c = _lanc([_ext("-100.00", ident=E1)], [_raz("-100.00", ident=E2), _raz("-100.00", ident=None)])
    _eq((ls[0].status, ls[0].par_idx), ("CONCILIADO", 1))


@caso("D9 E2E igual com caixa diferente nao e prova (casa)")
def _():
    # E2E de estrutura valida (D16): so a caixa do sufixo muda; um lado todo em maiusculas (MEMO do banco)
    e_up = "E12345678202601021200ABCXYZ12345"
    ls, _c = _lanc([_ext("-100.00", ident=e_up)], [_raz("-100.00", ident=e_up[:21] + e_up[21:].lower())])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ()))


@caso("D9 tolerancia: -100,05 contra -100,00 com mesmo nome: prova recusa; divergencia sem prova marca; mesmo CNPJ sem marca")
def _():
    ext = lambda: [_ext("-100.05", "Fornecedor Alfa", cnpj=A)]
    # o nome em comum daria afinidade > 0 (e o par casaria por tolerancia) se a prova nao o barrasse
    st, _c = _status(ext(), [_raz("-100.00", "Fornecedor Alfa", cnpj=B), _raz("-7.00", "Fornecedor Alfa", cnpj=A)])
    _eq(st, ["PENDENTE_EXTRATO"])
    ls, _c = _lanc(ext(), [_raz("-100.00", "Fornecedor Alfa", cnpj=B)])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_COM_DIFERENCA", ("cpf_cnpj",)))
    ls, _c = _lanc(ext(), [_raz("-100.00", "Fornecedor Alfa", cnpj=A)])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_COM_DIFERENCA", ()))


def _arquivos_marca(d):
    """Subpasta com 1 OFX (MEMO com o CNPJ A) e 1 razao (CNPJ B): concilia com divergencia sem prova."""
    ofx = ("OFXHEADER:100" + chr(10) + "DATA:OFXSGML" + chr(10) + "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
           "<BANKACCTFROM><BANKID>001<BRANCHID>1<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST>" + chr(10) +
           "<STMTTRN><DTPOSTED>20260102<TRNAMT>-100.00<FITID>F1<MEMO>PIX 11.111.111/0001-11 FORNECEDOR ALFA</STMTTRN>" + chr(10) +
           "</BANKTRANLIST><LEDGERBAL><BALAMT>900.00<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
    razao = ("Data;Valor;Documento;Contraparte;CNPJ_CPF" + chr(10)
             + "02/01/2026;-100,00;;FORNECEDOR ALFA;22222222000122" + chr(10))
    os.makedirs(os.path.join(d, "conta_a"))
    for nome, conteudo in (("extrato.ofx", ofx), ("razao.csv", razao)):
        with open(os.path.join(d, "conta_a", nome), "w", encoding="utf-8", newline="") as f:
            f.write(conteudo)


@caso("D9 marca no stdout e no resumo.json (modo pasta e modo conciliar): linha [!] fixa e contagem, sem CNPJ nem nome")
def _():
    linha = "[!] 1 conciliacao(oes) com CPF/CNPJ do banco diferente do razao (confira no Excel)"
    with tempfile.TemporaryDirectory() as d:
        _arquivos_marca(d)
        out = os.path.join(d, "res")
        r = subprocess.run([sys.executable, CLI, "pasta", "--pasta", d, "--out", out],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stderr)
        assert ("  " + linha) in r.stdout.splitlines(), r.stdout
        with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
            res = json.load(f)
        _eq(res["contas"][0]["conferir_cpf_cnpj"], 1)
        assert "11111111000111" not in r.stdout and "22222222000122" not in r.stdout
        sub = os.path.join(d, "conta_a")
        r = subprocess.run([sys.executable, CLI, "conciliar", "--extrato", os.path.join(sub, "extrato.ofx"),
                            "--razao", os.path.join(sub, "razao.csv"), "--saldo-razao", "900", "--out", os.path.join(d, "res2")],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stdout[-300:], r.stderr)
        assert ("  " + linha) in r.stdout.splitlines(), r.stdout



# ---------------------------------------------------------------- D9 (lote sem remessa) e D10a
@caso("D9 cascata 1:1 -> lote: extrato -100 (E111, Alfa) contra -40 e -60 (E222, mesma contraparte) nao vira lote")
def _():
    raz = [_raz("-40.00", "Fornecedor Alfa", ident=E2), _raz("-60.00", "Fornecedor Alfa", ident=E2)]
    st, cont = _status([_ext("-100.00", "Fornecedor Alfa", ident=E1)], raz)
    _eq(st, ["PENDENTE_EXTRATO"])
    _eq((cont.get("CONCILIADO_LOTE", 0), cont.get("PENDENTE_RAZAO")), (0, 2))


@caso("D9 lote: mesmo E2E nos componentes, ou componentes sem identificador, continuam virando lote sem marca")
def _():
    for ident in (E1, None):
        raz = [_raz("-40.00", "Fornecedor Alfa", ident=ident), _raz("-60.00", "Fornecedor Alfa", ident=ident)]
        ls, _c = _lanc([_ext("-100.00", "Fornecedor Alfa", ident=E1)], raz)
        _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_LOTE", ()))


@caso("D9 cascata: o titulo -100 rejeitado no 1:1 nao volta; o lote fecha com os outros dois")
def _():
    raz = [_raz("-100.00", "Fornecedor Alfa", ident=E2), _raz("-40.00", "Fornecedor Alfa"), _raz("-60.00", "Fornecedor Alfa")]
    ls, c = _lanc([_ext("-100.00", "Fornecedor Alfa", ident=E1)], raz)
    _eq((ls[0].status, sorted(ls[0].componentes)), ("CONCILIADO_LOTE", [1, 2]))
    _eq(c.contagem.get("PENDENTE_RAZAO"), 1)


@caso("D10a lote por CNPJ: prova (CNPJ do banco em outro titulo) recusa; divergencia sem prova marca o lote; mesma raiz e vazio nao marcam")
def _():
    raz = [_raz("-40.00", "X", cnpj=B), _raz("-60.00", "X", cnpj=B)]
    st, _c = _status([_ext("-100.00", "X", cnpj=A)], raz + [_raz("-7.00", "Y", cnpj=A)])      # A esta em outro titulo: prova
    _eq(st, ["PENDENTE_EXTRATO"])
    ls, c = _lanc([_ext("-100.00", "X", cnpj=A)], raz)                                          # A fora do razao: so divergencia
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_LOTE", ("cpf_cnpj",)))
    _eq(resumo_privado(c)["conferir_cpf_cnpj"], 1)
    for cnpj_ext in (None, B, "22222222000999"):
        ls, _c = _lanc([_ext("-100.00", "X", cnpj=cnpj_ext)], raz)
        _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_LOTE", ()))


@caso("D9 remessa explicita multi-contraparte: o lote casa como hoje, sem filtro de prova nem marca")
def _():
    raz = [_raz("-60.00", "Forn A", cnpj=A, ident=E2, lote="R1"),
           _raz("-40.00", "Forn B", cnpj=B, ident=None, lote="R1"),
           _raz("-9.00", "Forn C", cnpj="33333333000133")]
    ls, _c = _lanc([_ext("-100.00", "SISPAG FORNECEDORES", cnpj="33333333000133", ident=E1)], raz)
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_LOTE", ()))



# ---------------------------------------------------------------- D10b: grupo por nome so casa com TODOS os tokens no extrato
BETA_40_60 = [_raz("-40.00", "Fornecedor Beta"), _raz("-60.00", "Fornecedor Beta")]


@caso("D10b extrato 'Fornecedor Alfa' (-100) contra 'Fornecedor Beta' -40 e -60: FORNECEDOR em comum nao basta, fica pendente")
def _():
    st, cont = _status([_ext("-100.00", "Fornecedor Alfa")], BETA_40_60)
    _eq(st, ["PENDENTE_EXTRATO"])
    _eq(cont.get("PENDENTE_RAZAO"), 2)


@caso("D10b extrato 'PAGAMENTO FORNECEDOR BETA' contra o mesmo grupo: todos os tokens do grupo estao no extrato, vira lote")
def _():
    _eq(_status([_ext("-100.00", "PAGAMENTO FORNECEDOR BETA")], BETA_40_60)[0], ["CONCILIADO_LOTE"])


@caso("D10b extrato sem token nenhum (so palavra de ruido bancario) segue como hoje; grupo de 1 token dentro do extrato casa")
def _():
    _eq(_status([_ext("-100.00", "PIX")], BETA_40_60)[0], ["CONCILIADO_LOTE"])
    _eq(_status([_ext("-100.00", "Beta Comercio")], [_raz("-40.00", "Beta"), _raz("-60.00", "Beta")])[0], ["CONCILIADO_LOTE"])



# ---------------------------------------------------------------- D10c: unicidade; mesmos valores no mesmo grupo contam como uma
def _beta(*valores):
    return [_raz(v, "Fornecedor Beta") for v in valores]


EXT_BETA = "PAGAMENTO FORNECEDOR BETA"
CONF_LOTE = "conferir: lote com titulos de mesmo valor (confira quais)"


@caso("D10c -100 contra -40, -60, -20, -30, -50 (mesmo fornecedor): valores diferentes fecham, entao pendente")
def _():
    st, cont = _status([_ext("-100.00", EXT_BETA)], _beta("-40.00", "-60.00", "-20.00", "-30.00", "-50.00"))
    _eq(st, ["PENDENTE_EXTRATO"])
    _eq((cont.get("CONCILIADO_LOTE", 0), cont.get("PENDENTE_RAZAO")), (0, 5))
    for valores in (("-40.00", "-60.00"), ("-20.00", "-30.00", "-50.00")):               # so uma fecha: lote sem marca
        ls, _c = _lanc([_ext("-100.00", EXT_BETA)], _beta(*valores))
        _eq((ls[0].status, ls[0].conferir), ("CONCILIADO_LOTE", ()))


@caso("D10c dois grupos (CNPJ) que fecham o mesmo valor, ate com os mesmos valores: pendente, em qualquer ordem")
def _():
    ga = [_raz("-40.00", "X", cnpj=A), _raz("-60.00", "X", cnpj=A)]
    gb = [_raz("-40.00", "Y", cnpj=B), _raz("-60.00", "Y", cnpj=B)]
    for razao in (ga + gb, gb + ga):
        st, cont = _status([_ext("-100.00", "PIX")], razao)
        _eq(st, ["PENDENTE_EXTRATO"])
        _eq(cont.get("PENDENTE_RAZAO"), 4)
    _eq(_status([_ext("-100.00", "PIX")], ga)[0], ["CONCILIADO_LOTE"])


@caso("D10c valores DIFERENTES no mesmo grupo (-50,-50 e -30,-70): pendente")
def _():
    _eq(_status([_ext("-100.00", EXT_BETA)], _beta("-50.00", "-50.00", "-30.00", "-70.00"))[0], ["PENDENTE_EXTRATO"])


@caso("D10c mesmos valores no mesmo grupo (tres -50): casa a 1a da enumeracao e marca lote_valores_iguais; conta como conciliado")
def _():
    ls, c = _lanc([_ext("-100.00", EXT_BETA)], _beta("-50.00", "-50.00", "-50.00"))
    _eq((ls[0].status, ls[0].componentes, ls[0].conferir), ("CONCILIADO_LOTE", [0, 1], ("lote_valores_iguais",)))
    r = resumo_privado(c)
    _eq((r["conferir_lote_valores_iguais"], r["conferir_cpf_cnpj"], r["taxa_conciliacao_pct"]), (1, 0, 50.0))          # 1 conciliado em 2 registros (o 3o titulo fica pendente)
    _eq(c.contagem.get("PENDENTE_RAZAO"), 1)
    _eq(conciliar._rotulo_conferir(ls[0]), ("CONFERIR", CONF_LOTE))


@caso("D10c marca no stdout e no resumo.json do modo pasta: linha [!] fixa e contagem")
def _():
    ofx = ("OFXHEADER:100" + chr(10) + "DATA:OFXSGML" + chr(10) + "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
           "<BANKACCTFROM><BANKID>001<BRANCHID>1<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST>" + chr(10) +
           "<STMTTRN><DTPOSTED>20260102<TRNAMT>-100.00<FITID>F1<MEMO>PAGAMENTO FORNECEDOR BETA</STMTTRN>" + chr(10) +
           "</BANKTRANLIST><LEDGERBAL><BALAMT>900.00<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
    razao = "Data;Valor;Contraparte" + chr(10) + (("02/01/2026;-50,00;FORNECEDOR BETA" + chr(10)) * 3)
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "conta_a"))
        for nome, conteudo in (("extrato.ofx", ofx), ("razao.csv", razao)):
            with open(os.path.join(d, "conta_a", nome), "w", encoding="utf-8", newline="") as f:
                f.write(conteudo)
        out = os.path.join(d, "res")
        r = subprocess.run([sys.executable, CLI, "pasta", "--pasta", d, "--out", out],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stderr)
        assert "  [!] 1 lote(s) com titulos de mesmo valor (confira quais titulos no Excel)" in r.stdout.splitlines(), r.stdout
        with open(os.path.join(out, "resumo.json"), encoding="utf-8") as f:
            _eq(json.load(f)["contas"][0]["conferir_lote_valores_iguais"], 1)


@caso("D10c limites atuais: grupo inteiro de 9 contra -90 (sem marca); 9 subconjuntos de 8 iguais contra -80 (marca); >18 nao enumera")
def _():
    nove = _beta(*["-10.00"] * 9)
    ls, _c = _lanc([_ext("-90.00", EXT_BETA)], nove)
    _eq((ls[0].status, sorted(ls[0].componentes), ls[0].conferir), ("CONCILIADO_LOTE", list(range(9)), ()))
    ls, _c = _lanc([_ext("-80.00", EXT_BETA)], nove)
    _eq((ls[0].status, ls[0].componentes, ls[0].conferir), ("CONCILIADO_LOTE", list(range(8)), ("lote_valores_iguais",)))
    _eq(_status([_ext("-20.00", EXT_BETA)], _beta(*["-10.00"] * 19))[0], ["PENDENTE_EXTRATO"])    # >18: nao enumera subconjunto


@caso("D10c remessa explicita fora da regra: o 1o subconjunto que fecha casa, como hoje, sem marca")
def _():
    raz = [_raz(v, "Forn", lote="R1") for v in ("-40.00", "-60.00", "-20.00", "-30.00", "-50.00")]
    ls, _c = _lanc([_ext("-100.00", "SISPAG FORNECEDORES")], raz)
    _eq((ls[0].status, ls[0].componentes, ls[0].conferir), ("CONCILIADO_LOTE", [0, 1], ()))



# ---------------------------------------------------------------- D8: centavos do lote entram na amarracao
@caso("D8 extrato -100,05 contra -40 e -60, saldos 899,95 (banco) e 900 (razao): o lote grava -0,05 e a amarracao fecha")
def _():
    c = match_banco([_ext("-100.05", EXT_BETA)], _beta("-40.00", "-60.00"),
                    saldo_extrato_final=Decimal("899.95"), saldo_razao_final=Decimal("900.00"))
    l = [x for x in c.lancamentos if x.lado == "EXTRATO"][0]
    _eq((l.status, l.diferenca), ("CONCILIADO_LOTE", Decimal("-0.05")))
    _eq(c.amarracao["ajuste_diferenca_conciliados"], "-0.05")
    _eq((c.integridade_ok, c.amarracao["fecha"], c.amarracao["residuo"], c.amarracao["diagnostico"]),
        (True, True, "0.00", None))


@caso("D8 lote exato continua com diferenca zero; saldo errado em 5 centavos ainda NAO fecha (a regra nao mascara)")
def _():
    c = match_banco([_ext("-100.00", EXT_BETA)], _beta("-40.00", "-60.00"),
                    saldo_extrato_final=Decimal("900.00"), saldo_razao_final=Decimal("900.00"))
    l = [x for x in c.lancamentos if x.lado == "EXTRATO"][0]
    _eq((l.status, l.diferenca, c.integridade_ok), ("CONCILIADO_LOTE", Decimal("0.00"), True))
    c = match_banco([_ext("-100.05", EXT_BETA)], _beta("-40.00", "-60.00"),
                    saldo_extrato_final=Decimal("899.90"), saldo_razao_final=Decimal("900.00"))
    _eq((c.integridade_ok, c.amarracao["residuo"]), (False, "-0.05"))


# ---------------------------------------------------------------- D16: E2E do Pix pela estrutura
def _ofx_memo(memo):
    from ingest_ofx import parse_ofx_text
    t = parse_ofx_text("<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKACCTFROM><BANKID>001<ACCTID>1</BANKACCTFROM>"
                       f"<BANKTRANLIST><STMTTRN><DTPOSTED>20260102<TRNAMT>-10.00<FITID>F1<MEMO>{memo}</STMTTRN>"
                       "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>").transacoes
    return t[0]["identificador"]


E_ALFA = "E12345678202601021200ABCXYZ12345"      # sufixo alfanumerico
E_ISPB = "E1234567A202601021200ABCXYZ12345"      # letra maiuscula no ISPB (CNPJ alfanumerico)
E_ISPB2 = "E1234567B202601021200ABCXYZ12345"


@caso("D16 extracao: E2E com sufixo alfanumerico e com letra no ISPB saem do MEMO; fora da estrutura nao")
def _():
    _eq(_ofx_memo(f"PIX RECEBIDO {E_ALFA} FIM"), E_ALFA)
    _eq(_ofx_memo(f"PIX {E_ISPB}"), E_ISPB)
    _eq(_ofx_memo("PIX E" + "1" * 31), "E" + "1" * 31)                         # ficticio de 31 digitos segue valido
    _eq(_ofx_memo("PIX E12345678202601A21200ABCXYZ12345"), None)               # letra nas posicoes da data
    _eq(_ofx_memo("PIX E1234567a202601021200ABCXYZ12345"), None)               # minuscula no ISPB
    _eq(_ofx_memo("PIX E12345678202601021200ABCXYZ1234"), None)                # 31 chars
    _eq(_ofx_memo("PIX E12345678202601021200ABCXYZ123456"), None)              # 33 chars


@caso("D16 prova: dois E2E alfanumericos diferentes, mesmo valor e data -> os dois pendentes (tambem com letra no ISPB)")
def _():
    outro = "E12345678202601021200ABCXYZ12346"
    for a, b in ((E_ALFA, outro), (E_ISPB, E_ISPB2)):
        st, _c = _status([_ext("-100.00", ident=a)], [_raz("-100.00", ident=b)])
        _eq(st, ["PENDENTE_EXTRATO"])
    ls, _c = _lanc([_ext("-100.00", ident=E_ISPB)], [_raz("-100.00", ident=E_ISPB)])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ()))


@caso("D16 prova: so a caixa difere e os dois lados tem minuscula -> pendentes; um lado todo em maiusculas -> concilia")
def _():
    a, b = "E12345678202601021200AbcXyz12345", "E12345678202601021200aBcxYZ12345"
    st, _c = _status([_ext("-100.00", ident=a)], [_raz("-100.00", ident=b)])
    _eq(st, ["PENDENTE_EXTRATO"])
    ls, _c = _lanc([_ext("-100.00", ident=a.upper())], [_raz("-100.00", ident=b)])
    _eq((ls[0].status, ls[0].conferir), ("CONCILIADO", ()))


# ---------------------------------------------------------------- D19: delimitador do CSV pelo cabecalho
def _csv(conteudo):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "ext.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(conteudo)
        return ingest_extrato(p)


@caso("D19 CSV: virgulas dentro de campo aspeado nao viram o delimitador (ponto e virgula pelo cabecalho)")
def _():
    lin = '02/01/2026;"PIX, pagamento, fornecedor, Alfa, Beta";-100,00\n'
    r = _csv("Data;Historico;Valor\n" + lin * 3)
    _eq((r.status, [t["valor"] for t in r.transacoes]), ("OK", [Decimal("-100.00")] * 3))


@caso("D19 CSV: ponto e virgula dentro de campo, virgula decimal aspeada -> virgula pelo cabecalho")
def _():
    r = _csv('Data,Historico,Valor\n02/01/2026,PIX;A;B;C;D;E,"1.234,56"\n03/01/2026,PIX;F;G;H;I;J,"-50,00"\n')
    _eq((r.status, [t["valor"] for t in r.transacoes]), ("OK", [Decimal("1234.56"), Decimal("-50.00")]))


@caso("D19 CSV: regressao do Gate 1A (aspa literal em campo sem aspas) segue lendo as 2 transacoes com virgula")
def _():
    r = _csv('Data,Historico,Valor\n02/01/2026,PIX A;B;C;D;E "foo,-100.00\n03/01/2026,PIX BAR baz",-50.00\n')
    _eq((r.status, len(r.transacoes)), ("OK", 2))


@caso("D19 CSV: arquivo vazio e arquivo sem cabecalho seguem como hoje")
def _():
    _eq(_csv("").status, "VAZIO")
    _eq(_csv("a;b;c\n1;2;3\n").status, "MAPEAR_COLUNAS")


# ---------------------------------------------------------------- D14: R solto no prefixo do valor
def _pdf1(trecho):
    t = _pdf_text_to_txns(f"01/01/2026 {trecho}")
    assert len(t) == 1, (trecho, t)
    return t[0]["valor"], t[0]["descricao"]


@caso("D14 PDF: descricao que termina em R nao engole o valor (100,00- = -100.00, descricao inteira)")
def _():
    _eq(_pdf1("PIX FORNECEDOR 100,00-"), (Decimal("-100.00"), "PIX FORNECEDOR"))


@caso("D14 PDF: $ solto e R$ com espaco, sinal antes ou depois, parenteses")
def _():
    _eq(_pdf1("PIX FORNECEDOR -$ 10,00"), (Decimal("-10.00"), "PIX FORNECEDOR"))
    _eq(_pdf1("PIX FORNECEDOR - $ 10,00"), (Decimal("-10.00"), "PIX FORNECEDOR"))
    _eq(_pdf1("X $ 10,00"), (Decimal("10.00"), "X"))
    _eq(_pdf1("TARIFA R$ 1.234,56"), (Decimal("1234.56"), "TARIFA"))
    _eq(_pdf1("TARIFA -R$ 1.234,56"), (Decimal("-1234.56"), "TARIFA"))
    _eq(_pdf1("TARIFA (R$ 10,00)"), (Decimal("-10.00"), "TARIFA"))
    _eq(_pdf1("TED R$10,00-"), (Decimal("-10.00"), "TED"))


# ---------------------------------------------------------------- D15: linha de saldo do PDF
@caso("D15 PDF: SALDO DO DIA e Saldo Anterior nao viram lancamento; o lancamento ao lado fica")
def _():
    _eq(_pdf_text_to_txns("01/01/2026 SALDO DO DIA 1.000,00\n01/01/2026 Saldo Anterior 900,00"), [])
    t = _pdf_text_to_txns("01/01/2026 SALDO DO DIA 1.000,00\n01/01/2026 PIX RECEBIDO 100,00 1.100,00")
    _eq([(x["valor"], x["descricao"]) for x in t], [(Decimal("100.00"), "PIX RECEBIDO")])


@caso("D15 PDF: Saldo anterior sem data entre dois lancamentos nao come o anterior")
def _():
    t = _pdf_text_to_txns("01/01/2026 PIX RECEBIDO 100,00\nSaldo anterior 900,00\n02/01/2026 PAGAMENTO 50,00-")
    _eq([(x["descricao"], x["valor"]) for x in t], [("PIX RECEBIDO", Decimal("100.00")), ("PAGAMENTO", Decimal("-50.00"))])


@caso("D15 PDF: SALDO DO DIA sem data apos o lancamento nao vira continuacao")
def _():
    t = _pdf_text_to_txns("01/01/2026 PIX RECEBIDO 100,00\nSALDO DO DIA 1.100,00")
    _eq([(x["descricao"], x["valor"]) for x in t], [("PIX RECEBIDO", Decimal("100.00"))])


@caso("D15 PDF: rotulo de saldo quebrado abaixo da data e do valor e saldo (nao vira credito de 1000)")
def _():
    t = _pdf_text_to_txns("01/01/2026 1.000,00\nSALDO ANTERIOR\n02/01/2026 PIX RECEBIDO 100,00")
    _eq([(x["descricao"], x["valor"]) for x in t], [("PIX RECEBIDO", Decimal("100.00"))])


@caso("D15 PDF: rotulo de saldo sem valor depois de um lancamento e continuacao; o lancamento fica")
def _():
    t = _pdf_text_to_txns("01/01/2026 PIX RECEBIDO 100,00\nSALDO ANTERIOR\n02/01/2026 PAGAMENTO 50,00-")
    _eq([x["valor"] for x in t], [Decimal("100.00"), Decimal("-50.00")])
    # Gate 2 p3: linha datada so com a data; o rotulo e a 1a continuacao (PIX), nao a descricao acumulada
    t = _pdf_text_to_txns("01/01/2026\nPIX RECEBIDO 100,00\nSALDO ANTERIOR\n02/01/2026 PAGAMENTO 50,00-")
    _eq([x["valor"] for x in t], [Decimal("100.00"), Decimal("-50.00")])


@caso("D15 PDF: matriz de layouts (lancamento e saldo, datados ou nao, rotulo e valor quebrados) -> so os lancamentos")
def _():
    import itertools
    d = "01/01/2026"

    def lanc(i, k):
        v, h = f"{100 + i},00", f"PIX FORNECEDOR {i}"
        return {1: [f"{d} {h} {v}"], 2: [d, f"{h} {v}"], 3: [f"{d} {v}", h], 4: [f"{d} {h}", v],
                5: [f"{d} {h} {v}", "MAIS TEXTO DO HISTORICO"], 6: [f"{d} {h} {v} 9.999,00"]}[k]

    def saldo(i, k):
        v = f"{5000 + i}.000,00"
        return {1: [f"{d} SALDO ANTERIOR {v}"], 2: [f"SALDO DO DIA {v}"], 3: [f"{d} {v}", "SALDO ANTERIOR"],
                4: [d, f"SALDO ANTERIOR {v}"], 5: ["SALDO ANTERIOR"], 6: [f"{d} Saldo do dia {v}"],
                7: [f"{d} *** SALDO ANTERIOR *** {v}"]}[k]

    regs = [(lanc, k) for k in range(1, 7)] + [(saldo, k) for k in range(1, 8)]
    erradas = 0
    for tam in (1, 2, 3):
        for seq in itertools.product(regs, repeat=tam):
            linhas, esperado = [], []
            for i, (f, k) in enumerate(seq):
                linhas += f(i, k)
                if f is lanc:
                    esperado.append(Decimal(f"{100 + i}.00"))
            erradas += [t["valor"] for t in _pdf_text_to_txns("\n".join(linhas))] != esperado
    _eq(erradas, 0)


@caso("D15 PDF: 'saldo' no meio da descricao nao descarta (TRANSFERENCIA SALDO APLICACAO fica, como no tabular)")
def _():
    _eq(_pdf1("TRANSFERENCIA SALDO APLICACAO 50,00"), (Decimal("50.00"), "TRANSFERENCIA SALDO APLICACAO"))


# ---------------------------------------------------------------- D13: "+" explicito vale na linha
def _tab(*linhas, saldo=False):
    cab = ["Data", "Historico", "Valor"] + (["Saldo"] if saldo else [])
    r = ingest_tabular_rows([cab] + [list(x) for x in linhas])
    return r["status"], [t["valor"] for t in r["transacoes"]], r["aviso"]


@caso("D13 tabular: +100,00 sem coluna de saldo = 100.00, OK (nao vira debito)")
def _():
    _eq(_tab(("02/01/2026", "PIX CLIENTE", "+100,00"))[:2], ("OK", [Decimal("100.00")]))


@caso("D13 tabular: +100,00 e 50,00 de PAGAMENTO = 100.00 e -50.00, com aviso de palavra-chave so pela 2a")
def _():
    st, vals, aviso = _tab(("02/01/2026", "PIX CLIENTE", "+100,00"), ("02/01/2026", "PAGAMENTO", "50,00"))
    _eq((st, vals), ("ATENCAO", [Decimal("100.00"), Decimal("-50.00")]))
    assert "palavra-chave" in aviso, aviso
    st, vals, aviso = _tab(("02/01/2026", "PAGAMENTO", "+100,00"), ("03/01/2026", "PIX CLIENTE", "+30,00"))
    _eq((st, vals, aviso), ("OK", [Decimal("100.00"), Decimal("30.00")], ""))


@caso("D13 tabular: com coluna de saldo, a linha com + avanca o saldo anterior e a seguinte usa o dela")
def _():
    st, vals, aviso = _tab(("01/01/2026", "A", "+100,00", "1.100,00"), ("02/01/2026", "B", "50,00", "1.050,00"),
                           saldo=True)
    _eq((st, vals, aviso), ("OK", [Decimal("100.00"), Decimal("-50.00")], ""))


@caso("D13 tabular: modo signed (algum negativo) segue como hoje; + sozinho na celula e ignorado")
def _():
    _eq(_tab(("02/01/2026", "A", "+100,00"), ("02/01/2026", "B", "-50,00"))[:2],
        ("OK", [Decimal("100.00"), Decimal("-50.00")]))
    r = ingest_tabular_rows([["Data", "Historico", "Valor"], ["02/01/2026", "A", "+"], ["02/01/2026", "B", "+20,00"]])
    _eq([t["valor"] for t in r["transacoes"]], [Decimal("20.00")])


# ---------------------------------------------------------------- D12: OCR e tabelas do PDF fora do orcamento
import contextlib                                                                   # noqa: E402
import types                                                                        # noqa: E402
import time as _time                                                                # noqa: E402
import ingest_extrato as _ie                                                        # noqa: E402

TEXTO_LONGO = "Extrato de conta corrente, periodo de janeiro de 2026, sem nenhum lancamento neste texto de teste."


@contextlib.contextmanager
def _pdf_falso(paginas_ocr=0, passo_render=0, paginas_txt=(), passo_tabela=0, tabelas=()):
    """pypdfium2/pdfplumber falsos + OCR stubado + relogio que so anda por render/extract_tables. Restaura tudo."""
    estado = {"t": 0.0}
    salvo = (sys.modules.get("pypdfium2"), sys.modules.get("pdfplumber"), _ie.ocr_disponivel,
             _ie._ocr_texto_de_pil, _time.monotonic)

    class Pg:
        def render(self, scale=2):
            estado["t"] += passo_render
            return types.SimpleNamespace(to_pil=lambda: None)

    class Doc:
        def __init__(self, path): pass
        def __len__(self): return paginas_ocr
        def __getitem__(self, i): return Pg()
        def close(self): pass

    class PlPg:
        def __init__(self, txt): self.txt = txt
        def extract_text(self): return self.txt
        def extract_tables(self):
            estado["t"] += passo_tabela
            return [list(tabelas)] if tabelas else []

    class PlDoc:
        def __init__(self): self.pages = [PlPg(t) for t in paginas_txt]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    sys.modules["pypdfium2"] = types.SimpleNamespace(PdfDocument=Doc)
    sys.modules["pdfplumber"] = types.SimpleNamespace(open=lambda path: PlDoc())
    n = {"i": 0}

    def ocr_pagina(im):
        n["i"] += 1
        return f"0{n['i']}/01/2026 PAGAMENTO PAG{n['i']} 10,00-"
    _ie.ocr_disponivel = lambda: True
    _ie._ocr_texto_de_pil = ocr_pagina
    _time.monotonic = lambda: estado["t"]
    try:
        yield
    finally:
        for nome, v in (("pypdfium2", salvo[0]), ("pdfplumber", salvo[1])):
            if v is None:
                sys.modules.pop(nome, None)
            else:
                sys.modules[nome] = v
        _ie.ocr_disponivel, _ie._ocr_texto_de_pil, _time.monotonic = salvo[2], salvo[3], salvo[4]


AVISO_OCR = "PDF escaneado grande demais para o OCR (>60s): divida o periodo ou mande OFX/CSV"


@caso("D12 OCR: orcamento estoura depois da 1a pagina -> TIMEOUT, 0 transacoes, aviso fixo (nunca parcial)")
def _():
    with _pdf_falso(paginas_ocr=3, passo_render=40, paginas_txt=("",)):
        r = _ie.ingest_extrato("x.pdf", ocr=True)
    _eq((r.status, len(r.transacoes), r.aviso), ("TIMEOUT", 0, AVISO_OCR))


@caso("D12 OCR: dentro do orcamento entrega as transacoes das 3 paginas")
def _():
    with _pdf_falso(paginas_ocr=3, passo_render=1, paginas_txt=("",)):
        r = _ie.ingest_extrato("x.pdf", ocr=True)
    _eq((r.status, len(r.transacoes)), ("ATENCAO", 3))


@caso("D12 tabelas: orcamento estoura no laco de extract_tables -> o mesmo TIMEOUT do laco de texto")
def _():
    with _pdf_falso(paginas_txt=(TEXTO_LONGO, TEXTO_LONGO), passo_tabela=40,
                    tabelas=(["Data", "Historico", "Valor"], ["02/01/2026", "PIX", "-10,00"])):
        r = _ie.ingest_extrato("x.pdf")
    _eq((r.status, len(r.transacoes)), ("TIMEOUT", 0))
    assert "30s" in r.aviso and "\u2014" not in r.aviso, r.aviso
    with _pdf_falso(paginas_txt=(TEXTO_LONGO, TEXTO_LONGO), passo_tabela=1,
                    tabelas=(["Data", "Historico", "Valor"], ["02/01/2026", "PIX", "-10,00"])):
        r = _ie.ingest_extrato("x.pdf")
    _eq(len(r.transacoes), 2)       # uma tabela por pagina, dentro do orcamento


# ---------------------------------------------------------------- D17: texto do arquivo nunca vira formula
def _conc_formula():
    e = {"data": D, "valor": Decimal("-100.00"), "doc": "@SUM(A1)", "descricao": "=1+1", "contraparte": "x",
         "cpf_cnpj": None, "identificador": None}
    return match_banco([e], [])


@caso("D17 XLSX: descricao =1+1 e doc @SUM(A1) saem como texto literal (data_type s); valor segue numerico")
def _():
    try:
        import openpyxl
    except ImportError:
        return                                  # sem openpyxl o relatorio e o CSV (caso seguinte)
    with tempfile.TemporaryDirectory() as d:
        wb = openpyxl.load_workbook(conciliar._escreve_relatorio(_conc_formula(), d))
        ws = [w for w in wb.worksheets if w.title != wb.worksheets[0].title][0]
        cel = {c.value: c for row in ws.iter_rows(min_row=3) for c in row if c.value is not None}
        wb.close()
    for txt in ("=1+1", "@SUM(A1)"):
        _eq((cel[txt].data_type, cel[txt].value), ("s", txt))
    _eq(cel[-100.0].data_type, "n")


@caso("D17 CSV (sem openpyxl): =1+1 e @SUM(A1) levam apostrofo; valor -100.00 nao")
def _():
    import csv
    salvo = sys.modules.get("openpyxl", False)
    sys.modules["openpyxl"] = None              # import openpyxl -> ImportError
    try:
        with tempfile.TemporaryDirectory() as d:
            with open(conciliar._escreve_relatorio(_conc_formula(), d), encoding="utf-8-sig", newline="") as f:
                linhas = list(csv.reader(f, delimiter=";"))
    finally:
        if salvo is False:
            sys.modules.pop("openpyxl", None)
        else:
            sys.modules["openpyxl"] = salvo
    h, l = linhas[0], linhas[1]
    _eq((l[h.index("doc")], l[h.index("descricao")], l[h.index("valor")]), ("'@SUM(A1)", "'=1+1", "-100.00"))


@caso("D17 posicao.csv: ACCTID =1+1 sai como '=1+1; o proprio saldo nao leva prefixo")
def _():
    with tempfile.TemporaryDirectory() as d:
        pasta, out = _pasta(d, {"a.ofx": _ofx(conta="=1+1", saldo="1000.00")}), os.path.join(d, "res")
        r = subprocess.run([sys.executable, CLI, "posicao", "--pasta", pasta, "--out", out],
                           capture_output=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, (r.returncode, r.stderr)
        with open(os.path.join(out, "posicao.csv"), encoding="utf-8-sig") as f:
            txt = f.read()
    assert ";'=1+1;" in txt and ";=1+1;" not in txt, txt
    assert ";1000.00;" in txt, txt


# ---------------------------------------------------------------- D18: OFX multiconta fica fora do caixa
def _ofx_multi(*contas_saldos):
    """OFX ficticio com varias contas (conta, saldo); o parser le o saldo so da 1a."""
    corpo = "".join(
        f"<STMTTRNRS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<BRANCHID>1<ACCTID>{c}<ACCTTYPE>CHECKING"
        "</BANKACCTFROM><BANKTRANLIST>\n<STMTTRN><DTPOSTED>20260102<TRNAMT>-10.00<FITID>F1<MEMO>TESTE</STMTTRN>\n"
        f"</BANKTRANLIST><LEDGERBAL><BALAMT>{s}<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS>"
        for c, s in contas_saldos)
    return "OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1>" + corpo + "</BANKMSGSRSV1></OFX>"


AVISO_MULTI = "[!] 1 arquivo(s) com mais de uma conta fora do caixa: exporte uma conta por arquivo"


@caso("D18 posicao: OFX de 2 contas (100 e 200) fica fora com 'multiconta'; o de 1 conta (50) e o total; linha [!]")
def _():
    arq = {"a.ofx": _ofx_multi(("111", "100.00"), ("222", "200.00")), "b.ofx": _ofx(conta="333", saldo="50.00")}
    cons = _cons(arq)
    _eq(cons.total_caixa, Decimal("50.00"))
    _eq([(c.arquivo, c.entra_no_caixa, c.motivo_fora) for c in cons.contas],
        [("a.ofx", False, "multiconta"), ("b.ofx", True, "")])
    linhas, res = _posicao_cli(arq)
    _eq((res["total_caixa"], res["n_contas_no_caixa"], res["n_arquivos_multi_conta"]), ("50.00", 1, 1))
    assert AVISO_MULTI in linhas, linhas


@caso("D18 posicao: --forcar-conta nao poe o multiconta no caixa; multiconta sem LEDGERBAL tambem e 'multiconta'")
def _():
    multi = _ofx_multi(("111", "100.00"), ("222", "200.00"))
    with tempfile.TemporaryDirectory() as d:
        parsed = posicao.varrer_pasta(_pasta(d, {"a.ofx": multi, "b.ofx": _ofx(conta="333", saldo="50.00")}))
        cons = posicao.consolidar_extratos(parsed, forcar_conta=["a.ofx"])
    _eq((cons.total_caixa, cons.contas[0].motivo_fora), (Decimal("50.00"), "multiconta"))
    sem_saldo = multi.replace("<LEDGERBAL>", "<XX>").replace("</LEDGERBAL>", "</XX>")
    cons = _cons({"a.ofx": sem_saldo})
    _eq((cons.contas[0].entra_no_caixa, cons.contas[0].motivo_fora), (False, "multiconta"))


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {type(e).__name__}"); print(f"  XX   {nome}  -> EXCECAO {type(e).__name__}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> CORRECOES DE ABERTURA OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
