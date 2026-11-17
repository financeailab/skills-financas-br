# -*- coding: utf-8 -*-
"""Parser "tipo-Itau": texto corrido, multi-portador. Formato calibrado no
FIXTURE SINTETICO (v1 nao tem corpus real, ver SPEC-00 §3):

    "Portador: NOME SOBRENOME"
    "DD/MM/AAAA Estabelecimento (NN/NN) MOEDA R$ 1.234,56"   <- parcela e moeda OPCIONAIS
    "Encargo: IOF R$ 53,53"
    "Total desta fatura R$ 1.603,98"

Cada bloco "Portador:" abre uma secao; os lancamentos ate o proximo "Portador:"
(ou fim do documento) pertencem a ele. Encargos e o total sao de nivel-fatura
(nao por portador, igual a fatura real: IOF/anuidade aparecem uma vez so).
"""
from __future__ import annotations

import re

from bancos.generico import normaliza_sinal
from modelo import Encargo, FaturaParsed, LAYOUT_DESCONHECIDO, Lancamento
from normalize import _sem_acento, parse_data, parse_valor

_RE_HEADER = re.compile(r"FATURA CARTAO CORPORATIVO")
_RE_VENCIMENTO = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RE_PORTADOR = re.compile(r"^Portador:\s*(.+)$", re.IGNORECASE)
_RE_ENCARGO = re.compile(r"^Encargo:\s*(.+?)\s+R\$\s*([\d.,]+)\s*$", re.IGNORECASE)
_RE_TOTAL = re.compile(r"^Total desta fatura\s+R\$\s*([\d.,]+)\s*$", re.IGNORECASE)
_RE_LANCAMENTO = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.*)$")
_RE_PARCELA = re.compile(r"\((\d{2}/\d{2})\)")
_RE_MOEDA = re.compile(r"\b(USD|EUR|GBP)\b")
# aceita as formas NEGATIVAS de estorno/credito (achado Codex pre-PR: sem isso o
# lancamento negativo era pulado em silencio e o total dava TOTAL NAO FECHA):
# "-12,34" (prefixo) · "12,34-" (sufixo, convencao estilo-Itau) · "(12,34)" (contabil).
# parse_valor ja entende as 3; a regex so precisava deixar o token chegar la.
_RE_VALOR_FIM = re.compile(r"R\$\s*([+-]?[\d.,]+-?|\([\d.,]+\))\s*$")


def parse(paginas: list) -> FaturaParsed:
    """Extrai um FaturaParsed do layout tipo-Itau. `paginas` = list[{"texto","words"}]."""
    texto = "\n".join((p.get("texto") or "") for p in paginas)

    if not _RE_HEADER.search(_sem_acento(texto).upper()):  # como o detector: "Cartão" com acento
        # detector so despacha aqui apos achar a assinatura; guarda defensiva.
        fatura = FaturaParsed(emissor="itau")
        fatura.veredicto = LAYOUT_DESCONHECIDO
        fatura.aviso = "tipo-Itau: cabecalho 'Fatura Cartao Corporativo' nao encontrado"
        return fatura

    fatura = FaturaParsed(emissor="itau")
    m_venc = _RE_VENCIMENTO.search(texto)
    if m_venc:
        fatura.vencimento = parse_data(m_venc.group(1))

    portador_atual = ""
    lancamentos: list[Lancamento] = []
    encargos: list[Encargo] = []

    for linha in (l.strip() for l in texto.splitlines() if l.strip()):
        m_port = _RE_PORTADOR.match(linha)
        if m_port:
            portador_atual = m_port.group(1).strip()
            if portador_atual not in fatura.portadores:
                fatura.portadores.append(portador_atual)
            continue

        m_total = _RE_TOTAL.match(linha)
        if m_total:
            fatura.total_fatura = parse_valor(m_total.group(1))
            continue

        m_enc = _RE_ENCARGO.match(linha)
        if m_enc:
            encargos.append(Encargo(rotulo=m_enc.group(1).strip(), valor=parse_valor(m_enc.group(2))))
            continue

        m_lanc = _RE_LANCAMENTO.match(linha)
        if not m_lanc:
            continue  # ruido (cabecalho/legenda/linha em branco): nao e lancamento
        resto = normaliza_sinal(m_lanc.group(2))

        m_valor = _RE_VALOR_FIM.search(resto)
        if not m_valor:
            fatura.linhas_nao_lidas += 1  # linha com data mas sem valor reconhecivel: conta, nao inventa
            continue
        try:
            valor = parse_valor(m_valor.group(1))
        except ValueError:
            fatura.linhas_nao_lidas += 1
            continue
        resto_sem_valor = resto[:m_valor.start()].strip()

        parcela = None
        m_parc = _RE_PARCELA.search(resto_sem_valor)
        if m_parc:
            parcela = m_parc.group(1)
            resto_sem_valor = (resto_sem_valor[:m_parc.start()] + resto_sem_valor[m_parc.end():]).strip()

        moeda = "BRL"
        m_moeda = _RE_MOEDA.search(resto_sem_valor)
        if m_moeda:
            moeda = m_moeda.group(1)
            resto_sem_valor = (resto_sem_valor[:m_moeda.start()] + resto_sem_valor[m_moeda.end():]).strip()

        lancamentos.append(Lancamento(
            data=parse_data(m_lanc.group(1)),
            estabelecimento=resto_sem_valor.strip(),
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
