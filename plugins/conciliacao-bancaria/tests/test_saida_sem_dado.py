# -*- coding: utf-8 -*-
"""Saida do CLI sem texto do arquivo da pessoa. O stdout, o stderr e o resumo.json sao o canal que a IA le:
so contagem, total, saldo, codigo, numero de linha, coluna canonica, banco validado, conta mascarada e rotulo
de subpasta. Celula, tag do OFX, texto de excecao, traceback e nome de arquivo ficam locais.

CANARIO: "CANARIO SILVA 987654,32" entra em toda coluna de texto, em celula invalida, em linha que quebra o
parse e nas tags do OFX. O CLI roda por subprocess e nem CANARIO nem 987654 podem aparecer em stdout, stderr
nem em qualquer resumo.json, em nenhum modo. Colunas numericas VALIDAS usam outros valores (o total, o saldo e a
contagem sao saida permitida e nao podem casar o marcador por acaso).

Stdlib + openpyxl quando houver (sem openpyxl, o pedaco que o usa imprime [SKIP]).
Rodar:  python tests/test_saida_sem_dado.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
CLI = os.path.join(SCRIPTS, "conciliar.py")
sys.path.insert(0, os.path.join(SCRIPTS, "engine"))
sys.path.insert(0, SCRIPTS)
import conciliar                                  # noqa: E402
import ingest_ofx                                 # noqa: E402
from ingest_extrato import ingest_extrato         # noqa: E402

try:
    import openpyxl
except ImportError:                               # pragma: no cover
    openpyxl = None

CAN = "CANARIO SILVA"
NUM = "987654,32"
MARC = f"{CAN} {NUM}"
PROIBIDOS = ("CANARIO", "987654")
MASC = "•" * 4 + "32"                   # conta mascarada: 2 ultimos caracteres do ACCTID marcador
# frase fixa do _TEMPLATE_MAIN (scripts/d0/checar_saida_sem_dado.py): sem o nome do tipo da excecao
FRASE = "erro inesperado; o detalhe nao e impresso para nao expor o arquivo"

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


# ---------------------------------------------------------------- fixtures
def _w(path, content, mode="w"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if mode == "w":
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    else:
        with open(path, "wb") as f:
            f.write(content)
    return path


def _ofx(balamt="650.00", memo=MARC, cartao=False):
    """OFX com o marcador em BANKID, ACCTID, ACCTTYPE, CURDEF, MEMO e NAME. Valores numericos validos
    (TRNAMT, BALAMT) sao outros; balamt=MARC faz o OFX sem transacao legivel (TRNAMT e BALAMT com o marcador: VAZIO)."""
    t1, t2 = (MARC, MARC) if balamt == MARC else ("1500.00", "-850.00")
    if cartao:
        abre, fecha = "CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS", "CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1"
        de = f"<CCACCTFROM><ACCTID>{MARC}</CCACCTFROM>"
    else:
        abre, fecha = "BANKMSGSRSV1><STMTTRNRS><STMTRS", "STMTRS></STMTTRNRS></BANKMSGSRSV1"
        de = f"<BANKACCTFROM><BANKID>{MARC}<ACCTID>{MARC}<ACCTTYPE>{MARC}</BANKACCTFROM>"
    return ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><" + abre + f"><CURDEF>{MARC}" + de + "<BANKTRANLIST>\n"
            f"<STMTTRN><DTPOSTED>20260102<TRNAMT>{t1}<FITID>F1<MEMO>{memo}</STMTTRN>\n"
            f"<STMTTRN><DTPOSTED>20260103<TRNAMT>{t2}<FITID>F2<NAME>{MARC}</STMTTRN>\n"
            f"</BANKTRANLIST><LEDGERBAL><BALAMT>{balamt}<DTASOF>20260131</LEDGERBAL></" + fecha + "></OFX>")


EXT_CSV = (f"Data;Histórico;Valor\n"
           f"02/01/2026;{MARC};1500,00\n"
           f"03/01/2026;{MARC};-850,00\n"
           f"{MARC};{MARC};{MARC}\n"                    # celula invalida em toda coluna
           f"\"{MARC};x;y\n")                           # linha que quebra o parse (aspa aberta)

EXT_XLS_HTML = ("<html><body><table>"
                "<tr><th>Data</th><th>Histórico</th><th>Valor</th></tr>"
                f"<tr><td>02/01/2026</td><td>{MARC}</td><td>1500,00</td></tr>"
                f"<tr><td>03/01/2026</td><td>{MARC}</td><td>-850,00</td></tr>"
                f"<tr><td>{MARC}</td><td>{MARC}</td><td>{MARC}</td></tr>"
                "</table></body></html>")

RAZ_HEAD = "Data;Documento;Contraparte;Valor;Historico\n"
RAZ_OK = RAZ_HEAD + f"02/01/2026;1;{MARC};1.500,00;{MARC}\n03/01/2026;2;{MARC};-850,00;{MARC}\n"
# linha 4: data invalida; linha 5: valor invalido; linha 6: mais campos que o cabecalho; linha 7: so um campo
RAZ_RUIM = (RAZ_OK + f"{MARC};3;{MARC};10,00;{MARC}\n04/01/2026;4;{MARC};{MARC};{MARC}\n"
            f"05/01/2026;5;{MARC};20,00;{MARC};{MARC};{MARC}\n{MARC}\n")
RAZ_RUIM_ERROS = ["linha 4, coluna data: data_invalida", "linha 5, coluna valor: valor_invalido",
                  "linha 7, coluna data: data_invalida; coluna valor: valor_vazio"]
RAZ_SEM_CAB = f"02/01/2026;1;{MARC};1.500,00;{MARC}\n03/01/2026;2;{MARC};-850,00;{MARC}\n"   # o marcador repete: o DictReader funde as chaves iguais (4 colunas, nao 5)
RAZ_28 = RAZ_HEAD + f"02/01/2026;1;{MARC};{'1' * 30};{MARC}\n"   # >28 digitos: quantize levanta InvalidOperation


def _xlsx(path, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in linhas:
        ws.append(r)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path


XLSX_HEAD = ["Data", "Documento", "Contraparte", "Valor", "Historico"]
XLSX_OK = [XLSX_HEAD, ["02/01/2026", 1, MARC, "1.500,00", MARC], ["03/01/2026", 2, MARC, "-850,00", MARC]]
XLSX_RUIM = XLSX_OK + [[MARC, 3, MARC, "10,00", MARC], ["04/01/2026", 4, MARC, MARC, MARC]]
XLSX_NUM = [XLSX_HEAD, ["02/01/2026", 1, 12345, "1.500,00", 777], ["03/01/2026", 2, 12345, "-850,00", 777]]


# ---------------------------------------------------------------- execucao e checagens
def _run(args, prelude=None):
    """Roda o CLI em subprocess. `prelude` (codigo Python) roda antes do CLI, no mesmo processo, p/ trocar
    uma funcao (Sheets, ingest) sem rede. -> (rc, stdout, stderr)."""
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}   # pipe no Windows: o main reconfigura p/ utf-8
    if prelude is None:
        cmd = [sys.executable, CLI] + args
    else:
        boot = ("import sys, runpy\n"
                f"sys.path[:0] = [{os.path.join(SCRIPTS, 'engine')!r}, {SCRIPTS!r}]\n"
                + prelude + "\n"
                f"sys.argv = [{CLI!r}] + {args!r}\n"
                f"runpy.run_path({CLI!r}, run_name='__main__')\n")
        cmd = [sys.executable, "-c", boot]
    p = subprocess.run(cmd, capture_output=True, env=env)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


def _resumos(out):
    """Todo resumo.json sob `out`, como texto (chaves e valores)."""
    achados = []
    for raiz, _d, arqs in os.walk(out):
        for a in arqs:
            if a == "resumo.json":
                achados.append(json.dumps(json.load(open(os.path.join(raiz, a), encoding="utf-8")), ensure_ascii=False))
    return achados


def _sem_canario(texto, onde):
    for p in PROIBIDOS:
        assert p not in texto, f"{p} vazou em {onde}:\n{texto}"


def _limpo(rc_out_err, out_dir=None, onde=""):
    """stdout, stderr e todo resumo.json sem o canario; stderr sem traceback. -> (rc, out, err)."""
    rc, out, err = rc_out_err
    _sem_canario(out, onde + " stdout")
    _sem_canario(err, onde + " stderr")
    assert "Traceback" not in err and "Traceback" not in out, f"traceback em {onde}:\n{err}"
    if out_dir:
        for r in _resumos(out_dir):
            _sem_canario(r, onde + " resumo.json")
    return rc, out, err


def _carrega(out_dir):
    return json.load(open(os.path.join(out_dir, "resumo.json"), encoding="utf-8"))


def _extratos(d):
    """Os 4 extratos do canario: ofx valido, ofx sem transacao legivel, csv, xls em HTML."""
    return {
        "ofx": _w(os.path.join(d, "e.ofx"), _ofx()),
        "ofx_ruim": _w(os.path.join(d, "e_ruim.ofx"), _ofx(balamt=MARC)),
        "csv": _w(os.path.join(d, "e.csv"), EXT_CSV),
        "xls_html": _w(os.path.join(d, "e.xls"), EXT_XLS_HTML),
    }


def _razoes(d):
    r = {"csv_ok": _w(os.path.join(d, "r_ok.csv"), RAZ_OK),
         "csv_ruim": _w(os.path.join(d, "r_ruim.csv"), RAZ_RUIM),
         "csv_sem_cab": _w(os.path.join(d, "r_sem_cab.csv"), RAZ_SEM_CAB)}
    if openpyxl:
        r["xlsx_ok"] = _xlsx(os.path.join(d, "r_ok.xlsx"), XLSX_OK)
        r["xlsx_ruim"] = _xlsx(os.path.join(d, "r_ruim.xlsx"), XLSX_RUIM)
        r["xlsx_numerico"] = _xlsx(os.path.join(d, "r_num.xlsx"), XLSX_NUM)
    return r


# ---------------------------------------------------------------- V1: canario em todos os modos
@caso("V1 validar e conciliar: 4 extratos x razoes (csv e xlsx); sem canario em stdout, stderr e resumo.json")
def _():
    if not openpyxl:
        print("       [SKIP] openpyxl ausente: razao xlsx fora do canario")
    with tempfile.TemporaryDirectory() as d:
        ext, raz = _extratos(d), _razoes(d)
        for ne, e in ext.items():
            for nr, r in raz.items():
                onde = f"{ne} x {nr}"
                rc, out, _ = _limpo(_run(["validar", "--extrato", e, "--razao", r]), onde=f"validar {onde}")
                assert "{" in out, out                          # a saida JSON da validacao existe
                esperado_ok = ne != "ofx_ruim" and nr in ("csv_ok", "xlsx_ok", "xlsx_numerico")
                assert (rc == 0) == esperado_ok and rc in (0, 2), (onde, rc, out)
                od = os.path.join(d, f"o_{ne}_{nr}")
                rc, out, _ = _limpo(_run(["conciliar", "--extrato", e, "--razao", r, "--saldo-razao", "650,00",
                                          "--saldo-extrato", "650,00", "--out", od]), od, onde=f"conciliar {onde}")
                assert (rc in (0, 3)) == esperado_ok and (rc == 2 or esperado_ok), (onde, rc, out)
                if esperado_ok:                                  # alcancou a saida: resumo.json com as contagens
                    assert os.path.isfile(os.path.join(od, "resumo.json")), onde
                    assert "taxa_conciliacao_pct" in _carrega(od), onde
                else:
                    assert "Nada foi conciliado" in out, (onde, out)


@caso("V1 OFX valido com o marcador nas tags: validar mostra banco '?', conta mascarada, tipo e moeda '?'")
def _():
    with tempfile.TemporaryDirectory() as d:
        e = _w(os.path.join(d, "e.ofx"), _ofx())
        r = _w(os.path.join(d, "r.csv"), RAZ_OK)
        rc, out, _ = _limpo(_run(["validar", "--extrato", e, "--razao", r]), onde="validar ofx valido")
        assert rc == 0, out
        extrato = json.loads(out[:out.rindex("}") + 1])["extrato"]
        assert (extrato["banco"], extrato["conta"], extrato["tipo"], extrato["moeda"]) == ("?", MASC, "?", "?"), extrato
        assert extrato["transacoes"] == 2 and extrato["creditos"] == 1 and extrato["debitos"] == 1, extrato


def _pasta(d):
    """Pasta do mes: 1 subpasta por combinacao (rotulos neutros); nome de arquivo com o canario."""
    pasta = os.path.join(d, "mes")
    ext = {"ofx": ("CANARIO_SILVA_987654.ofx", _ofx()), "ofx_ruim": ("CANARIO_SILVA_987654.ofx", _ofx(balamt=MARC)),
           "csv": ("CANARIO_SILVA_987654.csv", EXT_CSV), "xls": ("CANARIO_SILVA_987654.xls", EXT_XLS_HTML)}
    raz = {"ok": ("razao.csv", RAZ_OK), "ruim": ("razao.csv", RAZ_RUIM), "sem_cab": ("razao.csv", RAZ_SEM_CAB)}
    for ne, (nome_e, conteudo_e) in ext.items():
        for nr, (nome_r, conteudo_r) in raz.items():
            sub = os.path.join(pasta, f"c_{ne}_{nr}")
            _w(os.path.join(sub, nome_e), conteudo_e)
            _w(os.path.join(sub, nome_r), conteudo_r)
    if openpyxl:
        sub = os.path.join(pasta, "c_ofx_xlsx_numerico")
        _w(os.path.join(sub, "CANARIO_SILVA_987654.ofx"), _ofx())
        _xlsx(os.path.join(sub, "razao.xlsx"), XLSX_NUM)
    return pasta


@caso("V1 pasta: sem canario (nome de arquivo e celulas); conta so pelo rotulo da subpasta; razao ruim nao concilia")
def _():
    with tempfile.TemporaryDirectory() as d:
        pasta, od = _pasta(d), os.path.join(d, "res")
        rc, out, _ = _limpo(_run(["pasta", "--pasta", pasta, "--out", od]), od, onde="pasta")
        assert rc == 0, out
        res = _carrega(od)
        por = {c["conta"]: c for c in res["contas"]}
        assert por["c_ofx_ok"]["tem_razao"] is True and "taxa_pct" in por["c_ofx_ok"], por["c_ofx_ok"]
        for k in ("c_ofx_ruim_ok", "c_ofx_ruim_ruim"):
            assert por[k]["status_extrato"] == "VAZIO" and por[k]["precisa_acao"] is True, por[k]
        for k in ("c_ofx_ruim", "c_csv_ruim", "c_xls_ruim", "c_ofx_sem_cab", "c_csv_sem_cab"):
            assert por[k].get("razao_reprovada") is True and por[k]["tem_razao"] is False, (k, por[k])
            assert "taxa_pct" not in por[k], k
        assert os.path.isfile(os.path.join(pasta, "c_ofx_ok", "conciliacao.xlsx")) or not openpyxl


@caso("V1 posicao: nome de arquivo, ACCTID, BANKID, ACCTTYPE e CURDEF fora da saida; posicao.csv local tem o arquivo")
def _():
    with tempfile.TemporaryDirectory() as d:
        pasta, od = os.path.join(d, "ofx"), os.path.join(d, "res")
        _w(os.path.join(pasta, "CANARIO_SILVA_987654.ofx"), _ofx())
        os.makedirs(os.path.join(pasta, "CANARIO_SILVA_987654_ruim.ofx"))   # .ofx que nao abre: ilegivel
        _w(os.path.join(pasta, "CANARIO_SILVA_987654_cartao.ofx"), _ofx(cartao=True, balamt="-10.00"))
        rc, out, err = _limpo(_run(["posicao", "--pasta", pasta, "--saldo-minimo", "100", "--out", od]), od, onde="posicao")
        assert rc == 0, (out, err)
        res = _carrega(od)
        assert res["erros_parse"] == 1 and res["n_contas_no_caixa"] == 1 and res["n_cartoes_fora"] == 1, res
        assert res["por_banco"] == {"?": "650.00"}, res["por_banco"]
        assert [(c["banco"], c["conta"], c["tipo"]) for c in res["contas"]] == [("?", MASC, "?"), ("?", MASC, "cartao")], res["contas"]
        csv_local = open(os.path.join(od, "posicao.csv"), encoding="utf-8-sig").read()
        assert "CANARIO_SILVA_987654.ofx" in csv_local and MARC in csv_local, csv_local   # o detalhe local fica
        # V2: as linhas [!] e [i] da posicao, exatas
        linhas = out.splitlines()
        assert "[!] 1 arquivo(s) ilegiveis (ignorados)" in linhas, linhas
        assert f"[i] Cartoes fora do caixa (envelope de cartao): ? {MASC}" in linhas, linhas
        assert ("    Se algum for conta (ex.: NuConta), inclua com --forcar-conta nome.ofx;"
                " o nome do arquivo esta no posicao.csv local") in linhas, linhas
        assert f"{'?':<8}{MASC:<10}{'?':<9}{'R$ 650,00':>16}{'sim':>8}" in linhas, linhas


@caso("V1 posicao --sheet com push que lanca Exception(canario): so o tipo sai, rc 4, sem rede")
def _():
    with tempfile.TemporaryDirectory() as d:
        pasta, od = os.path.join(d, "ofx"), os.path.join(d, "res")
        _w(os.path.join(pasta, "a.ofx"), _ofx())
        prel = ("import sheets_push\n"
                "def _boom(*a, **k):\n"
                f"    raise Exception({CAN!r})\n"
                "sheets_push.push_para_sheet = _boom\n")
        rc, out, err = _limpo(_run(["posicao", "--pasta", pasta, "--out", od, "--sheet", "ID_FALSO"], prelude=prel), od, onde="sheet")
        assert rc == 4, (rc, out, err)
        assert "[!] Push p/ Sheet nao concluido (Exception)" in out.splitlines(), out
        assert err == "", err


# ---------------------------------------------------------------- V2: listas exatas
@caso("V2 _razao_canonico: erros exatos (codigo e numero de linha), vazio != invalido, >28 digitos, coluna ausente")
def _():
    cols = {"data": "Data", "valor": "Valor"}
    assert conciliar._razao_canonico([{"Data": " ", "Valor": ""}], cols)[1] == ["linha 2, coluna data: data_vazia; coluna valor: valor_vazio"]
    assert conciliar._razao_canonico([{"Data": "02/01/2026", "Valor": None}], cols)[1] == ["linha 2, coluna valor: valor_vazio"]
    assert conciliar._razao_canonico([{"Data": "02/01/2026"}], cols)[1] == ["linha 2, coluna valor: coluna_ausente"]
    assert conciliar._razao_canonico([{"Data": MARC, "Valor": MARC}], cols)[1] == ["linha 2, coluna data: data_invalida; coluna valor: valor_invalido"]
    assert conciliar._razao_canonico([{"Data": "02/01/2026", "Valor": "1" * 30}], cols)[1] == ["linha 2, coluna valor: valor_invalido"]
    assert conciliar._razao_canonico([{"Data": "99/99/2026", "Valor": "1,00"}], cols)[1] == ["linha 2, coluna data: data_invalida"]
    # celulas opcionais de xlsx (int, float, datetime) passam por str() antes do strip
    import datetime
    reg, erros = conciliar._razao_canonico(
        [{"Data": "02/01/2026", "Valor": "1,00", "C": 12345, "H": 1.5, "L": datetime.date(2026, 1, 2), "I": 9}],
        {**cols, "contraparte": "C", "desc": "H", "lote": "L", "ident": "I"})
    assert erros == [] and reg[0]["contraparte"] == "12345" and reg[0]["descricao"] == "1.5" and reg[0]["identificador"] == "9", (reg, erros)


@caso("V2 validar: lista exata de reprovas (razao ruim, razao sem cabecalho, OFX ilegivel) e aviso do ingest")
def _():
    with tempfile.TemporaryDirectory() as d:
        e, ruim = _w(os.path.join(d, "e.ofx"), _ofx()), _w(os.path.join(d, "ruim.ofx"), _ofx(balamt=MARC))
        r = _w(os.path.join(d, "r.csv"), RAZ_RUIM)
        ok, metad = conciliar.fase1_validar(e, r, {})
        n = len(RAZ_RUIM_ERROS)
        assert not ok and metad["reprovas"] == [
            f"{n} linha(s) da razao nao parseavel(is) (ex.: subtotal/rodape, valor vazio, data invalida): "
            + "; ".join(RAZ_RUIM_ERROS) + ". Remova-as ou corrija no modelo."], metad["reprovas"]
        sc = _w(os.path.join(d, "sc.csv"), RAZ_SEM_CAB)
        ok, metad = conciliar.fase1_validar(e, sc, {})
        assert not ok and metad["reprovas"] == [
            f"coluna obrigatoria nao detectada na razao: '{c}'. Razao esperado no formato do modelo "
            f"{list(conciliar.COLUNAS_MODELO)} (ver modelo-razao.csv; ';' como separador, valor com sinal "
            f"+entrada/-saida). Recebi 4 coluna(s) no arquivo. Reformate no modelo ou use --col-{c}."
            for c in ("data", "valor")], metad["reprovas"]
        ok, metad = conciliar.fase1_validar(ruim, _w(os.path.join(d, "ok.csv"), RAZ_OK), {})
        assert not ok and metad["reprovas"] == ["extrato sem transacoes legiveis (confira o arquivo; OFX e o formato mais seguro)."], metad["reprovas"]
        res = ingest_extrato(ruim)
        assert (res.status, res.aviso, res.txns_corrompidas) == ("VAZIO", "", 2), (res.status, res.aviso)
        # qualquer excecao do parse: so o tipo
        orig = ingest_ofx.parse_ofx
        ingest_ofx.parse_ofx = lambda p: (_ for _ in ()).throw(KeyError(MARC))
        try:
            assert ingest_extrato(e).aviso == "KeyError"
        finally:
            ingest_ofx.parse_ofx = orig


@caso("V2 pasta: aviso exato, nota 'razao reprovada' na tabela, linha [!] com ate 5 linhas e (+N); ingerida, nao conciliada")
def _():
    sete = RAZ_HEAD + "".join(f"{MARC};{i};x;1,00;y\n" for i in range(7))   # 7 linhas com data invalida: 2..8
    with tempfile.TemporaryDirectory() as d:
        pasta, od = os.path.join(d, "mes"), os.path.join(d, "res")
        _w(os.path.join(pasta, "itau", "e.ofx"), _ofx())
        _w(os.path.join(pasta, "itau", "razao.csv"), RAZ_RUIM)
        _w(os.path.join(pasta, "bradesco", "e.ofx"), _ofx())
        _w(os.path.join(pasta, "bradesco", "razao.csv"), sete)
        _w(os.path.join(pasta, "bb", "e.ofx"), _ofx())
        _w(os.path.join(pasta, "bb", "razao.csv"), RAZ_OK)
        rc, out, _ = _limpo(_run(["pasta", "--pasta", pasta, "--out", od]), od, onde="pasta v2")
        assert rc == 0, out
        por = {c["conta"]: c for c in _carrega(od)["contas"]}
        assert por["itau"]["aviso"] == "razao reprovada: 3 linha(s) invalida(s): linhas 4, 5, 7; conta so ingerida", por["itau"]
        assert por["bradesco"]["aviso"] == "razao reprovada: 7 linha(s) invalida(s): linhas 2, 3, 4, 5, 6 (+2); conta so ingerida", por["bradesco"]
        assert por["itau"]["tem_razao"] is False and por["bb"]["tem_razao"] is True
        assert _carrega(od)["resumo"] == {"contas": 3, "conciliadas": 1, "ingeridas": 2, "precisa_acao": 0, "ar_cred": 0}
        linhas = out.splitlines()
        assert "  [!] razão reprovada em: itau (3 linha(s) inválida(s): linhas 4, 5, 7)" in linhas, linhas
        assert "  [!] razão reprovada em: bradesco (7 linha(s) inválida(s): linhas 2, 3, 4, 5, 6 (+2))" in linhas, linhas
        assert any(l.startswith("  itau") and l.endswith("razao reprovada") for l in linhas), linhas
        assert any(l.startswith("  bb") and not l.endswith("razao reprovada") and "sem razao" not in l for l in linhas), linhas
        assert not any(l.endswith("sem razao") for l in linhas), linhas


@caso("V2 validadores de saida: banco so digitos (ate 5), tipo e moeda de vocabulario curto, senao '?'")
def _():
    from posicao import banco_saida, tipo_saida, moeda_saida
    assert [banco_saida(x) for x in ("341", "00001", "123456", "", None, "ab1", MARC)] == ["341", "00001", "?", "?", "?", "?", "?"]
    assert [tipo_saida(x) for x in ("CHECKING", "savings", "CREDITCARD", "", None, MARC)] == ["CHECKING", "SAVINGS", "CREDITCARD", "conta", "conta", "?"]
    assert [moeda_saida(x) for x in ("BRL", "USD", "brl", "BR", "", MARC)] == ["BRL", "USD", "?", "?", "?", "?"]


@caso("V2 resumo_agregado e Sheets: banco e tipo validados; bancos invalidos agrupam sob '?' SOMANDO os saldos")
def _():
    from decimal import Decimal
    import posicao
    import sheets_push
    with tempfile.TemporaryDirectory() as d:
        pasta = os.path.join(d, "ofx")
        _w(os.path.join(pasta, "a.ofx"), _ofx())                                              # banco invalido, 650.00
        _w(os.path.join(pasta, "b.ofx"), _ofx(balamt="100.00").replace(f"<BANKID>{MARC}", "<BANKID>XYZ"))   # tambem invalido
        _w(os.path.join(pasta, "c.ofx"), _ofx(balamt="5.00").replace(f"<BANKID>{MARC}", "<BANKID>341").replace(f"<ACCTTYPE>{MARC}", "<ACCTTYPE>CHECKING"))
        cons = posicao.consolidar_extratos(posicao.varrer_pasta(pasta))
        res = posicao.resumo_agregado(cons)
        assert res["por_banco"] == {"341": "5.00", "?": "750.00"}, res["por_banco"]
        assert [(c["banco"], c["tipo"]) for c in res["contas"]] == [("?", "?"), ("?", "?"), ("341", "CHECKING")], res["contas"]
        assert cons.contas[0].banco == MARC and cons.contas[0].tipo_conta == MARC          # objeto interno nao muda
        assert cons.total_caixa == Decimal("755.00")
        sheet = json.dumps(sheets_push.montar_linhas_agregadas(cons), ensure_ascii=False)
        _sem_canario(sheet, "linhas do Sheets")


# ---------------------------------------------------------------- V3: excecoes que escapavam
def _sem_traceback(rc_out_err, rc_esperado, frase=None, onde=""):
    rc, out, err = _limpo(rc_out_err, onde=onde)
    assert rc == rc_esperado, (onde, rc, out, err)
    if frase:
        assert err.strip() == frase, (onde, err)
    return out, err


@caso("V3 descricao com caractere de controle no OFX: o relatorio local falha, o run segue com 'relatorio nao gravado'")
def _():
    if not openpyxl:
        print("       [SKIP] openpyxl ausente: sem Excel o relatorio cai para CSV"); return
    with tempfile.TemporaryDirectory() as d:
        e = _w(os.path.join(d, "e.ofx"), _ofx(memo=f"{CAN}\x01 {NUM}"))
        r, od = _w(os.path.join(d, "r.csv"), RAZ_OK), os.path.join(d, "o")
        out, err = _sem_traceback(_run(["conciliar", "--extrato", e, "--razao", r, "--saldo-razao", "650,00", "--out", od]), 0, onde="ctrl")
        assert "  relatorio (LOCAL, dado bruto): relatorio nao gravado (IllegalCharacterError)" in out.splitlines(), out
        assert err == "" and os.path.isfile(os.path.join(od, "resumo.json"))


@caso("V3 contraparte numerica em xlsx no razao: validar, conciliar e pasta rodam sem traceback")
def _():
    if not openpyxl:
        print("       [SKIP] openpyxl ausente"); return
    with tempfile.TemporaryDirectory() as d:
        e, r = _w(os.path.join(d, "e.ofx"), _ofx()), _xlsx(os.path.join(d, "r.xlsx"), XLSX_NUM)
        _sem_traceback(_run(["validar", "--extrato", e, "--razao", r]), 0, onde="validar xlsx numerico")
        od = os.path.join(d, "o")
        _sem_traceback(_run(["conciliar", "--extrato", e, "--razao", r, "--saldo-razao", "650,00", "--out", od]), 0, onde="conciliar xlsx numerico")
        assert "taxa_conciliacao_pct" in _carrega(od)


@caso("V3 valor com mais de 28 digitos no razao e no saldo-razao.txt: razao reprovada e saldo ignorado, sem traceback")
def _():
    with tempfile.TemporaryDirectory() as d:
        e, r = _w(os.path.join(d, "e.ofx"), _ofx()), _w(os.path.join(d, "r.csv"), RAZ_28)
        out, _ = _sem_traceback(_run(["validar", "--extrato", e, "--razao", r]), 2, onde="validar 30 digitos")
        assert "linha 2, coluna valor: valor_invalido" in out, out
        pasta, od = os.path.join(d, "mes"), os.path.join(d, "res")
        _w(os.path.join(pasta, "a", "e.ofx"), _ofx())
        _w(os.path.join(pasta, "a", "razao.csv"), RAZ_OK)
        _w(os.path.join(pasta, "a", "saldo-razao.txt"), "9" * 30)
        _sem_traceback(_run(["pasta", "--pasta", pasta, "--out", od]), 0, onde="pasta saldo 30 digitos")
        conta = _carrega(od)["contas"][0]
        assert conta["tem_razao"] is True and conta["amarracao"] is None, conta
        _w(os.path.join(pasta, "b", "e.ofx"), _ofx())
        _w(os.path.join(pasta, "b", "razao.csv"), RAZ_28)
        _sem_traceback(_run(["pasta", "--pasta", pasta, "--out", od]), 0, onde="pasta razao 30 digitos")
        assert {c["conta"]: c.get("razao_reprovada") for c in _carrega(od)["contas"]} == {"a": None, "b": True}


@caso("V3 ponto de entrada: excecao forcada no main (mensagem com canario) vira a frase fixa do template, rc 2, sem traceback")
def _():
    with tempfile.TemporaryDirectory() as d:
        pasta = os.path.join(d, "mes")
        _w(os.path.join(pasta, "a", "e.ofx"), _ofx())
        prel = ("import ingest_extrato\n"
                "def _boom(*a, **k):\n"
                f"    raise Exception({CAN!r})\n"
                "ingest_extrato.ingest_extrato = _boom\n")
        out, err = _sem_traceback(_run(["pasta", "--pasta", pasta, "--out", os.path.join(d, "o")], prelude=prel), 2,
                                  frase=FRASE, onde="entrada")
        assert out == "" or "CONCILIACAO" not in out, out
        # SystemExit do argparse passa pelo template (tambem rc 2): o que distingue e a mensagem de uso, sem a frase fixa
        rc, _, err = _run(["conciliar"])
        assert rc == 2 and "usage:" in err and FRASE not in err, (rc, err)


@caso("V3 escrita em --out invalido (arquivo no lugar da pasta): frase fixa do template, rc 2, sem caminho nem traceback")
def _():
    with tempfile.TemporaryDirectory() as d:
        e, r = _w(os.path.join(d, "e.ofx"), _ofx()), _w(os.path.join(d, "r.csv"), RAZ_OK)
        alvo = _w(os.path.join(d, "arquivo.txt"), "x")
        _sem_traceback(_run(["conciliar", "--extrato", e, "--razao", r, "--saldo-razao", "650,00", "--out", alvo]), 2,
                       frase=FRASE, onde="out invalido")


# ---------------------------------------------------------------- V3: warning e log de biblioteca
AVISO = "[aviso] uma biblioteca emitiu {}; detalhe omitido (pode trazer texto do arquivo)"


def _xlsx_prop_custom(path, linhas):
    """XLSX legivel com propriedade personalizada vt:blob (tipo que o openpyxl nao conhece) de nome = marcador."""
    import zipfile
    tmp = _xlsx(path + ".tmp", linhas)
    custom = ('<?xml version="1.0" encoding="UTF-8"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
              'custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
              f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="2" name="{MARC}"><vt:blob>AA==</vt:blob></property></Properties>')
    with zipfile.ZipFile(tmp) as zi, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            dado = zi.read(item.filename)
            if item.filename == "[Content_Types].xml":
                dado = dado.replace(b"</Types>", b'<Override PartName="/docProps/custom.xml" ContentType="application/'
                                    b'vnd.openxmlformats-officedocument.custom-properties+xml"/></Types>')
            elif item.filename == "_rels/.rels":
                dado = dado.replace(b"</Relationships>", b'<Relationship Id="rIdCustom" Type="http://schemas.openxmlformats.org/'
                                    b'officeDocument/2006/relationships/custom-properties" Target="docProps/custom.xml"/></Relationships>')
            zo.writestr(item.filename, dado)
        zo.writestr("docProps/custom.xml", custom)
    os.remove(tmp)
    return path


@caso("V3 XLSX de razao com propriedade personalizada desconhecida: o UserWarning da lib sai sem o texto (validar, conciliar, pasta)")
def _():
    if not openpyxl:
        print("       [SKIP] openpyxl ausente"); return
    with tempfile.TemporaryDirectory() as d:
        e, r = _w(os.path.join(d, "e.ofx"), _ofx()), _xlsx_prop_custom(os.path.join(d, "r.xlsx"), XLSX_OK)
        frase = AVISO.format("UserWarning")
        _, err = _sem_traceback(_run(["validar", "--extrato", e, "--razao", r]), 0, onde="validar prop custom")
        assert frase in err, err                               # o warning existe e foi contido, nao some por acaso
        _, err = _sem_traceback(_run(["conciliar", "--extrato", e, "--razao", r, "--saldo-razao", "650,00",
                                      "--out", os.path.join(d, "o")]), 0, onde="conciliar prop custom")
        assert frase in err, err
        pasta = os.path.join(d, "mes")
        _w(os.path.join(pasta, "a", "e.ofx"), _ofx())
        _xlsx_prop_custom(os.path.join(pasta, "a", "razao.xlsx"), XLSX_OK)
        _, err = _sem_traceback(_run(["pasta", "--pasta", pasta, "--out", os.path.join(d, "res")]), 0, onde="pasta prop custom")
        assert frase in err, err


@caso("V3 warnings.warn e logging (pdfminer) com o marcador dentro do ingest: stderr so com a frase fixa")
def _():
    with tempfile.TemporaryDirectory() as d:
        e, r = _w(os.path.join(d, "e.ofx"), _ofx()), _w(os.path.join(d, "r.csv"), RAZ_OK)
        prel = ("import warnings, logging\n"
                "import conciliar\n"
                "_orig = conciliar.ingest_extrato\n"
                "def _wrap(*a, **k):\n"
                f"    warnings.warn({MARC!r})\n"
                f"    logging.getLogger('pdfminer').warning({MARC!r})\n"
                "    return _orig(*a, **k)\n"
                "conciliar.ingest_extrato = _wrap\n"
                f"sys.exit(conciliar.main(['validar', '--extrato', {e!r}, '--razao', {r!r}]))\n")
        rc, out, err = _limpo(_run([], prelude=prel), onde="warn + logging")
        assert rc == 0 and '"extrato"' in out, (rc, out)
        assert err.strip() == AVISO.format("UserWarning"), err   # so a frase do warning; o log do pdfminer nao imprime nada


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {type(e).__name__} {e}"); print(f"  XX   {nome}  -> EXCECAO {type(e).__name__} {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> SAIDA SEM DADO OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
