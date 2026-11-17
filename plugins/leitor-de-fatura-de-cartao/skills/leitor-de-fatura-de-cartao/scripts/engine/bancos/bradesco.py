# -*- coding: utf-8 -*-
"""Parser "tipo-Bradesco": tabela POSICIONAL por coluna (as colunas colapsam no
texto corrido; usa `words` do pdfplumber e ancora pelos ROTULOS do cabecalho
"DATA ESTABELECIMENTO PARCELA MOEDA VALOR", igual ao padrao do irmao
`conversor-extrato/scripts/engine/bancos/bradesco.py`).

Cabecalho/Portador/Encargo/Total ficam FORA da tabela e sao lidos como texto
corrido comum (mesmas regex do `bancos/itau.py`, reaproveitadas aqui reconstruindo
a linha a partir das `words` agrupadas por proximidade vertical).
"""
from __future__ import annotations

import re

from modelo import Encargo, FaturaParsed, LAYOUT_DESCONHECIDO, Lancamento
from normalize import _sem_acento, parse_data, parse_valor

_TOLERANCIA_LINHA = 3.0   # palavras com |top - top| <= isso pertencem a mesma linha
_TOLERANCIA_X = 8.0       # tolerancia (pontos PDF) p/ casar um token a coluna mais proxima

_RE_HEADER = re.compile(r"DEMONSTRATIVO DE CARTAO CORPORATIVO")
_RE_VENCIMENTO = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RE_PORTADOR = re.compile(r"^Portador:\s*(.+)$", re.IGNORECASE)
_RE_ENCARGO = re.compile(r"^Encargo:\s*(.+?)\s+R\$\s*([\d.,]+)\s*$", re.IGNORECASE)
_RE_TOTAL = re.compile(r"^Total desta fatura\s+R\$\s*([\d.,]+)\s*$", re.IGNORECASE)

_RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_PARCELA = re.compile(r"^\(\d{2}/\d{2}\)$")
_RE_MOEDA = re.compile(r"^(USD|EUR|GBP)$")
# aceita as formas NEGATIVAS de estorno/credito (achado Codex pre-PR): "-12,34"
# (prefixo) · "12,34-" (sufixo) · "(12,34)" (contabil). parse_valor entende as 3.
_RE_MONEY = re.compile(r"^(?:-?\d{1,3}(?:\.\d{3})*,\d{2}-?|\(\d{1,3}(?:\.\d{3})*,\d{2}\))$")
_COLUNAS_CABECALHO = {"DATA", "ESTABELECIMENTO", "PARCELA", "MOEDA", "VALOR"}


def _agrupar_linhas(words: list) -> list:
    """Agrupa palavras (de UMA pagina) em linhas logicas por proximidade de `top`.
    Devolve list[list[word]], cada sublista ja ordenada por x0 (esquerda->direita)."""
    ordenadas = sorted(words, key=lambda w: (w["top"], w["x0"]))
    linhas = []
    for w in ordenadas:
        if linhas and abs(w["top"] - linhas[-1][0]["top"]) <= _TOLERANCIA_LINHA:
            linhas[-1].append(w)
        else:
            linhas.append([w])
    for linha in linhas:
        linha.sort(key=lambda w: w["x0"])
    return linhas


def _achar_colunas(paginas: list):
    """Acha a linha de rotulos (DATA ESTABELECIMENTO PARCELA MOEDA VALOR) e devolve
    (x0_parcela, x0_moeda, x1_valor) ou None se nao achar."""
    for pagina in paginas:
        for linha in _agrupar_linhas(pagina.get("words") or []):
            textos = {_sem_acento(w["text"]).upper(): w for w in linha}
            if _COLUNAS_CABECALHO <= set(textos):
                return textos["PARCELA"]["x0"], textos["MOEDA"]["x0"], textos["VALOR"]["x1"]
    return None


def parse(paginas: list) -> FaturaParsed:
    """Extrai um FaturaParsed do layout tipo-Bradesco. `paginas` = list[{"texto","words"}]."""
    texto = "\n".join((p.get("texto") or "") for p in paginas)

    if not _RE_HEADER.search(_sem_acento(texto).upper()):  # como o detector: "Cartão" com acento
        fatura = FaturaParsed(emissor="bradesco")
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = "tipo-Bradesco: cabecalho 'Demonstrativo de Cartao Corporativo' nao encontrado"
        return fatura

    fatura = FaturaParsed(emissor="bradesco")
    m_venc = _RE_VENCIMENTO.search(texto)
    if m_venc:
        fatura.vencimento = parse_data(m_venc.group(1))

    colunas = _achar_colunas(paginas)
    if colunas is None:
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = "tipo-Bradesco: nao encontrei os rotulos de coluna (DATA/ESTABELECIMENTO/PARCELA/MOEDA/VALOR)"
        return fatura
    x0_parcela, x0_moeda, x1_valor = colunas

    portador_atual = ""
    lancamentos: list[Lancamento] = []
    encargos: list[Encargo] = []

    for pagina in paginas:
        for linha in _agrupar_linhas(pagina.get("words") or []):
            if not linha:
                continue
            textos_norm = {_sem_acento(w["text"]).upper() for w in linha}
            if _COLUNAS_CABECALHO <= textos_norm:
                continue  # cabecalho de colunas: nao e dado

            linha_texto = " ".join(w["text"] for w in linha).strip()

            m_port = _RE_PORTADOR.match(linha_texto)
            if m_port:
                portador_atual = m_port.group(1).strip()
                if portador_atual not in fatura.portadores:
                    fatura.portadores.append(portador_atual)
                continue

            m_total = _RE_TOTAL.match(linha_texto)
            if m_total:
                fatura.total_fatura = parse_valor(m_total.group(1))
                continue

            m_enc = _RE_ENCARGO.match(linha_texto)
            if m_enc:
                encargos.append(Encargo(rotulo=m_enc.group(1).strip(), valor=parse_valor(m_enc.group(2))))
                continue

            if not (linha and _RE_DATA.match(linha[0]["text"])):
                continue  # nao e linha de lancamento (ruido/cabecalho de pagina/etc)

            data_lanc = parse_data(linha[0]["text"])
            parcela = None
            moeda = "BRL"
            valor = None
            palavras_estab = []
            for w in linha[1:]:
                txt = w["text"]
                if _RE_PARCELA.match(txt) and abs(w["x0"] - x0_parcela) <= _TOLERANCIA_X:
                    parcela = txt.strip("()")
                    continue
                if _RE_MOEDA.match(txt) and abs(w["x0"] - x0_moeda) <= _TOLERANCIA_X:
                    moeda = txt
                    continue
                if _RE_MONEY.match(txt) and abs(w["x1"] - x1_valor) <= _TOLERANCIA_X:
                    valor = parse_valor(txt, origem="br")
                    continue
                palavras_estab.append(txt)

            if valor is None:
                fatura.linhas_nao_lidas += 1  # linha com data sem valor casavel na coluna: conta, nao inventa
                continue

            lancamentos.append(Lancamento(
                data=data_lanc,
                estabelecimento=" ".join(palavras_estab).strip(),
                valor=valor,
                portador=portador_atual,
                parcela=parcela,
                moeda=moeda,
                internacional=(moeda != "BRL"),
            ))

    lancamentos.sort(key=lambda l: (l.data, l.portador))
    fatura.lancamentos = lancamentos
    fatura.encargos = encargos
    return fatura
