# -*- coding: utf-8 -*-
"""Parser OFX -> lancamentos bancarios canonicos, multi-arquivo = multi-conta.

Cobre OFX 1.x (SGML, sem tag de fechamento em campo-folha: `<TRNAMT>-150.00` sem
`</TRNAMT>`) e OFX 2.x (XML, tags fechadas). Estrategia: regex tolerante por
bloco <STMTTRN>...</STMTTRN>, igual ao padrao de `conciliacao-bancaria/motor`
(SPEC-00 §9; mesma familia de parser, adaptado ao contrato deste motor).

Saida canonica de cada lancamento:
  { 'data': date, 'valor': Decimal(+credito/-debito), 'descricao': str,
    'fitid': str, 'conta_id': str }

Consolidacao multi-conta: cada arquivo .ofx normalmente traz 1 conta; N arquivos
= N contas (ou a mesma conta relida, dedup por FITID). `conta_id` e QUALIFICADO
POR BANCO E AGENCIA: "BANKID/BRANCHID/ACCTID" (achados Codex: bancos ou agencias
diferentes podem usar o mesmo ACCTID; a chave nua fundia as contas, um LEDGERBAL
suprimia o outro e FITID coincidente descartava lancamento valido no dedup). A posicao
fica mesmo com campo vazio ("341//X"); sem BANKID e sem BRANCHID, o ACCTID puro; sem
ACCTID (raro), nome do arquivo sem extensao.
Limite: a mesma conta exportada uma vez com BRANCHID e outra sem vira duas contas.

O motor nao faz chamada de rede.
"""
from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from normalize import parse_valor, parse_data
from recusa import Recusa

EXTENSAO_OFX = ".ofx"
_ENTIDADE = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|amp|lt|gt|quot|apos);")


@dataclass
class _ExtratoOFX:
    """Resultado de parsear UM arquivo/bloco OFX (pode conter varias transacoes,
    mas so uma conta; o motor nao precisa lidar com envelope multi-conta por
    arquivo, ao contrario do hero de conciliacao)."""
    banco: str = ""
    agencia: str = ""
    conta: str = ""
    tipo_conta: str = ""
    moeda: str = "BRL"
    saldo_final: Decimal | None = None
    data_saldo: date | None = None
    saldo_ilegivel: bool = False  # LEDGERBAL presente, BALAMT ilegivel
    ilegiveis: int = 0  # STMTTRN sem data/valor ou com data/valor ilegivel: ignorado, mas contado
    transacoes: list = field(default_factory=list)


@dataclass
class ContaOFX:
    """Metadados consolidados de uma conta (podem vir de varios arquivos; fica
    o LEDGERBAL de DTASOF mais recente, SPEC-00 §5). `conta_id` = rotulo
    qualificado "BANKID/BRANCHID/ACCTID" (o mesmo que sai em XLSX/CSV/JSON)."""
    conta_id: str
    banco: str = ""
    agencia: str = ""
    tipo_conta: str = ""
    moeda: str = "BRL"
    saldo_final: Decimal | None = None
    data_saldo: date | None = None


@dataclass
class IngestOFXResult:
    lancamentos: list = field(default_factory=list)      # dicts canonicos + conta_id
    contas: dict = field(default_factory=dict)             # conta_id -> ContaOFX
    arquivos_lidos: list = field(default_factory=list)
    arquivos_ignorados: list = field(default_factory=list)  # nao-.ofx, dentro de uma pasta ou passado direto
    ilegiveis: dict = field(default_factory=dict)          # conta_id -> lancamentos ignorados (alerta)


def _decode(raw: bytes) -> str:
    """OFX BR vem em Windows-1252/Latin-1 (CHARSET:1252) ou UTF-8."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _tag(bloco: str, nome: str) -> str | None:
    """Extrai o valor de uma tag-folha SGML ou XML: `<NOME>valor` ate o proximo
    '<' ou fim de linha. Funciona nos dois dialetos."""
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.IGNORECASE)
    if not m:
        return None
    # OFX 2.x (XML) traz &amp; e &#193;; so entidade fechada com ";" decodifica, senao "JOSE&REGINA" viraria "JOSE®INA"
    v = _ENTIDADE.sub(lambda e: html.unescape(e.group(0)), m.group(1)).strip()
    return v or None


def parse_ofx_text(txt: str) -> _ExtratoOFX:
    """Parseia OFX ja decodificado (str)."""
    ext = _ExtratoOFX()
    if len(re.findall(r"<(?:CC)?STMTRS>", txt, re.IGNORECASE)) > 1:
        # o parser e de uma conta por arquivo: com duas (ou conta + cartao), os lancamentos da 2a iriam para a 1a
        raise Recusa("um dos extratos traz mais de uma conta no mesmo arquivo; exporte uma conta por arquivo")

    acct = re.search(r"<BANKACCTFROM>(.*?)</BANKACCTFROM>", txt, re.IGNORECASE | re.DOTALL)
    bloco_acct = acct.group(1) if acct else txt
    ext.banco = _tag(bloco_acct, "BANKID") or ""
    ext.agencia = _tag(bloco_acct, "BRANCHID") or ""
    ext.conta = _tag(bloco_acct, "ACCTID") or ""
    ext.tipo_conta = _tag(bloco_acct, "ACCTTYPE") or ""
    ext.moeda = _tag(txt, "CURDEF") or "BRL"

    ledger = re.search(r"<LEDGERBAL>(.*?)</LEDGERBAL>", txt, re.IGNORECASE | re.DOTALL)
    if ledger:
        bal = _tag(ledger.group(1), "BALAMT")
        if bal is None:
            ext.saldo_ilegivel = True  # LEDGERBAL sem BALAMT (ou vazio): saldo ilegivel, nao ausente
        else:
            try:
                ext.saldo_final = parse_valor(bal, origem="ofx")
            except (ValueError, ArithmeticError):
                ext.saldo_final = None  # saldo ilegivel nao derruba a rodada: conta sem saldo -> SALDO_ESTIMADO
                ext.saldo_ilegivel = True
        dtasof = _tag(ledger.group(1), "DTASOF")
        if dtasof:
            try:
                ext.data_saldo = parse_data(dtasof)
            except (ValueError, ArithmeticError):
                ext.data_saldo = None

    for m in re.finditer(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>|$)",
                         txt, re.IGNORECASE | re.DOTALL):
        b = m.group(1)
        dt = _tag(b, "DTPOSTED")
        amt = _tag(b, "TRNAMT")
        if dt is None or amt is None:
            ext.ilegiveis += 1  # transacao corrompida (sem data ou valor): ignora, mas avisa
            continue
        descricao = (_tag(b, "MEMO") or _tag(b, "NAME") or "").strip()
        fitid = _tag(b, "FITID") or ""
        if not fitid and descricao.lower().startswith("saldo"):
            continue  # quirk BB: "Saldo Anterior/do dia" injetado como STMTTRN
        try:
            data = parse_data(dt)
            valor = parse_valor(amt, origem="ofx")
        except (ValueError, ArithmeticError):
            ext.ilegiveis += 1  # data/valor invalido: ignora, mas avisa (alerta LANCAMENTO_ILEGIVEL)
            continue
        ext.transacoes.append({
            "data": data,
            "valor": valor,
            "descricao": descricao,
            "fitid": fitid,
        })

    return ext


def parse_ofx(caminho: str) -> _ExtratoOFX:
    raw = open(caminho, "rb").read()
    return parse_ofx_text(_decode(raw))


def _expandir_caminhos(caminhos: list[str]) -> tuple[list[str], list[str]]:
    """Cada item de `caminhos` pode ser um arquivo .ofx ou uma pasta (varrida,
    nao-recursiva, so .ofx). Devolve (arquivos_ofx, arquivos_ignorados)."""
    ofx_paths: list[str] = []
    ignorados: list[str] = []
    for c in caminhos:
        if os.path.isdir(c):
            for nome in sorted(os.listdir(c)):
                p = os.path.join(c, nome)
                if os.path.isfile(p) and nome.lower().endswith(EXTENSAO_OFX):
                    ofx_paths.append(p)
                elif os.path.isfile(p):
                    ignorados.append(p)
        elif os.path.isfile(c):
            if c.lower().endswith(EXTENSAO_OFX):
                ofx_paths.append(c)
            else:
                ignorados.append(c)
        else:
            raise Recusa(f"extrato nao encontrado: {c}")  # c = caminho digitado na linha de comando
    # o mesmo arquivo pela pasta e pelo caminho seria lido duas vezes (lancamento sem FITID contaria em dobro)
    vistos, unicos = set(), []
    for p in ofx_paths:
        chave = os.path.normcase(os.path.realpath(p))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(p)
    return unicos, ignorados


def ingest_extratos(caminhos: list[str]) -> IngestOFXResult:
    """Ingere uma lista de arquivos/pastas .ofx -> lancamentos consolidados
    multi-conta, deduplicados por (conta_id, FITID) (invariante #4, SPEC-00 §8).

    Sem FITID (raro), o lancamento nunca e considerado duplicata do mesmo par
    (conta, data, valor, descricao). Decisao conservadora: melhor um lancamento
    a mais do que sumir um real por falta de identificador."""
    res = IngestOFXResult()
    ofx_paths, ignorados = _expandir_caminhos(caminhos)
    res.arquivos_ignorados.extend(ignorados)

    vistos: set = set()
    ilegivel_sem_data: set = set()
    for path in ofx_paths:
        ext = parse_ofx(path)
        # chave/rotulo QUALIFICADO por banco e agencia (achados Codex): bancos diferentes, ou agencias do
        # mesmo banco, podem repetir ACCTID; sem BANKID e BRANCHID na chave, as contas se fundiriam.
        # A posicao dos campos fica mesmo vazia: "0341//X" (so banco) e "/0341/X" (so agencia) nao colidem.
        if ext.conta:
            conta_id = f"{ext.banco}/{ext.agencia}/{ext.conta}" if (ext.banco or ext.agencia) else ext.conta
        else:
            conta_id = os.path.splitext(os.path.basename(path))[0]

        if ext.moeda.upper() != "BRL":  # o texto da moeda vem do arquivo: nao vai para a mensagem
            raise Recusa("um dos extratos nao esta em reais (CURDEF diferente de BRL); o motor so soma BRL")
        conta = res.contas.get(conta_id) or ContaOFX(conta_id=conta_id)
        conta.banco = conta.banco or ext.banco
        conta.agencia = conta.agencia or ext.agencia
        conta.tipo_conta = conta.tipo_conta or ext.tipo_conta
        conta.moeda = ext.moeda or conta.moeda
        if ext.saldo_final is not None and (
            conta.data_saldo is None or (ext.data_saldo or date.min) >= conta.data_saldo
        ):
            conta.saldo_final = ext.saldo_final
            conta.data_saldo = ext.data_saldo
        elif ext.saldo_ilegivel and ext.data_saldo is not None and (
            conta.data_saldo is None or ext.data_saldo > conta.data_saldo
        ):
            # o saldo mais recente da conta e ilegivel: o de um extrato mais antigo nao vale por ele (SALDO_ESTIMADO)
            conta.saldo_final = None
            conta.data_saldo = ext.data_saldo
        if ext.saldo_ilegivel and ext.data_saldo is None:
            ilegivel_sem_data.add(conta_id)  # sem data nao da para saber se e o mais recente: estima (abaixo)
        res.contas[conta_id] = conta
        if ext.ilegiveis:
            res.ilegiveis[conta_id] = res.ilegiveis.get(conta_id, 0) + ext.ilegiveis

        for t in ext.transacoes:
            if t["fitid"]:
                chave = (conta_id, t["fitid"])
                if chave in vistos:
                    continue
                vistos.add(chave)
            # sem FITID nao ha como saber se e repetido: entra sempre (o id() reaproveitado descartava lancamento)
            res.lancamentos.append({**t, "conta_id": conta_id})

        res.arquivos_lidos.append(path)

    for conta_id in ilegivel_sem_data:
        res.contas[conta_id].saldo_final = None  # vira SALDO_ESTIMADO, nunca saldo antigo como atual

    return res
