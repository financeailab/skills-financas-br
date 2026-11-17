# -*- coding: utf-8 -*-
"""Gera PDFs-fixture de fatura de cartao corporativo NATIVO (texto extraivel) p/
testar os parsers.

⚠️ v1 nao tem corpus real (nunca vimos uma fatura de verdade): os fixtures usam
nomes de banco DECLARADAMENTE ficticios ("BANCO EXEMPLO ITA"/"BANCO EXEMPLO BRA")
para nao afirmar que reproduzimos o layout real de um emissor especifico. Os
parsers reconhecem um ESTILO estrutural (texto corrido multi-portador vs. tabela
posicional por coluna), nao uma assinatura literal de banco real — ver SPEC-00 §3.

Dados 100% ficticios (fake-BR). Os PDFs sao regeneraveis e NAO vao pro git
(binario + timestamp do reportlab); os testes/CI geram antes de rodar.

Uso: python gen_faturas_pdf.py <outdir>   (gera todos + variantes 'furado')
"""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

D = Decimal
W, H = A4

# ---------------------------------------------------------------------------
# GABARITO: dados conhecidos por emissor (ordem CRONOLOGICA por portador).
# Cada lancamento: (data, portador, estabelecimento, parcela|None, moeda, valor)
# Cada gabarito tem 1 ESTORNO (valor negativo): o total da fatura so fecha se o
# parser capturar o lancamento negativo (achado Codex pre-PR: regex de valor
# ignorava as formas negativas e o estorno sumia em silencio).
# ---------------------------------------------------------------------------
GABARITO = {
    "itau": {
        "vencimento": date(2026, 2, 10),
        "lancamentos": [
            (date(2026, 1, 5), "CARLOS EDUARDO LIMA", "Supermercado Bom Preco", None, "BRL", D("358.40")),
            (date(2026, 1, 8), "CARLOS EDUARDO LIMA", "Loja Tech Informatica", "02/05", "BRL", D("210.00")),
            (date(2026, 1, 12), "MARIA SILVA SOUZA", "Hotel Barcelona Espanha", None, "EUR", D("892.15")),
            (date(2026, 1, 20), "MARIA SILVA SOUZA", "Farmacia Saude Total", None, "BRL", D("64.90")),
            # estorno (renderizado com '-' SUFIXO: "R$ 64,90-", convencao estilo-Itau)
            (date(2026, 1, 22), "MARIA SILVA SOUZA", "Estorno Farmacia Saude Total", None, "BRL", D("-64.90")),
        ],
        "encargos": [("IOF", D("53.53")), ("Anuidade", D("25.00"))],
    },
    "bradesco": {
        "vencimento": date(2026, 2, 15),
        "lancamentos": [
            (date(2026, 1, 3), "ANA PAULA COSTA", "Posto Ipiranga Centro", None, "BRL", D("180.00")),
            (date(2026, 1, 10), "ANA PAULA COSTA", "Livraria Cultura Norte", "03/06", "BRL", D("145.00")),
            (date(2026, 1, 18), "ANA PAULA COSTA", "Hotel Lisboa Central", None, "EUR", D("512.60")),
            (date(2026, 1, 25), "ANA PAULA COSTA", "Farmacia Popular", None, "BRL", D("42.30")),
            # estorno (renderizado com '-' PREFIXO na coluna VALOR: "-30,00")
            (date(2026, 1, 28), "ANA PAULA COSTA", "Estorno Livraria Cultura Norte", None, "BRL", D("-30.00")),
        ],
        "encargos": [("IOF", D("22.40")), ("Anuidade", D("25.00"))],
    },
}

# indice do lancamento removido na variante 'furado' (do meio, p/ quebrar o total)
_FURADO_IDX = 1


def _br(v: Decimal) -> str:
    """Decimal -> '1.234,56' (formato BR, sempre positivo)."""
    n = abs(v)
    inteiro, _, dec = f"{n:.2f}".partition(".")
    rev = inteiro[::-1]
    grupos = [rev[i:i + 3] for i in range(0, len(rev), 3)]
    inteiro_fmt = ".".join(grupos)[::-1]
    return f"{inteiro_fmt},{dec}"


def _total(emissor: str) -> Decimal:
    g = GABARITO[emissor]
    total = sum((v for (*_, v) in g["lancamentos"]), D("0.00"))
    total += sum((v for (_, v) in g["encargos"]), D("0.00"))
    return total


def _lancamentos(emissor: str, furado: bool):
    lst = list(GABARITO[emissor]["lancamentos"])
    if furado:
        del lst[_FURADO_IDX]
    return lst


def esperado(emissor: str, furado: bool = False) -> dict:
    """Answer-key: o que o parser DEVE extrair do PDF gerado. Quando furado=True, a
    lista reflete o PDF (um lancamento a menos), mas total_fatura continua o
    ORIGINAL -> a prova de completude deve reprovar (TOTAL NAO FECHA)."""
    g = GABARITO[emissor]
    lst = _lancamentos(emissor, furado)
    portadores = []
    for (_, portador, *_r) in g["lancamentos"]:
        if portador not in portadores:
            portadores.append(portador)
    return {
        "emissor": emissor,
        "vencimento": g["vencimento"],
        "portadores": portadores,
        "total_fatura": _total(emissor),  # total IMPRESSO: sempre o original, mesmo furado
        "lancamentos": [
            {"data": d, "portador": p, "estabelecimento": e, "parcela": parc, "moeda": m, "valor": v}
            for (d, p, e, parc, m, v) in lst
        ],
        "encargos": [{"rotulo": r, "valor": v} for (r, v) in g["encargos"]],
    }


# ---------------------------------------------------------------------------
# Render: "itau" — texto corrido, multi-portador (Portador: NOME; Encargo: rotulo)
# ---------------------------------------------------------------------------
def _render_itau(path: str, furado: bool):
    g = GABARITO["itau"]
    c = canvas.Canvas(path, pagesize=A4)
    y = H - 50
    c.setFont("Helvetica", 9)

    def line(txt, dy=14):
        nonlocal y
        c.drawString(40, y, txt)
        y -= dy

    line("BANCO EXEMPLO ITA S.A.")
    line("FATURA CARTAO CORPORATIVO")
    line(f"Vencimento: {g['vencimento'].strftime('%d/%m/%Y')}")
    line("")

    lancamentos = _lancamentos("itau", furado)
    portador_corrente = None
    for (d, portador, estab, parcela, moeda, valor) in lancamentos:
        if portador != portador_corrente:
            line(f"Portador: {portador}")
            portador_corrente = portador
        txt = f"{d.strftime('%d/%m/%Y')} {estab}"
        if parcela:
            txt += f" ({parcela})"
        if moeda != "BRL":
            txt += f" {moeda}"
        # estorno: '-' SUFIXO no valor ("R$ 64,90-"), convencao estilo-Itau
        txt += f" R$ {_br(valor)}" + ("-" if valor < 0 else "")
        line(txt)

    line("")
    line("Resumo de encargos")
    for rotulo, valor in g["encargos"]:
        line(f"Encargo: {rotulo} R$ {_br(valor)}")
    line(f"Total desta fatura R$ {_br(_total('itau'))}")

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Render: "bradesco" — tabela posicional (colunas ancoradas por rotulo, words)
# ---------------------------------------------------------------------------
X_DATA, X_ESTAB, X_PARCELA, X_MOEDA = 40, 95, 330, 400
XR_VALOR = 555


def _render_bradesco(path: str, furado: bool):
    g = GABARITO["bradesco"]
    c = canvas.Canvas(path, pagesize=A4)
    y = H - 50
    c.setFont("Helvetica", 9)

    def line_full(txt, dy=14):
        nonlocal y
        c.drawString(40, y, txt)
        y -= dy

    line_full("BANCO EXEMPLO BRA S.A.")
    line_full("DEMONSTRATIVO DE CARTAO CORPORATIVO")
    line_full(f"Vencimento: {g['vencimento'].strftime('%d/%m/%Y')}")
    line_full("Portador: ANA PAULA COSTA")

    # cabecalho de colunas (ancora p/ o parser posicional achar os x das colunas)
    c.drawString(X_DATA, y, "DATA")
    c.drawString(X_ESTAB, y, "ESTABELECIMENTO")
    c.drawString(X_PARCELA, y, "PARCELA")
    c.drawString(X_MOEDA, y, "MOEDA")
    c.drawRightString(XR_VALOR, y, "VALOR")
    y -= 14

    for (d, _portador, estab, parcela, moeda, valor) in _lancamentos("bradesco", furado):
        c.drawString(X_DATA, y, d.strftime("%d/%m/%Y"))
        c.drawString(X_ESTAB, y, estab)
        if parcela:
            c.drawString(X_PARCELA, y, f"({parcela})")
        if moeda != "BRL":
            c.drawString(X_MOEDA, y, moeda)
        # estorno: '-' PREFIXO na coluna VALOR ("-30,00")
        c.drawRightString(XR_VALOR, y, ("-" if valor < 0 else "") + _br(valor))
        y -= 14

    y -= 14
    line_full("Resumo de encargos")
    for rotulo, valor in g["encargos"]:
        line_full(f"Encargo: {rotulo} R$ {_br(valor)}")
    line_full(f"Total desta fatura R$ {_br(_total('bradesco'))}")

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Render: "generico" (layout desconhecido de propositado — sem rotulos-ancora)
# ---------------------------------------------------------------------------
def _render_generico_reconhecivel(path: str):
    """Fatura de emissor 'de fora' (nem tipo-Itau nem tipo-Bradesco): sem 'Portador:'/
    'Encargo:'/'Total desta fatura', so linhas soltas 'DD/MM/AAAA ESTABELECIMENTO
    VALOR' — o parser generico deve ler os lancamentos best-effort, mas sem total
    impresso reconhecido a prova de completude nao fecha (BAIXA CONFIANCA)."""
    c = canvas.Canvas(path, pagesize=A4)
    y = H - 50
    c.setFont("Helvetica", 9)

    def line(txt, dy=14):
        nonlocal y
        c.drawString(40, y, txt)
        y -= dy

    line("OUTRO BANCO LTDA - RESUMO DE COMPRAS DO CARTAO")
    line("06/01/2026 Restaurante Sabor Caseiro R$ 89,90")
    line("14/01/2026 Papelaria Central R$ 37,50")
    line("22/01/2026 Posto Shell Rodovia R$ 210,00")
    # estorno na forma CONTABIL (parenteses = negativo)
    line("28/01/2026 Estorno Papelaria Central R$ (37,50)")
    c.showPage()
    c.save()


def _render_generico_ilegivel(path: str):
    """PDF nativo sem NENHUMA linha reconhecivel (nem data no inicio de linha):
    dispara LAYOUT DESCONHECIDO em qualquer parser (nada a extrair)."""
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica", 10)
    c.drawString(40, H - 50, "Documento sem estrutura de fatura reconhecivel.")
    c.drawString(40, H - 70, "Nenhuma linha de lancamento aqui.")
    c.showPage()
    c.save()


_RENDERERS = {"itau": _render_itau, "bradesco": _render_bradesco}


def gerar(emissor: str, path: str, furado: bool = False) -> str:
    """Gera o PDF-fixture de `emissor` em `path`. Retorna o path."""
    _RENDERERS[emissor](path, furado)
    return path


def gerar_generico_reconhecivel(path: str) -> str:
    _render_generico_reconhecivel(path)
    return path


def gerar_generico_ilegivel(path: str) -> str:
    _render_generico_ilegivel(path)
    return path


def gerar_todos(outdir: str) -> dict:
    """Gera todos os fixtures (normal + furado + os 2 genericos) em `outdir`."""
    os.makedirs(outdir, exist_ok=True)
    saidas = {}
    for emissor in _RENDERERS:
        saidas[emissor] = gerar(emissor, os.path.join(outdir, f"{emissor}.pdf"))
        saidas[f"{emissor}_furado"] = gerar(
            emissor, os.path.join(outdir, f"{emissor}_furado.pdf"), furado=True
        )
    saidas["generico"] = gerar_generico_reconhecivel(os.path.join(outdir, "generico.pdf"))
    saidas["ilegivel"] = gerar_generico_ilegivel(os.path.join(outdir, "ilegivel.pdf"))
    return saidas


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures"
    for nome, p in gerar_todos(out).items():
        print(f"  {nome}: {p}")
