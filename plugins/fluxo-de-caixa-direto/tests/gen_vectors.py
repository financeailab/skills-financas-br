# -*- coding: utf-8 -*-
"""Gabarito sintetico fake-BR do motor Fluxo de Caixa Direto (SPEC-00 §9 / PRD-FUT-14 §6).

Cenario: 2 contas OFX (corrente + poupanca), 8 semanas de lancamentos realizados
cobrindo as 9 categorias com keyword do dicionario-categorias.csv (+ 1 descricao
NAO mapeada), mais contas a pagar/a receber (perfil `generico`) com um titulo
futuro em aberto, um titulo VENCIDO ainda em aberto de cada lado, um titulo ja
baixado (nunca deve entrar na projecao) e um titulo grande o bastante pra forcar
uma semana projetada negativa.

`DATA_BASE = 2026-07-20` cai exatamente numa segunda-feira (ISO semana 30), o que
deixa a aritmetica de semana simples de conferir a mao nos testes de dfc.py.

Nenhum dado real. Tudo inventado pra exercitar o motor.
"""
from __future__ import annotations

from datetime import date

DATA_BASE = date(2026, 7, 20)

CONTAS_PROPRIAS = ["11111-1", "22222-2"]


# --- construtor de OFX 1.x SGML (mesmo dialeto que o conversor-extrato emite) ---

def _ofx_conta(banco, agencia, conta, tipo_conta, transacoes, saldo_final=None, dtasof=None):
    """Monta um OFX 1.x SGML minimo com N <STMTTRN>. `transacoes` = lista de
    (data 'AAAAMMDD', valor 'NNNN.NN' com sinal, memo, fitid)."""
    linhas_trn = []
    for dt, valor, memo, fitid in transacoes:
        tipo = "CREDIT" if not valor.startswith("-") else "DEBIT"
        linhas_trn.append(
            "<STMTTRN>"
            f"<TRNTYPE>{tipo}</TRNTYPE>"
            f"<DTPOSTED>{dt}</DTPOSTED>"
            f"<TRNAMT>{valor}</TRNAMT>"
            f"<FITID>{fitid}</FITID>"
            f"<MEMO>{memo}</MEMO>"
            "</STMTTRN>"
        )
    corpo_trn = "\n".join(linhas_trn)

    ledgerbal = ""
    if saldo_final is not None:
        ledgerbal = f"<LEDGERBAL><BALAMT>{saldo_final}</BALAMT><DTASOF>{dtasof}</DTASOF></LEDGERBAL>\n"

    return (
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "VERSION:102\n"
        "SECURITY:NONE\n"
        "ENCODING:UTF-8\n"
        "CHARSET:NONE\n"
        "COMPRESSION:NONE\n"
        "OLDFILEUID:NONE\n"
        "NEWFILEUID:NONE\n"
        "\n"
        "<OFX>\n"
        "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
        "<DTSERVER>20260719000000</DTSERVER><LANGUAGE>POR</LANGUAGE></SONRS></SIGNONMSGSRSV1>\n"
        "<BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>\n"
        "<STMTRS><CURDEF>BRL</CURDEF>\n"
        f"<BANKACCTFROM><BANKID>{banco}</BANKID><BRANCHID>{agencia}</BRANCHID>"
        f"<ACCTID>{conta}</ACCTID><ACCTTYPE>{tipo_conta}</ACCTTYPE></BANKACCTFROM>\n"
        f"<BANKTRANLIST><DTSTART>20260525</DTSTART><DTEND>20260719</DTEND>\n"
        f"{corpo_trn}\n"
        "</BANKTRANLIST>\n"
        f"{ledgerbal}"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )


# --- conta corrente A (Itau, 16 lancamentos, 8 semanas: 2026-05-25 a 2026-07-19) ---

_TXNS_CONTA_A = [
    # (data, valor, memo, fitid, categoria esperada)
    ("20260526", "15000.00", "PIX RECEBIDO CLIENTE ACME LTDA", "CCA0001", "Recebimentos"),
    ("20260528", "-3200.00", "PAGTO FORNECEDOR MATERIAL ESCRITORIO", "CCA0002", "Fornecedores"),
    ("20260605", "-1850.32", "DARF IRPJ COMPETENCIA MAIO", "CCA0003", "Impostos/Tributos"),
    ("20260605", "-22000.00", "FOLHA PAGAMENTO JUNHO", "CCA0004", "Folha & Benefícios"),
    ("20260610", "-4500.00", "ALUGUEL SALA COMERCIAL JUNHO", "CCA0005", "Aluguel/Ocupação"),
    ("20260612", "-42.90", "TARIFA MANUTENCAO CONTA PJ", "CCA0006", "Tarifas Bancárias"),
    ("20260615", "-10000.00", "APLICACAO CDB AUTOMATICA", "CCA0007", "Aplicações/Resgates"),
    ("20260618", "10120.00", "RESGATE AUTOMATICO CDB", "CCA0008", "Aplicações/Resgates"),
    # camada 1 (conta propria) tem PRECEDENCIA sobre a keyword "PIX ENVIADO" (que sozinha
    # seria Fornecedores). Prova real de precedencia dentro do gabarito, nao so em unit test.
    ("20260622", "-3000.00", "PIX ENVIADO CONTA PROPRIA 22222-2 APLICACAO INTERNA", "CCA0009", "Transferências Internas"),
    ("20260625", "-680.00", "PAGTO FATURA CARTAO CREDITO EMPRESARIAL", "CCA0010", "Fatura de Cartão"),
    ("20260629", "8200.00", "TED RECEBIDA CLIENTE BETA SA", "CCA0011", "Recebimentos"),
    ("20260702", "-95.00", "CONTA DE LUZ ENERGIA ELETRICA JUNHO", "CCA0012", "Aluguel/Ocupação"),
    ("20260706", "-310.00", "XPTO SERVICO ASSINATURA 123", "CCA0013", "Não classificado"),
    ("20260710", "-1200.00", "COMPRA MATERIAL GRAFICA", "CCA0014", "Fornecedores"),
    ("20260714", "-900.40", "GPS INSS COMPETENCIA JUNHO", "CCA0015", "Impostos/Tributos"),
    ("20260717", "500.00", "DEPOSITO EM DINHEIRO LOJA", "CCA0016", "Recebimentos"),
]

_TXNS_CONTA_B = [
    ("20260530", "3000.00", "TRANSFERENCIA ENTRE CONTAS MESMO CNPJ", "CPB0001", "Transferências Internas"),
    ("20260608", "-60.00", "TARIFA TED DOC PACOTE SERVICOS", "CPB0002", "Tarifas Bancárias"),
    ("20260620", "-350.00", "VALE TRANSPORTE FUNCIONARIOS", "CPB0003", "Folha & Benefícios"),
    ("20260701", "-180.00", "INTERNET E TELEFONIA ESCRITORIO", "CPB0004", "Aluguel/Ocupação"),
    ("20260708", "1500.00", "CREDITO LIQUIDACAO CARTAO VISA", "CPB0005", "Recebimentos"),
    ("20260715", "-220.00", "PAGAMENTO FATURA CARTAO NUBANK", "CPB0006", "Fatura de Cartão"),
]

SALDO_FINAL_CONTA_A = "58000.00"
SALDO_FINAL_CONTA_B = "12500.00"
DTASOF_CONTAS = "20260719"


def ofx_conta_a() -> str:
    return _ofx_conta("341", "1234", "11111-1", "CHECKING",
                       [(d, v, m, f) for d, v, m, f, _cat in _TXNS_CONTA_A],
                       saldo_final=SALDO_FINAL_CONTA_A, dtasof=DTASOF_CONTAS)


def ofx_conta_b() -> str:
    return _ofx_conta("001", "5678", "22222-2", "SAVINGS",
                       [(d, v, m, f) for d, v, m, f, _cat in _TXNS_CONTA_B],
                       saldo_final=SALDO_FINAL_CONTA_B, dtasof=DTASOF_CONTAS)


def categorias_esperadas() -> dict:
    """fitid -> categoria esperada, pras 22 transacoes realizadas do cenario."""
    return {f: cat for _d, _v, _m, f, cat in (_TXNS_CONTA_A + _TXNS_CONTA_B)}


def total_transacoes_realizadas() -> int:
    return len(_TXNS_CONTA_A) + len(_TXNS_CONTA_B)


def transacoes_realizadas_com_categoria() -> list[tuple[str, str]]:
    """(descricao, categoria_esperada) das 22 transacoes do cenario: usado tanto
    pelo categorizador (unit, sem precisar parsear OFX) quanto pelo dfc (pipeline
    completo, via categorias_esperadas())."""
    return [(m, cat) for _d, _v, m, _f, cat in (_TXNS_CONTA_A + _TXNS_CONTA_B)]


# --- fixtures avulsas (nao fazem parte do cenario principal) ---

def ofx_mesmo_acctid_bancos_diferentes() -> tuple[str, str]:
    """Dois OFX de BANCOS diferentes (341 Itau / 237 Bradesco) com o MESMO
    ACCTID e ao menos 1 FITID coincidente (achado Codex P1): as contas NAO
    podem se fundir, os 2 LEDGERBALs somam e nenhum lancamento e descartado
    pelo dedup."""
    ofx_itau = _ofx_conta("341", "0001", "12345-6", "CHECKING",
                           [("20260710", "100.00", "PIX RECEBIDO CLIENTE ITAU", "DUP001"),
                            ("20260712", "-40.00", "TARIFA MANUTENCAO CONTA", "IT0002")],
                           saldo_final="100.00", dtasof="20260719")
    ofx_bradesco = _ofx_conta("237", "0002", "12345-6", "CHECKING",
                               [("20260711", "200.00", "TED RECEBIDA CLIENTE BRADESCO", "DUP001")],
                               saldo_final="200.00", dtasof="20260719")
    return ofx_itau, ofx_bradesco


def ofx_sem_ledgerbal() -> str:
    """Conta sem bloco LEDGERBAL -> dispara alerta SALDO_ESTIMADO."""
    return _ofx_conta("237", "0001", "99999-9", "CHECKING",
                       [("20260715", "1000.00", "PIX RECEBIDO TESTE", "SEM0001")])


def ofx_dado_velho(dtasof: str) -> str:
    """Conta com DTASOF antigo (parametrizavel) -> dispara alerta DADO_VELHO quando
    DTASOF fica a mais de 7 dias da data-base."""
    return _ofx_conta("033", "0002", "88888-8", "CHECKING",
                       [("20260601", "500.00", "PIX RECEBIDO TESTE", "VELHO001")],
                       saldo_final="500.00", dtasof=dtasof)


def ofx_conta_xml_2x() -> str:
    """OFX 2.x (XML, tags fechadas), mesmo conteudo semantico de um STMTTRN simples.
    Prova que o parser aceita os dois dialetos."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE" OLDFILEUID="NONE" NEWFILEUID="NONE"?>\n'
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL</CURDEF>"
        "<BANKACCTFROM><BANKID>104</BANKID><BRANCHID>0003</BRANCHID>"
        "<ACCTID>77777-7</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>"
        "<BANKTRANLIST><DTSTART>20260701</DTSTART><DTEND>20260710</DTEND>"
        "<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260705</DTPOSTED>"
        "<TRNAMT>250.00</TRNAMT><FITID>XML0001</FITID>"
        "<MEMO>PIX RECEBIDO VIA XML</MEMO></STMTTRN>"
        "</BANKTRANLIST>"
        "<LEDGERBAL><BALAMT>250.00</BALAMT><DTASOF>20260710</DTASOF></LEDGERBAL>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )


# --- contas a pagar / a receber (perfil `generico`) ---

def titulos_pagar_generico() -> list[dict]:
    return [
        {"fornecedor": "ABC Materiais", "documento": "NF-1001", "vencimento": "10/08/2026",
         "valor": "5000,00", "status": "aberto"},
        # vencido ANTES da data-base mas ainda em aberto -> ATRASADO_EM_ABERTO, entra semana 0
        {"fornecedor": "XYZ Servicos", "documento": "NF-1002", "vencimento": "05/07/2026",
         "valor": "1200,00", "status": "pendente"},
        # ja baixado -> NUNCA entra na projecao (invariante #5)
        {"fornecedor": "Fornecedor Ja Pago", "documento": "NF-0999", "vencimento": "01/07/2026",
         "valor": "999,00", "status": "pago"},
        # grande o bastante pra forcar saldo negativo na semana 1
        {"fornecedor": "Fornecedor Grande Equipamentos", "documento": "NF-2000",
         "vencimento": "27/07/2026", "valor": "80000,00", "status": "a pagar"},
    ]


def titulos_receber_generico() -> list[dict]:
    return [
        {"cliente": "Cliente Grande Corp", "documento": "NF-R500", "vencimento": "24/08/2026",
         "valor": "15000,00", "status": "a receber"},
        # vencido ANTES da data-base mas ainda em aberto -> ATRASADO_EM_ABERTO, entra semana 0
        {"cliente": "Cliente Atrasado Ltda", "documento": "NF-R501", "vencimento": "10/07/2026",
         "valor": "3000,00", "status": "aberto"},
        # ja baixado -> NUNCA entra na projecao (invariante #5)
        {"cliente": "Cliente Ja Recebido", "documento": "NF-R502", "vencimento": "05/07/2026",
         "valor": "2000,00", "status": "recebido"},
    ]


# saldo inicial esperado = LEDGERBAL conta A + conta B
SALDO_INICIAL_ESPERADO = "70500.00"
# semana 0 (2026-07-20..26): +3000 (receber atrasado) -1200 (pagar atrasado) = 72300.00
SALDO_SEMANA_0_ESPERADO = "72300.00"
# semana 1 (2026-07-27..08-02): -80000 (NF-2000) -> negativo
SALDO_SEMANA_1_ESPERADO = "-7700.00"
