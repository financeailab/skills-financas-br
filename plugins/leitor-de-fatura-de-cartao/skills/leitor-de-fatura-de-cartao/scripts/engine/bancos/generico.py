# -*- coding: utf-8 -*-
"""Parser generico (fallback best-effort quando o layout nao bate com nenhum
emissor conhecido). Heuristica minima e honesta: uma linha que comeca com
`DD/MM/AAAA` e termina com um valor monetario e um lancamento; o resto do meio
e o estabelecimento. Nunca tenta achar portador/parcela/moeda (arriscado demais
sem ancora conhecida) nem um "total impresso" confiavel — por isso a prova de
completude (prova_total.py) nunca aprova um generico como `OK`: sem total pra
provar, o melhor veredicto possivel e `BAIXA CONFIANCA`."""
from __future__ import annotations

import re

from modelo import FaturaParsed, LAYOUT_DESCONHECIDO, Lancamento
from normalize import parse_data, parse_valor

_RE_DATA_INI = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.*)$")
# aceita as formas NEGATIVAS de estorno/credito (achado Codex pre-PR): "-12,34"
# (prefixo) · "12,34-" (sufixo) · "(12,34)" (contabil). parse_valor entende as 3.
# o token nunca comeca no meio de um numero (Gate 2 da abertura: "R$ 1234,56" virava 234,56 e "-1234,56" perdia o
# sinal) e pode vir colado no texto ("Centro89,90", 1B passe 3); valor com ou sem separador de milhar, com sinal na
# frente: "+", "-", o menos tipografico (U+2212) ou a meia-risca (U+2013), estes dois trocados por "-" antes do parse.
_NUM = r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}"
_SINAIS = str.maketrans({"\u2212": "-", "\u2013": "-"})
# sinal antes da moeda: "-R$ 12,34" (menos colado na moeda) e "R$ - 12,34" viram "R$ -12,34" (Gate 2 do clone,
# passe 2). " - R$ 12,34", com espaco dos dois lados, e separador comum e fica como esta.
_RE_MENOS_MOEDA = re.compile(r"(?<!\S)-(R?\$)\s*(?=\d)")  # so antes de digito: "-R$ -12,34" e "-R$ (10,00)" ficam como estao
_RE_MOEDA_MENOS = re.compile(r"(R?\$)\s*-\s*(?=\d)")


def normaliza_sinal(texto: str) -> str:
    """Troca o menos tipografico e a meia-risca por "-" e cola o sinal solto ao numero, depois da moeda."""
    t = texto.translate(_SINAIS)
    t = _RE_MENOS_MOEDA.sub(lambda m: m.group(1) + " -", t)
    return _RE_MOEDA_MENOS.sub(lambda m: m.group(1) + " -", t)


# o token comeca depois da moeda, num sinal ou parentese (como antes: "Loja24-12,34" e -12,34, Gate 2 do monorepo) ou
# num digito que nao continua outro numero
_RE_VALOR_FIM = re.compile(r"(?:R?\$\s*|(?=[+\-(])|(?<!\d)(?<!\d[.,]))([+-]?" + _NUM + r"-?|\(" + _NUM + r"\))\s*$")


def parse(paginas: list) -> FaturaParsed:
    """Extrai um FaturaParsed best-effort de um layout desconhecido.
    `paginas` = list[{"texto","words"}] (so `texto` e usado aqui)."""
    fatura = FaturaParsed(emissor="generico")

    texto = "\n".join((p.get("texto") or "") for p in paginas)
    lancamentos: list[Lancamento] = []
    for linha in (l.strip() for l in texto.splitlines() if l.strip()):
        m = _RE_DATA_INI.match(linha)
        if not m:
            continue
        resto = normaliza_sinal(m.group(2))
        m_valor = _RE_VALOR_FIM.search(resto)
        if not m_valor:
            fatura.linhas_nao_lidas += 1  # linha com data mas sem valor reconhecivel: conta, nao inventa
            continue
        try:
            data_lanc = parse_data(m.group(1))
            valor = parse_valor(m_valor.group(1))
        except ValueError:
            fatura.linhas_nao_lidas += 1
            continue
        estabelecimento = resto[:m_valor.start()].strip()
        lancamentos.append(Lancamento(data=data_lanc, estabelecimento=estabelecimento, valor=valor))

    lancamentos.sort(key=lambda l: l.data)
    fatura.lancamentos = lancamentos

    if not lancamentos:
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = "generico: nao reconheci nenhuma linha de lancamento no PDF"

    return fatura
