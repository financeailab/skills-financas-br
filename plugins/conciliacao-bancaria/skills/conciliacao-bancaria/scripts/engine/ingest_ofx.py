# -*- coding: utf-8 -*-
"""Parser OFX -> transacoes bancarias canonicas.

Cobre OFX 1.x (SGML, o que Itau/BB/Bradesco/Santander/Caixa/Nubank/Inter exportam)
e OFX 2.x (XML). O SGML omite tags de fechamento de campos-folha
(`<TRNAMT>-150.00` sem `</TRNAMT>`), entao NAO da pra usar um parser XML direto no 1.x.
Estrategia: regex tolerante por bloco <STMTTRN>...</STMTTRN>, robusta a encoding.

Saida: lista de dicts canonicos
  { 'data': date, 'valor': Decimal(+credito/-debito), 'doc': str|None,
    'descricao': str, 'tipo': str, 'fitid': str }
+ metadados de conta (banco, agencia, conta, tipo) e LEDGERBAL (saldo final).

Privacidade: este modulo roda LOCAL. Nada aqui faz rede. O orquestrador so
expoe ao Claude o resumo agregado, nunca estas linhas.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from decimal import Decimal

from normalize import parse_valor, parse_data, norm_doc, extrai_cpf_cnpj

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB — PRD-SAN-07 S-06 (anti-OOM em arquivo gigante)


@dataclass
class ExtratoOFX:
    banco: str = ""
    agencia: str = ""
    conta: str = ""
    tipo_conta: str = ""
    moeda: str = "BRL"
    saldo_final: Decimal | None = None
    data_saldo = None
    transacoes: list = field(default_factory=list)
    marcadores_saldo: int = 0   # linhas "Saldo Anterior/do dia" descartadas (quirk BB)
    n_contas: int = 0           # nº de contas no arquivo (>1 = multi-conta, Fase 1 reprova)
    txns_corrompidas: int = 0   # STMTTRN descartados por data/valor invalido
    eh_cartao: bool = False     # envelope de cartao de credito (CREDITCARDMSGSRSV1/CCACCTFROM sem BANKACCTFROM)


# E2E do Pix (EndToEndId), 32 chars: "E" + ISPB (8, [0-9A-Z]: CNPJ alfanumerico) + aaaaMMddHHmm (12 digitos)
# + 11 alfanumericos. A estrutura filtra outro codigo do MEMO. Identificador forte.
_E2E = re.compile(r"\bE[0-9A-Z]{8}\d{12}[0-9A-Za-z]{11}\b")


def _decode(raw: bytes) -> str:
    """OFX BR vem em Windows-1252/Latin-1 (CHARSET:1252) ou UTF-8. Tenta na ordem."""
    # header pode declarar ENCODING/CHARSET; mas na pratica tentar e o mais seguro
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _tag(bloco: str, nome: str) -> str | None:
    """Extrai o valor de uma tag-folha SGML: `<NOME>valor` ate o proximo '<' ou fim de linha.
    Funciona tanto pra SGML (sem fechamento) quanto pra XML (<NOME>valor</NOME>)."""
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.IGNORECASE)
    if not m:
        return None
    v = m.group(1).strip()
    return v or None


def parse_ofx(caminho: str) -> ExtratoOFX:
    # PRD-SAN-07 S-06: recusa arquivo gigante ANTES de carregar em memoria (erro
    # claro; o orquestrador ja converte excecao de parse em mensagem ao operador).
    tam = os.path.getsize(caminho)
    if tam > MAX_FILE_SIZE:
        raise ValueError(
            f"arquivo recusado: {os.path.basename(caminho)} tem {tam // (1024 * 1024)} MB "
            f"(limite: {MAX_FILE_SIZE // (1024 * 1024)} MB); exporte um periodo menor")
    raw = open(caminho, "rb").read()
    return parse_ofx_text(_decode(raw))


def parse_ofx_text(txt: str) -> ExtratoOFX:
    """Parseia OFX ja decodificado (str). Robusto a header bagunçado/19 linhas em
    branco/uma linha so porque trabalha por regex no CORPO, nao no cabecalho."""
    # neutraliza CDATA (mantem o texto, tira os <> internos) e <BR/> — senao truncam o MEMO
    txt = re.sub(r"<!\[CDATA\[(.*?)\]\]>",
                 lambda m: m.group(1).replace("<", " ").replace(">", " "), txt, flags=re.S | re.I)
    txt = re.sub(r"<\s*br\s*/?\s*>", " ", txt, flags=re.I)

    ext = ExtratoOFX()

    # --- nº de contas (conta corrente + cartao + poupanca num arquivo so) ---
    ext.n_contas = len(re.findall(r"<(?:BANK|CC)ACCTFROM>", txt, re.IGNORECASE)) \
        or len(re.findall(r"<(?:STMTRS|CCSTMTRS)>", txt, re.IGNORECASE))

    # --- envelope de cartao de credito? (CREDITCARDMSGSRSV1/CCACCTFROM/CCSTMTRS) ---
    # Alguns bancos (ex.: Nubank) exportam ate a CONTA no envelope de cartao, entao
    # esta deteccao e estrutural mas NAO definitiva: o consolidador (posicao.py) trata
    # cartao como fora do caixa e deixa o usuario forcar um arquivo como conta.
    tem_cc = bool(re.search(r"<CCACCTFROM>|<CREDITCARDMSGSRSV1>|<CCSTMTRS>", txt, re.IGNORECASE))
    tem_bank = bool(re.search(r"<BANKACCTFROM>|<STMTRS>", txt, re.IGNORECASE))
    ext.eh_cartao = tem_cc and not tem_bank

    # --- metadados de conta (1a conta; bancaria OU cartao) ---
    acct = re.search(r"<(?:BANK|CC)ACCTFROM>(.*?)</(?:BANK|CC)ACCTFROM>", txt, re.IGNORECASE | re.DOTALL)
    bloco_acct = acct.group(1) if acct else txt
    ext.banco = _tag(bloco_acct, "BANKID") or ""
    ext.agencia = _tag(bloco_acct, "BRANCHID") or ""
    ext.conta = _tag(bloco_acct, "ACCTID") or ""
    ext.tipo_conta = _tag(bloco_acct, "ACCTTYPE") or ""
    ext.moeda = _tag(txt, "CURDEF") or "BRL"

    # --- saldo final (LEDGERBAL) ---
    ledger = re.search(r"<LEDGERBAL>(.*?)</LEDGERBAL>", txt, re.IGNORECASE | re.DOTALL)
    if ledger:
        bal = _tag(ledger.group(1), "BALAMT")
        if bal is not None:
            try:
                ext.saldo_final = parse_valor(bal, origem="ofx")
            except (ValueError, ArithmeticError):
                ext.saldo_final = None  # saldo ilegivel nao derruba o arquivo: fica sem saldo (sem amarracao)
        dtasof = _tag(ledger.group(1), "DTASOF")
        if dtasof:
            try:
                ext.data_saldo = parse_data(dtasof)
            except ValueError:
                ext.data_saldo = None

    # --- transacoes ---
    # bloco = de <STMTTRN> ate </STMTTRN> OU o proximo <STMTTRN>/</BANKTRANLIST> (SGML pode omitir fechamento)
    for m in re.finditer(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>|$)",
                         txt, re.IGNORECASE | re.DOTALL):
        b = m.group(1)
        dt = _tag(b, "DTPOSTED")
        amt = _tag(b, "TRNAMT")
        if dt is None or amt is None:
            ext.txns_corrompidas += 1
            continue  # transacao corrompida -> ignora (sinalizado em txns_corrompidas)
        descricao = _tag(b, "MEMO") or _tag(b, "NAME") or ""
        fitid = _tag(b, "FITID") or ""
        # Quirk Banco do Brasil: injeta "Saldo Anterior" / "Saldo do dia" como
        # STMTTRN (sem FITID). Nao sao lancamentos — poluiriam o matching e a
        # amarracao. Descartar marcadores de saldo (validado com modelos reais do GitHub).
        if not fitid and descricao.strip().lower().startswith("saldo"):
            ext.marcadores_saldo += 1
            continue
        doc_raw = _tag(b, "CHECKNUM") or _tag(b, "REFNUM")
        descricao = descricao.strip()
        try:
            data = parse_data(dt)
            valor = parse_valor(amt, origem="ofx")   # OFX: ponto e SEMPRE decimal
        except (ValueError, ArithmeticError):
            ext.txns_corrompidas += 1               # data/valor invalido (lixo de conversor) -> ignora
            continue
        e2e = _E2E.search(descricao)
        ext.transacoes.append({
            "data": data,
            "valor": valor,                      # OFX ja vem com sinal: +credito / -debito
            "doc": norm_doc(doc_raw),
            "descricao": descricao,
            # enriquecimento p/ desempate (o banco costuma trazer contraparte; PIX traz CPF/CNPJ + E2E)
            "contraparte": descricao,            # nome bruto p/ overlap de tokens
            "cpf_cnpj": extrai_cpf_cnpj(descricao),
            "identificador": e2e.group(0) if e2e else None,  # E2E do Pix, quando vem no MEMO
            "tipo": (_tag(b, "TRNTYPE") or "").upper(),
            "fitid": fitid,
        })

    return ext
