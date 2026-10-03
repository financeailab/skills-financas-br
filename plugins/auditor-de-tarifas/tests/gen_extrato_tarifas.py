# -*- coding: utf-8 -*-
"""Gerador de fixtures (OFX + CSV) a partir de lancamentos CONHECIDOS (fake-BR).

SPEC-00 secao 9 (gabarito sintetico). Cada lancamento tem o tipo esperado
anotado; os testes assert contra os TOTAIS ao centavo, nao contra a lista
crua (o motor e o alvo do teste, nao este gerador).

Nenhum dado real: valores redondos, nomes ficticios.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

# (banco, data, descricao, valor, tipo_esperado, arquivo)
# arquivo: "ofx" -> banco 341 (Itau fake); "csv" -> banco 237 (Bradesco fake)
LANCAMENTOS = [
    # --- banco 341, arquivo OFX ---
    ("341", date(2024, 12, 20), "TAR MANUTENCAO CESTA SERVICOS", Decimal("-25.00"), "manutencao", "ofx"),
    ("341", date(2025, 1, 5), "TAR MANUTENCAO CESTA SERVICOS", Decimal("-29.90"), "manutencao", "ofx"),
    ("341", date(2025, 1, 10), "TAR TED", Decimal("-10.90"), "transferencia", "ofx"),  # armadilha: TAR+TED
    ("341", date(2025, 1, 15), "TED 50000,00 PAGAMENTO FORNECEDOR", Decimal("-50000.00"), None, "ofx"),  # operacao real, NAO tarifa
    ("341", date(2025, 1, 20), "TARIFA PIX ENVIO", Decimal("-1.50"), "pix", "ofx"),
    ("341", date(2025, 1, 25), "TAR BOLETO EMISSAO", Decimal("-3.90"), "boleto", "ofx"),
    ("341", date(2025, 2, 2), "TAR CUSTODIA TITULOS", Decimal("-15.00"), "custodia", "ofx"),
    ("341", date(2025, 2, 5), "TAR CARTAO ANUIDADE", Decimal("-120.00"), "cartao", "ofx"),
    ("341", date(2025, 2, 10), "TAR SAQUE ATM", Decimal("-6.50"), "saque_extrato", "ofx"),
    ("341", date(2025, 2, 12), "IOF OPERACAO CREDITO", Decimal("-8.32"), "imposto", "ofx"),
    ("341", date(2025, 2, 15), "TAR XPTO SERVICO NOVO", Decimal("-4.20"), "outra_tarifa", "ofx"),  # termo inventado
    ("341", date(2025, 2, 20), "PIX RECEBIDO JOAO SILVA", Decimal("2500.00"), None, "ofx"),  # credito real, NAO tarifa
    ("341", date(2025, 2, 22), "JUROS CHEQUE ESPECIAL", Decimal("-45.00"), None, "ofx"),  # juros, NAO tarifa

    # --- banco 237, arquivo CSV ---
    ("237", date(2025, 1, 8), "TAR MANUTENCAO", Decimal("-19.90"), "manutencao", "csv"),
    ("237", date(2025, 2, 18), "TAR PIX", Decimal("-2.00"), "pix", "csv"),
]


def gerar_ofx(banco: str) -> str:
    """Monta um OFX SGML (tags sem fechamento, como extrato real pre-2.0)."""
    linhas = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "",
        "<OFX>",
        "<BANKMSGSRSV1>",
        "<STMTTRNRS>",
        "<STMTRS>",
        "<BANKACCTFROM>",
        f"<BANKID>{banco}",
        "<ACCTID>12345-6",
        "</BANKACCTFROM>",
        "<BANKTRANLIST>",
    ]
    for lb, d, desc, valor, _tipo, arquivo in LANCAMENTOS:
        if arquivo != "ofx" or lb != banco:
            continue
        dtposted = f"{d.year:04d}{d.month:02d}{d.day:02d}120000[-3:GMT]"
        linhas += [
            "<STMTTRN>",
            "<TRNTYPE>DEBIT" if valor < 0 else "<TRNTYPE>CREDIT",
            f"<DTPOSTED>{dtposted}",
            f"<TRNAMT>{valor}",
            "<FITID>1",
            f"<MEMO>{desc}",
            "</STMTTRN>",
        ]
    linhas += [
        "</BANKTRANLIST>",
        "</STMTRS>",
        "</STMTTRNRS>",
        "</BANKMSGSRSV1>",
        "</OFX>",
    ]
    return "\n".join(linhas)


def gerar_csv(banco: str) -> str:
    """Monta um CSV BR (';' delimitador, ',' decimal), como export de banco."""
    linhas = ["data;descricao;valor;banco"]
    for lb, d, desc, valor, _tipo, arquivo in LANCAMENTOS:
        if arquivo != "csv" or lb != banco:
            continue
        valor_br = str(valor).replace(".", ",")
        linhas.append(f"{d.day:02d}/{d.month:02d}/{d.year:04d};{desc};{valor_br};{lb}")
    return "\n".join(linhas)


def escreve_fixtures(tmp_path) -> tuple:
    """Escreve os 2 arquivos de fixture num diretorio e devolve os caminhos."""
    ofx_path = tmp_path / "extrato_itau.ofx"
    csv_path = tmp_path / "extrato_bradesco.csv"
    ofx_path.write_text(gerar_ofx("341"), encoding="utf-8")
    csv_path.write_text(gerar_csv("237"), encoding="utf-8")
    return ofx_path, csv_path


# --- gabarito (totais esperados, calculados a partir de LANCAMENTOS) ---

def _soma_tarifa(lancamentos, ano=None):
    total = Decimal("0.00")
    for _lb, d, _desc, valor, tipo, _arq in lancamentos:
        if tipo is None or tipo == "imposto":
            continue
        if ano is not None and d.year != ano:
            continue
        total += abs(valor)
    return total


def _soma_iof(lancamentos, ano=None):
    total = Decimal("0.00")
    for _lb, d, _desc, valor, tipo, _arq in lancamentos:
        if tipo != "imposto":
            continue
        if ano is not None and d.year != ano:
            continue
        total += abs(valor)
    return total


def _conta_nao_classificados(lancamentos, ano=None):
    n = 0
    for _lb, d, _desc, _valor, tipo, _arq in lancamentos:
        if tipo != "outra_tarifa":
            continue
        if ano is not None and d.year != ano:
            continue
        n += 1
    return n


TOTAL_TARIFA_SEM_FILTRO = _soma_tarifa(LANCAMENTOS)                  # 238.80
TOTAL_TARIFA_2025 = _soma_tarifa(LANCAMENTOS, ano=2025)               # 213.80
TOTAL_IOF_2025 = _soma_iof(LANCAMENTOS, ano=2025)                     # 8.32
NAO_CLASSIFICADOS_2025 = _conta_nao_classificados(LANCAMENTOS, ano=2025)  # 1
