# -*- coding: utf-8 -*-
"""Ingestao de contas a pagar/a receber do ERP (CSV/XLSX) -> titulos canonicos.

Dois perfis de coluna (SPEC-00 §4):
  - `generico`: cabecalhos comuns (fornecedor/cliente, documento, vencimento, valor, status).
  - `omie`: mapeamento fixo do export padrao do Omie (Fornecedor/Cliente, Numero Doc.,
    Vencimento, Valor Doc., Status).

Status decide se o titulo entra na projecao: so titulo EM ABERTO entra (invariante
#5, SPEC-00 §8). Decisao de build D4 (ver README): a lista de status "fora"
(baixado) e FECHADA e a lista de "aberto" e o default. Um status desconhecido
(digitado diferente do esperado) fica em aberto, porque e mais seguro mostrar um
titulo a mais pro operador conferir do que sumir um pagamento/recebimento real.

Saida canonica de cada titulo:
  { 'tipo': 'pagar'|'receber', 'contraparte': str, 'documento': str,
    'vencimento': date, 'valor': Decimal (sempre positivo), 'status_raw': str,
    'em_aberto': bool }
"""
from __future__ import annotations

import csv
import io
import os

from normalize import parse_valor, parse_data, _sem_acento
from recusa import Recusa

PERFIS_ALIASES = {
    "generico": {
        "contraparte": ("fornecedor", "cliente", "razao social", "nome"),
        "documento": ("documento", "numero", "nf", "no", "n."),
        "vencimento": ("vencimento", "data vencimento", "dt venc", "dt. venc."),
        "valor": ("valor", "valor titulo", "valor a pagar", "valor a receber"),
        "status": ("status", "situacao"),
    },
    "omie": {
        "contraparte": ("fornecedor", "cliente"),
        "documento": ("numero doc.", "numero doc", "no doc."),
        "vencimento": ("vencimento",),
        "valor": ("valor doc.", "valor doc"),
        "status": ("status",),
    },
}

# status "fora" = titulo ja baixado, NUNCA entra na projecao. Lista fechada por
# desenho: tudo que nao esta aqui fica em aberto (default seguro, Decisao D4).
_FORA = {"pago", "baixado", "liquidado", "recebido", "cancelado"}
STATUS_FORA = {"generico": _FORA, "omie": _FORA}  # o omie sem "cancelado" projetava titulo cancelado (Gate 2, passe 3)

COLUNAS_OBRIGATORIAS = ("vencimento", "valor")


def _norm_header(s) -> str:
    return _sem_acento(str(s or "")).strip().lower()


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _ler_csv(caminho: str) -> list[dict]:
    raw = open(caminho, "rb").read()
    txt = _decode(raw)
    if not txt.strip():
        return []
    primeira = txt.splitlines()[0]
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    linhas = list(csv.DictReader(io.StringIO(txt), delimiter=sep))
    return [{(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            for r in linhas]


def _ler_xlsx(caminho: str) -> list[dict]:
    import openpyxl  # dependencia opcional; so carrega se precisar de xlsx
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    try:
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
    except StopIteration:
        return []
    out = []
    for r in rows:
        if r is None or all(c is None for c in r):
            continue
        # sem <dimension> o openpyxl corta as celulas vazias do fim da linha: completa ate o cabecalho
        r = tuple(r) + (None,) * (len(header) - len(r))
        out.append({header[i]: (str(r[i]).strip() if isinstance(r[i], str) else r[i])
                    for i in range(len(header))})
    return out


def _ler_tabular(caminho: str) -> list[dict]:
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _ler_xlsx(caminho)
    return _ler_csv(caminho)


def _detectar_colunas(headers: list[str], perfil: str) -> dict:
    aliases = PERFIS_ALIASES[perfil]
    low = {_norm_header(h): h for h in headers}
    achadas = {}
    for chave, opcoes in aliases.items():
        for opcao in opcoes:
            if opcao in low:
                achadas[chave] = low[opcao]
                break
    return achadas


def _em_aberto(status_raw: str, perfil: str) -> bool:
    return _norm_header(status_raw) not in STATUS_FORA[perfil]


def ler_titulos(caminho: str, perfil: str, tipo: str) -> list[dict]:
    """`tipo` = 'pagar' ou 'receber' (so rotula a origem; nao muda o parsing)."""
    if perfil not in PERFIS_ALIASES:
        raise Recusa(
            f"perfil de titulos desconhecido: {perfil!r}. Perfis disponiveis: "
            f"{', '.join(PERFIS_ALIASES)}. Use --perfil generico se nao for Omie.")

    linhas = _ler_tabular(caminho)
    if not linhas:
        return []

    headers = list(linhas[0].keys())
    cols = _detectar_colunas(headers, perfil)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in cols]
    if faltando:
        raise Recusa(
            f"coluna(s) obrigatoria(s) nao encontrada(s) no arquivo de titulos a {tipo} "
            f"(perfil '{perfil}'): {', '.join(faltando)}. O arquivo tem {len(headers)} coluna(s). "
            f"Confira o export do ERP ou use --perfil generico se as colunas nao seguirem "
            f"o padrao {perfil}.")

    titulos = []
    for i, linha in enumerate(linhas, start=2):  # linha 2 = 1a linha de dados
        # a celula nunca vai para a mensagem: so a linha e a coluna logica
        try:
            vencimento = parse_data(linha.get(cols["vencimento"]))
        except (ValueError, ArithmeticError, TypeError):
            raise Recusa(f"linha {i} do arquivo de titulos a {tipo}: vencimento ilegivel") from None
        bruto = linha.get(cols["valor"])
        # celula numerica do XLSX ja e o numero: como texto BR, 2.345 viraria milhar (2345); ponto = decimal
        origem = "ofx" if isinstance(bruto, (int, float)) and not isinstance(bruto, bool) else "br"
        try:
            valor = abs(parse_valor(bruto, origem=origem))
        except (ValueError, ArithmeticError, TypeError):
            raise Recusa(f"linha {i} do arquivo de titulos a {tipo}: valor ilegivel") from None
        status_raw = str(linha.get(cols.get("status", ""), "") or "").strip()
        titulos.append({
            "tipo": tipo,
            "contraparte": str(linha.get(cols.get("contraparte", ""), "") or "").strip(),
            "documento": str(linha.get(cols.get("documento", ""), "") or "").strip(),
            "vencimento": vencimento,
            "valor": valor,
            "status_raw": status_raw,
            "em_aberto": _em_aberto(status_raw, perfil),
        })
    return titulos
