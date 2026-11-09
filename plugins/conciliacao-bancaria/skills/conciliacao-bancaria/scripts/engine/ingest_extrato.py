# -*- coding: utf-8 -*-
"""Ingestao MULTI-FORMATO do lado banco (antifragil).

O time de tesouraria manda o extrato em QUALQUER formato (OFX, CSV, XLSX, XLS, HTML
disfarcado de xls, PDF-texto, PDF-escaneado, imagem). Este modulo:
  - despacha por formato (extensao + sniff de conteudo),
  - extrai a MESMA lista canonica de transacoes do ingest_ofx (data/valor/descricao...),
  - NUNCA quebra: erro vira status claro (CORROMPIDO / PRECISA_OCR / MAPEAR_COLUNAS / VAZIO),
  - roda 100% LOCAL (o fosso de privacidade): nenhuma chamada de rede.

Convencao de sinal: +entrada / -saida (igual ao OFX e ao match_banco).
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from normalize import parse_valor, parse_data, norm_doc, extrai_cpf_cnpj, norm_cpf_cnpj

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

# keywords de credito (entrada) p/ ultimo recurso de sinal quando nao ha saldo/coluna
_KW_CRED = ("recebid", "credito", "resgate", "estorno", "devolucao", "deposito", "rend", "entrada")


@dataclass
class ExtratoResult:
    transacoes: list = field(default_factory=list)
    status: str = "OK"            # OK | ATENCAO | MAPEAR_COLUNAS | PRECISA_OCR | CORROMPIDO | VAZIO
    fonte: str = ""               # ofx | csv | xlsx | xls | html | pdf | imagem
    banco: str = ""
    conta: str = ""
    saldo_final: Decimal | None = None
    aviso: str = ""
    n_ignoradas: int = 0
    # campos OFX (SPEC-06/A2: conciliar/validar multiformato usam o mesmo objeto). Tabular usa os defaults.
    tipo_conta: str = ""          # OFX: CHECKING/SAVINGS/... (vazio p/ tabular)
    moeda: str = "BRL"
    n_contas: int = 1             # OFX: nº de contas no arquivo (>1 = multi-conta, Fase 1 reprova)
    txns_corrompidas: int = 0     # OFX: STMTTRN descartados por data/valor invalido
    eh_cartao: bool = False       # OFX: envelope de cartao de credito


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def excel_serial_to_date(serial) -> date:
    """Converte serial do Excel (sistema 1900) para date. Base 1899-12-30 cobre o bug
    do ano-bissexto de 1900 p/ datas modernas."""
    return date(1899, 12, 30) + timedelta(days=int(float(serial)))


# ----------------------------------------------------------------------------
# Nucleo tabular: list-of-lists -> transacoes canonicas. Compartilhado por
# CSV / XLSX / XLS / HTML (cada reader entrega rows; a logica de mapa e uma so).
# ----------------------------------------------------------------------------
# tokens PT + EN (o time manda export gringo tambem — ex.: Mercado Pago RELEASE_DATE).
# "credit"/"debit" sao substring de "credito"/"debito" -> cobrem PT e EN num token so.
_TOKENS_DATA = ("data", "date")
_TOKENS_VALOR = ("valor", "montante", "lancamento r$", "amount", "value")
_TOKENS_CRED = ("credito", "credit")
_TOKENS_DEB = ("debito", "debit")
_TOKENS_SALDO = ("saldo", "balance")
_TOKENS_DESC = ("histor", "descri", "lancament", "transaction_type", "movimentacao", "description")
_TOKENS_DOC = ("docto", "documento", "reference", "controle")
_TOKENS_CPF = ("cpf", "cnpj")
_TOKENS_NOME = ("nome", "razao", "favorec", "benefic", "contraparte")


def _res(txns, status, aviso="", **kw):
    return ExtratoResult(transacoes=txns, status=status, aviso=aviso, **kw)


def _cell(row, i):
    if i is None or i >= len(row):
        return None
    return row[i]


def _find_header(rows) -> int | None:
    """Acha a linha de cabecalho: a 1a (ate ~40) que tem um token de DATA e um de
    VALOR/CREDITO/DEBITO. Distingue header de linha de dado. Janela 40 cobre os blocos
    de metadados grandes (BTG/Sofisa poem o cabecalho real bem abaixo)."""
    for i, r in enumerate(rows[:40]):
        cells = [_norm(c) for c in (r or [])]
        tem_data = any(any(t in c for t in _TOKENS_DATA) for c in cells)
        tem_val = any(any(t in c for t in _TOKENS_VALOR + _TOKENS_CRED + _TOKENS_DEB) for c in cells)
        if tem_data and tem_val:
            return i
    return None


def _map_cols(header) -> dict:
    cells = [_norm(c) for c in header]

    def find(tokens, evitar=()):
        for i, c in enumerate(cells):
            if any(t in c for t in tokens) and not any(e in c for e in evitar):
                return i
        return None

    idx = {
        "data": find(_TOKENS_DATA),
        "credito": find(_TOKENS_CRED),
        "debito": find(_TOKENS_DEB),
        "valor": find(_TOKENS_VALOR, evitar=("saldo",)),
        "saldo": find(_TOKENS_SALDO),
        "doc": find(_TOKENS_DOC),
        "cpfcnpj": find(_TOKENS_CPF),
        "nome": find(_TOKENS_NOME),
    }
    # descricao: prefere histor/descri; senao um "lancament"/transaction que NAO seja a data
    desc = None
    for i, c in enumerate(cells):
        if any(t in c for t in ("histor", "descri", "transaction_type", "movimentacao")):
            desc = i
            break
    if desc is None:
        for i, c in enumerate(cells):
            if "lancament" in c and i != idx["data"]:
                desc = i
                break
    idx["desc"] = desc
    return idx


def _celula_vazia(cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def _parse_date_cell(cell):
    if _celula_vazia(cell):
        return None
    if isinstance(cell, (int, float)) and float(cell) > 40000:
        return excel_serial_to_date(cell)
    s = str(cell).strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", s) and float(s) > 40000:   # serial como string
        return excel_serial_to_date(s)
    try:
        return parse_data(s)
    except ValueError:
        return None


def _val(cell):
    if cell is None:
        return None
    s = str(cell).strip()
    if s == "" or s == "-":
        return None
    try:
        return parse_valor(s, origem="auto")
    except ValueError:
        return None


def _value_mode(data_rows, idx) -> str:
    if idx.get("credito") is not None and idx.get("debito") is not None:
        return "credito_debito"
    # ha algum valor negativo na coluna 'valor'? entao ja vem com sinal
    for r in data_rows:
        v = _val(_cell(r, idx.get("valor")))
        if v is not None and v < ZERO:
            return "signed"
    if idx.get("saldo") is not None:
        return "saldo_delta"
    return "keyword"


def _eh_linha_saldo(descn) -> bool:
    """Descricao normalizada de linha de saldo (anterior/do dia/final): nao e lancamento. Tabular e PDF."""
    return descn.startswith("saldo") or "saldo anterior" in descn


def _kw_sign(valor_abs, descn):
    return valor_abs if any(k in descn for k in _KW_CRED) else -valor_abs


def ingest_tabular_rows(rows) -> dict:
    """Recebe list-of-lists (qualquer fonte tabular) -> dict com transacoes canonicas.
    Retorna sempre (nunca lanca): status diz OK/ATENCAO/MAPEAR_COLUNAS/VAZIO."""
    rows = [r for r in (rows or []) if r is not None]
    if not any(any(c not in (None, "") for c in (r or [])) for r in rows):
        return {"transacoes": [], "status": "VAZIO", "aviso": "sem linhas", "n_ignoradas": 0}

    hi = _find_header(rows)
    if hi is None:
        return {"transacoes": [], "status": "MAPEAR_COLUNAS",
                "aviso": "nao identifiquei o cabecalho (preciso de colunas Data + Valor/Credito/Debito)",
                "n_ignoradas": 0}
    idx = _map_cols(rows[hi])
    tem_valor = idx.get("valor") is not None or (idx.get("credito") is not None and idx.get("debito") is not None)
    if idx.get("data") is None or not tem_valor:
        return {"transacoes": [], "status": "MAPEAR_COLUNAS",
                "aviso": "faltou coluna de Data ou de Valor/Credito/Debito", "n_ignoradas": 0}

    data_rows = rows[hi + 1:]
    mode = _value_mode(data_rows, idx)

    coletadas = []
    opening = None
    prev_date = None
    ignoradas = 0
    aviso = ""
    for r in data_rows:
        if not r or all(c in (None, "") for c in r):
            continue
        desc = str(_cell(r, idx.get("desc")) or "").strip()
        descn = _norm(desc)
        # linha de saldo (anterior/do dia/final) — nao e transacao; captura abertura
        if _eh_linha_saldo(descn):
            if idx.get("saldo") is not None and opening is None:
                opening = _val(_cell(r, idx["saldo"]))
            ignoradas += 1
            continue

        # valor por modo
        valor = None
        valor_abs = None
        explicito = False   # D13: celula de valor com "+" na frente = credito declarado, sem inferencia
        if mode == "credito_debito":
            cred = _val(_cell(r, idx["credito"]))
            deb = _val(_cell(r, idx["debito"]))
            if cred is not None and cred != ZERO:
                valor = abs(cred)
            elif deb is not None and deb != ZERO:
                valor = -abs(deb)
            else:
                ignoradas += 1
                continue
        else:
            v = _val(_cell(r, idx.get("valor")))
            if v is None:
                ignoradas += 1
                continue
            if mode == "signed":
                valor = v
            else:  # saldo_delta / keyword -> guarda magnitude p/ pos-processar
                valor_abs = abs(v)
                explicito = str(_cell(r, idx.get("valor"))).strip().startswith("+")

        # data: carry-forward SO com a celula vazia (extrato agrupado por dia); data preenchida e invalida
        # descarta a linha (herdar a data anterior mudaria o dia do lancamento em silencio)
        cel_data = _cell(r, idx["data"])
        dt = _parse_date_cell(cel_data)
        if dt is None and _celula_vazia(cel_data):
            dt = prev_date
        if dt is None:
            ignoradas += 1
            continue
        prev_date = dt

        cpf = norm_cpf_cnpj(_cell(r, idx.get("cpfcnpj"))) or extrai_cpf_cnpj(desc)
        nome = str(_cell(r, idx.get("nome")) or "").strip()
        saldo = _val(_cell(r, idx.get("saldo"))) if idx.get("saldo") is not None else None
        coletadas.append({
            "data": dt, "valor": valor, "valor_abs": valor_abs, "saldo": saldo, "explicito": explicito,
            "descricao": desc, "doc": norm_doc(_cell(r, idx.get("doc"))),
            "contraparte": nome or desc, "cpf_cnpj": cpf, "descn": descn,
        })

    # pos-processa sinal nos modos sem sinal explicito
    if mode in ("saldo_delta", "keyword"):
        prev = opening if opening is not None else ZERO
        usou_kw = False
        n_centavo = 0
        for c in coletadas:
            if c["explicito"]:
                c["valor"] = c["valor_abs"]
                if mode == "saldo_delta" and c["saldo"] is not None:
                    prev = c["saldo"]
                continue
            if mode == "saldo_delta" and c["saldo"] is not None:
                delta = c["saldo"] - prev
                if abs(abs(delta) - c["valor_abs"]) <= CENT and delta != ZERO:
                    # o saldo da so o SINAL; a magnitude e a do arquivo (o delta de +-1 centavo trocaria o valor)
                    c["valor"] = c["valor_abs"] if delta > ZERO else -c["valor_abs"]
                    if abs(delta) != c["valor_abs"]:
                        n_centavo += 1
                else:
                    c["valor"] = _kw_sign(c["valor_abs"], c["descn"]); usou_kw = True
                prev = c["saldo"]
            else:
                c["valor"] = _kw_sign(c["valor_abs"], c["descn"]); usou_kw = True
        avisos = []
        if usou_kw:
            avisos.append("sinal de alguns lancamentos inferido por palavra-chave (confira)")
        if n_centavo:
            avisos.append(f"{n_centavo} lancamento(s) com diferenca de centavo entre valor e saldo (confira)")
        aviso = "; ".join(avisos)

    txns = []
    for c in coletadas:
        txns.append({
            "data": c["data"], "valor": c["valor"], "doc": c["doc"],
            "descricao": c["descricao"], "contraparte": c["contraparte"],
            "cpf_cnpj": c["cpf_cnpj"], "identificador": None, "fitid": "", "tipo": "",
        })
    status = "OK" if not aviso else "ATENCAO"
    if not txns:
        status = "MAPEAR_COLUNAS"
        aviso = aviso or "nenhuma transacao extraida (so linhas de saldo/cabecalho?)"
    return {"transacoes": txns, "status": status, "aviso": aviso, "n_ignoradas": ignoradas}


# ----------------------------------------------------------------------------
# Readers por formato -> list-of-lists (alimentam o nucleo tabular).
# ----------------------------------------------------------------------------
def _read_text(path) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _cabecalho_serve(sample, delim) -> bool:
    """A amostra lida com `delim` tem cabecalho reconhecido, com Data e Valor/Credito/Debito em colunas distintas."""
    import csv
    import io
    try:
        rows = list(csv.reader(io.StringIO(sample), delimiter=delim))
    except csv.Error:
        return False
    hi = _find_header(rows)
    if hi is None:
        return False
    idx = _map_cols(rows[hi])
    d = idx.get("data")
    return d is not None and any(idx.get(k) not in (None, d) for k in ("valor", "credito", "debito"))


def _rows_from_csv(path) -> list:
    import csv
    import io
    txt = _read_text(path).replace("\r\n", "\n").replace("\r", "\n")   # normaliza fim de linha
    sample = txt[:8192]
    bons = [d for d in (";", ",") if _cabecalho_serve(sample, d)]
    # D19: o cabecalho reconhecido decide; os dois ou nenhum -> a contagem
    delim = bons[0] if len(bons) == 1 else (";" if sample.count(";") >= sample.count(",") else ",")
    try:
        # csv.reader trata newline DENTRO de campo aspeado corretamente.
        return list(csv.reader(io.StringIO(txt), delimiter=delim))
    except csv.Error:
        # export bagunçado (Bradesco: quoting/newline inconsistente) -> split tolerante.
        # Bancos BR nao poem o delimitador dentro do campo, entao isto recupera sem mangle.
        out = []
        for line in txt.split("\n"):
            out.append([c.strip().strip('"').strip() for c in line.split(delim)])
        return out


def _rows_from_xlsx(path) -> list:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def _looks_html(path) -> bool:
    head = open(path, "rb").read(4096).lower()
    return b"<html" in head or b"<table" in head or b"<!doctype html" in head


def _rows_from_html(path) -> list:
    from html.parser import HTMLParser
    import html as _html

    class _T(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables, self.cur, self.row, self.buf, self.intd = [], None, None, [], False

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.cur = []
            elif tag == "tr" and self.cur is not None:
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.intd, self.buf = True, []

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.row is not None:
                self.row.append(_html.unescape("".join(self.buf)).strip())
                self.intd = False
            elif tag == "tr" and self.row is not None:
                self.cur.append(self.row); self.row = None
            elif tag == "table" and self.cur is not None:
                self.tables.append(self.cur); self.cur = None

        def handle_data(self, data):
            if self.intd:
                self.buf.append(data)

    p = _T()
    p.feed(_read_text(path))
    return max(p.tables, key=len) if p.tables else []


def _rows_from_xls(path) -> list:
    if _looks_html(path):
        return _rows_from_html(path)
    import xlrd
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_index(0)
    return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]


# ----------------------------------------------------------------------------
# PDF: tenta tabelas (pdfplumber); senao heuristica de linha sobre o texto;
# sem texto -> PRECISA_OCR (escaneado).
# ----------------------------------------------------------------------------
_RE_DATA_INI = re.compile(r"^\s*(\d{2}/\d{2}/\d{2,4})\b")
# inteiro sem milhar (1234,56) OU milhar com ponto (1.234,56); o lookbehind impede comecar no meio de um
# numero (sem ele, "1234,56" casaria "234,56" e o valor perdia o 1o digito)
_RE_MONEY = re.compile(r"-?\(?\s*(?:R?\$)?\s*(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}\)?-?")
_RE_NAO_NUM = re.compile(r"[R$\s]")


def _pdf_text_to_txns(texto) -> list:
    """Heuristica: agrupa linhas logicas (uma comeca em cada DATA), pega o 1o valor
    monetario como valor da transacao (2o, se houver, e saldo). Best-effort."""
    linhas = [l for l in texto.splitlines() if l.strip()]
    # [rotulo, linha logica]: o rotulo e o 1o texto da linha (o da linha datada; vazio -> o da 1a continuacao com
    # texto) e decide se ela e saldo (D15), nao a descricao acumulada
    logicas = []
    for l in linhas:
        m0 = _RE_DATA_INI.match(l)
        if m0:
            logicas.append([_RE_MONEY.sub("", l[m0.end():]).strip(" -|\t"), l])
        elif logicas and not (_eh_linha_saldo(_norm(l)) and _RE_MONEY.search(l)):
            # saldo avulso (sem data, com valor proprio) nao e continuacao; rotulo sem valor e (quebra de linha)
            if not logicas[-1][0]:
                logicas[-1][0] = _RE_MONEY.sub("", l).strip(" -|\t")
            logicas[-1][1] += " " + l.strip()
    txns = []
    for rotulo, l in logicas:
        m = _RE_DATA_INI.match(l)
        try:
            dt = parse_data(m.group(1))
        except ValueError:
            continue
        moedas = _RE_MONEY.findall(l)
        if not moedas:
            continue
        try:
            valor = parse_valor(_RE_NAO_NUM.sub("", moedas[0]), origem="br")   # R, $ e espacos fora (D14)
        except ValueError:
            continue
        resto = l[m.end():]
        desc = _RE_MONEY.sub("", resto).strip(" -|\t")
        if _eh_linha_saldo(_norm(rotulo)):
            continue
        cpf = extrai_cpf_cnpj(desc)
        txns.append({"data": dt, "valor": valor, "doc": None, "descricao": desc[:120],
                     "contraparte": desc[:120], "cpf_cnpj": cpf, "identificador": None,
                     "fitid": "", "tipo": ""})
    return txns


def _pdf_text_pypdf(path) -> str:
    """Fallback de extracao de texto via pypdf (quando o pdfminer/pdfplumber estoura)."""
    import pypdf
    r = pypdf.PdfReader(path)
    return "\n".join((pg.extract_text() or "") for pg in r.pages)


# ----------------------------------------------------------------------------
# OCR LOCAL (SPEC-02) — Tesseract. Imagem e PDF escaneado -> texto -> mesma heuristica
# do PDF-texto. 100% LOCAL (preserva o fosso). OPT-IN e SKIP-SAFE: sem pytesseract OU
# sem o binario do Tesseract, o arquivo continua PRECISA_OCR (nunca quebra).
# ----------------------------------------------------------------------------
def _tesseract_cmd():
    import shutil
    c = shutil.which("tesseract")
    if c:
        return c
    for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"):
        if os.path.exists(p):
            return p
    return None


def ocr_disponivel() -> bool:
    """True se da p/ rodar OCR local (pytesseract importavel + binario do Tesseract)."""
    try:
        import pytesseract  # noqa: F401
    except Exception:
        return False
    return _tesseract_cmd() is not None


def _ocr_texto_de_pil(im) -> str:
    import pytesseract
    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    g = im.convert("L")   # grayscale ajuda o Tesseract
    try:
        return pytesseract.image_to_string(g, lang="por")
    except Exception:     # por nao instalado -> ingles (digitos/datas/valores leem bem)
        return pytesseract.image_to_string(g, lang="eng")


def _ocr_imagem(path) -> str:
    from PIL import Image
    with Image.open(path) as im:
        return _ocr_texto_de_pil(im)


def _ocr_pdf(path, budget_s: float = 60.0):
    """Renderiza cada pagina (pypdfium2 — wheel puro, sem binario de sistema) e roda OCR.
    Respeita orcamento de tempo (PDF escaneado grande nao pendura). Orcamento estourado antes da ultima
    pagina -> None (D12: nunca devolve so as paginas lidas)."""
    import time as _t
    import pypdfium2 as pdfium
    t0 = _t.monotonic()
    partes = []
    pdf = pdfium.PdfDocument(path)
    try:
        for i in range(len(pdf)):
            if _t.monotonic() - t0 > budget_s:
                return None
            page = pdf[i]
            bitmap = page.render(scale=2)        # ~144 dpi
            partes.append(_ocr_texto_de_pil(bitmap.to_pil()))
    finally:
        pdf.close()
    return "\n".join(partes)


def _timeout_pdf(budget_s) -> dict:
    return {"transacoes": [], "status": "TIMEOUT", "n_ignoradas": 0,
            "aviso": f"PDF muito grande/complexo (>{int(budget_s)}s): divida o periodo ou mande OFX/CSV"}


def _ingest_pdf(path, budget_s: float = 30.0, ocr: bool = False) -> dict:
    """TEXT-FIRST (rapido) + ANTIFRAGIL:
    - extrai texto pagina-a-pagina respeitando um ORCAMENTO DE TEMPO: PDF gigante
      (Mercado Pago/Starkbank, centenas de pag.) -> status TIMEOUT (sem entregar parcial,
      que falsearia a conciliacao); o operador divide o periodo ou manda OFX/CSV;
    - se o pdfplumber/pdfminer estourar (PDF que ele acha corrompido) -> tenta pypdf;
    - PDF sem texto -> PRECISA_OCR (escaneado). extract_tables (caro) so como ultimo recurso."""
    import time as _t
    t0 = _t.monotonic()
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            paginas = pdf.pages
            partes = []
            for pg in paginas:
                if _t.monotonic() - t0 > budget_s:
                    return _timeout_pdf(budget_s)
                partes.append(pg.extract_text() or "")
            texto = "\n".join(partes)
            txns = _pdf_text_to_txns(texto)
            if txns:
                return {"transacoes": txns, "status": "ATENCAO", "n_ignoradas": 0,
                        "aviso": "PDF lido por heuristica de texto — confira os lancamentos"}
            if len(texto.strip()) < 60:
                if ocr and ocr_disponivel():        # SPEC-02: PDF escaneado -> OCR local
                    texto_ocr = _ocr_pdf(path)
                    if texto_ocr is None:           # D12: OCR parcial nunca entra (meio extrato conciliado)
                        return {"transacoes": [], "status": "TIMEOUT", "n_ignoradas": 0,
                                "aviso": "PDF escaneado grande demais para o OCR (>60s): "
                                         "divida o periodo ou mande OFX/CSV"}
                    txns_ocr = _pdf_text_to_txns(texto_ocr)
                    if txns_ocr:
                        return {"transacoes": txns_ocr, "status": "ATENCAO", "n_ignoradas": 0,
                                "aviso": "PDF escaneado lido por OCR local — confira os lancamentos"}
                return {"transacoes": [], "status": "PRECISA_OCR", "n_ignoradas": 0,
                        "aviso": "PDF sem texto extraivel (escaneado?) — precisa OCR"
                                 + ("" if ocr_disponivel() else " (Tesseract nao instalado)")}
            rows_all = []
            for pg in paginas:
                if _t.monotonic() - t0 > budget_s:
                    return _timeout_pdf(budget_s)
                for tb in (pg.extract_tables() or []):
                    rows_all.extend(tb)
        if rows_all:
            res = ingest_tabular_rows(rows_all)
            if res["transacoes"]:
                res["aviso"] = (res["aviso"] + "; ").lstrip("; ") + "PDF via tabela"
                return res
        return {"transacoes": [], "status": "MAPEAR_COLUNAS", "n_ignoradas": 0,
                "aviso": "PDF com texto mas nao reconheci linhas de lancamento"}
    except Exception as e0:                              # noqa: BLE001 — pdfminer estourou; tenta pypdf
        try:
            texto = _pdf_text_pypdf(path)
        except Exception as e1:                          # noqa: BLE001
            return {"transacoes": [], "status": "CORROMPIDO", "n_ignoradas": 0,
                    "aviso": f"PDF ilegivel (pdfplumber: {type(e0).__name__}; pypdf: {type(e1).__name__})"}
        txns = _pdf_text_to_txns(texto)
        if txns:
            return {"transacoes": txns, "status": "ATENCAO", "n_ignoradas": 0,
                    "aviso": "PDF lido por pypdf (fallback) — confira os lancamentos"}
        if len(texto.strip()) < 60:
            return {"transacoes": [], "status": "PRECISA_OCR", "n_ignoradas": 0,
                    "aviso": "PDF sem texto extraivel (escaneado?) — precisa OCR"}
        return {"transacoes": [], "status": "MAPEAR_COLUNAS", "n_ignoradas": 0,
                "aviso": "PDF (pypdf) com texto mas nao reconheci linhas de lancamento"}


# ----------------------------------------------------------------------------
# Dispatcher unico — NUNCA quebra. Qualquer erro -> status CORROMPIDO.
# ----------------------------------------------------------------------------
_TABULAR = {"csv": _rows_from_csv, "xlsx": _rows_from_xlsx, "xls": _rows_from_xls, "txt": _rows_from_csv}


def ingest_extrato(path, ocr: bool = False) -> ExtratoResult:
    """ocr=False (default): imagem/escaneado -> PRECISA_OCR (opt-in, fosso intacto).
    ocr=True: roda OCR LOCAL (Tesseract) p/ imagem e PDF escaneado; skip-safe sem o binario."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    try:
        if ext == "ofx":
            from ingest_ofx import parse_ofx
            e = parse_ofx(path)
            return ExtratoResult(transacoes=e.transacoes, status="OK" if e.transacoes else "VAZIO",
                                 fonte="ofx", banco=e.banco, conta=e.conta, saldo_final=e.saldo_final,
                                 tipo_conta=e.tipo_conta, moeda=e.moeda, n_contas=e.n_contas,
                                 txns_corrompidas=e.txns_corrompidas, eh_cartao=e.eh_cartao)
        if ext == "pdf":
            d = _ingest_pdf(path, ocr=ocr)
            return ExtratoResult(transacoes=d["transacoes"], status=d["status"], fonte="pdf",
                                 aviso=d.get("aviso", ""), n_ignoradas=d.get("n_ignoradas", 0))
        if ext in ("jpg", "jpeg", "png", "tiff", "bmp"):
            if ocr and ocr_disponivel():            # SPEC-02: imagem -> OCR local
                txns = _pdf_text_to_txns(_ocr_imagem(path))
                if txns:
                    return ExtratoResult(transacoes=txns, status="ATENCAO", fonte="imagem",
                                         aviso="imagem lida por OCR local — confira os lancamentos")
                return ExtratoResult(status="MAPEAR_COLUNAS", fonte="imagem",
                                     aviso="OCR rodou mas nao reconheci lancamentos na imagem")
            return ExtratoResult(status="PRECISA_OCR", fonte="imagem",
                                 aviso="imagem de extrato — precisa OCR local (Tesseract)"
                                       + ("" if ocr_disponivel() else "; Tesseract nao instalado"))
        if ext in _TABULAR:
            fonte = "html" if (ext == "xls" and _looks_html(path)) else ext
            rows = _TABULAR[ext](path)
            d = ingest_tabular_rows(rows)
            return ExtratoResult(transacoes=d["transacoes"], status=d["status"], fonte=fonte,
                                 aviso=d.get("aviso", ""), n_ignoradas=d.get("n_ignoradas", 0))
        return ExtratoResult(status="CORROMPIDO", fonte=ext or "?", aviso=f"formato nao suportado: .{ext}")
    except Exception as e:                              # noqa: BLE001 — antifragil: nada derruba o run
        return ExtratoResult(status="CORROMPIDO", fonte=ext or "?",
                             aviso=type(e).__name__)



# ----------------------------------------------------------------------------
# Orquestracao de PASTA (a jornada do analista, SPEC-04 + preferencia de formato
# da SPEC-01): varre a pasta, ingere cada arquivo (timeout embutido no PDF), agrupa
# por conta e escolhe o MELHOR formato (OFX > CSV/XLSX > PDF > OCR) — nao conta a
# mesma conta 2x quando vem em varios formatos. Tudo local; nunca quebra.
# ----------------------------------------------------------------------------
_FORMATO_RANK = {"ofx": 0, "csv": 1, "xls": 1, "xlsx": 1, "html": 1, "txt": 1, "pdf": 2, "imagem": 3}
_STATUS_RANK = {"OK": 0, "ATENCAO": 1, "VAZIO": 2, "MAPEAR_COLUNAS": 3,
                "TIMEOUT": 4, "PRECISA_OCR": 5, "CORROMPIDO": 6}
_EXTS_EXTRATO = ("ofx", "csv", "xlsx", "xls", "pdf", "txt", "jpg", "jpeg", "png")


def _chave_conta(path, res: "ExtratoResult"):
    """Chave de agrupamento de uma conta = a PASTA-PAI. A estrutura real do analista e
    1 pasta por conta (um mes/conta com o extrato em varios formatos); agrupar pela pasta
    mantem OFX+CSV+PDF da MESMA conta juntos -> a preferencia de formato funciona (nao
    misturar com (banco,conta) detectado, que so o OFX traz e separaria do CSV/PDF irmaos).
    [SPEC-01 P2: quando detectarmos banco/conta tambem no tabular/PDF, da p/ desduplicar
    pasta achatada com varias contas.]"""
    return os.path.dirname(path)


def ingest_pasta(pasta, recursivo: bool = True, ocr: bool = False) -> dict:
    """Varre `pasta`, ingere cada extrato e devolve, POR CONTA, a melhor leitura
    (preferencia de formato) + um relatorio de todos os arquivos. Antifragil: qualquer
    arquivo problematico vira status, nunca excecao. So agregados sobem p/ a IA.
    ocr=True -> imagem/escaneado passam pelo OCR local (skip-safe sem o Tesseract)."""
    achados = []
    for root, dirs, files in os.walk(pasta):
        dirs[:] = [d for d in dirs if not d.startswith("._")]
        for f in sorted(files):
            if f.startswith("._"):
                continue
            if os.path.splitext(f)[1].lower().lstrip(".") in _EXTS_EXTRATO:
                achados.append(os.path.join(root, f))
        if not recursivo:
            break

    grupos: dict = {}
    for p in sorted(achados):
        res = ingest_extrato(p, ocr=ocr)
        grupos.setdefault(_chave_conta(p, res), []).append((p, res))

    def _rank(item):
        _p, r = item
        return (_STATUS_RANK.get(r.status, 9), _FORMATO_RANK.get(r.fonte, 9), -len(r.transacoes))

    contas, arquivos = [], []
    resumo = Counter()
    for chave, itens in sorted(grupos.items(), key=lambda kv: str(kv[0])):
        itens_ord = sorted(itens, key=_rank)
        esc_path, esc = itens_ord[0]
        tem_txn = bool(esc.transacoes)
        contas.append({
            "chave": list(chave), "arquivo": os.path.relpath(esc_path, pasta),
            "fonte": esc.fonte, "status": esc.status, "n_txns": len(esc.transacoes),
            "precisa_acao": not tem_txn, "aviso": esc.aviso,
            "n_formatos": len(itens_ord),
        })
        resumo["contas"] += 1
        resumo["contas_ok" if tem_txn else "contas_acao"] += 1
        resumo["txns"] += len(esc.transacoes)
        for i, (p, r) in enumerate(itens_ord):
            papel = ("escolhido" if tem_txn else "acao") if i == 0 else "redundante"
            arquivos.append({"arquivo": os.path.relpath(p, pasta), "fonte": r.fonte,
                             "status": r.status, "n_txns": len(r.transacoes),
                             "papel": papel, "aviso": r.aviso})
            resumo[f"st_{r.status}"] += 1
    resumo["arquivos"] = len(arquivos)
    return {"contas": contas, "arquivos": arquivos, "resumo": dict(resumo)}
