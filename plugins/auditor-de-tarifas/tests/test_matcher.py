# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.engine.matcher import classifica


def test_manutencao():
    assert classifica("TAR MANUTENCAO CESTA SERVICOS") == "manutencao"
    assert classifica("mensalidade pacote de servicos") == "manutencao"


def test_transferencia_tarifa_com_marcador():
    assert classifica("TAR TED") == "transferencia"
    assert classifica("TARIFA DOC/TED") == "transferencia"
    assert classifica("TAR TRANSFERENCIA") == "transferencia"


def test_transferencia_operacao_real_nao_e_tarifa():
    # TED/DOC sozinhos (sem marcador de tarifa) sao a OPERACAO, nao a tarifa.
    assert classifica("TED 50000,00 PAGAMENTO FORNECEDOR") is None
    assert classifica("DOC RECEBIDO EMPRESA XPTO LTDA") is None


def test_pix():
    assert classifica("TARIFA PIX ENVIO") == "pix"
    assert classifica("TAR PIX") == "pix"
    assert classifica("PIX ENVIO TARIFA COBRADA") == "pix"


def test_pix_operacao_real_nao_e_tarifa():
    assert classifica("PIX RECEBIDO JOAO SILVA") is None
    assert classifica("PIX ENVIADO MARIA") is None


def test_boleto():
    assert classifica("TAR BOLETO EMISSAO") == "boleto"
    # LIQUIDACAO/EMISSAO so contam como tarifa COM marcador (senao e a operacao)
    assert classifica("TAR LIQUIDACAO BOLETO") == "boleto"
    assert classifica("TARIFA EMISSAO BOLETO") == "boleto"


def test_boleto_operacao_sem_marcador_e_ignorada():
    # pagar/emitir um boleto (a operacao) NAO e tarifa sem marcador junto.
    assert classifica("LIQUIDACAO DE BOLETO 5000,00") is None
    assert classifica("EMISSAO DE BOLETO") is None


def test_custodia():
    assert classifica("TAR CUSTODIA TITULOS") == "custodia"
    assert classifica("MANUTENCAO DE TITULO") == "custodia"


def test_cartao():
    assert classifica("TAR CARTAO ANUIDADE") == "cartao"
    assert classifica("ANUIDADE CARTAO CREDITO") == "cartao"


def test_saque_extrato():
    assert classifica("TAR SAQUE ATM") == "saque_extrato"
    assert classifica("SEGUNDA VIA CARTAO") == "saque_extrato"


def test_imposto_iof_a_parte():
    assert classifica("IOF OPERACAO CREDITO") == "imposto"


def test_outra_tarifa_fallback_generico():
    assert classifica("TAR XPTO SERVICO NOVO") == "outra_tarifa"
    assert classifica("TARIFA DE SERVICO DESCONHECIDO") == "outra_tarifa"


def test_juros_nao_e_tarifa():
    assert classifica("JUROS CHEQUE ESPECIAL") is None


def test_acento_e_caixa_tolerantes():
    assert classifica("tar manutenção cesta serviços") == "manutencao"
    assert classifica("TAR DE TRANSFERÊNCIA") == "transferencia"


def test_saque_sozinho_nao_e_tarifa():
    # SAQUE sem o prefixo TAR e a operacao de saque em si, nao a tarifa.
    assert classifica("SAQUE CAIXA ELETRONICO") is None


# --- termos reais do corpus (refino P2) ---

def test_manutencao_nomes_reais_de_pacote():
    assert classifica("CONTA CERTA") == "manutencao"
    assert classifica("MANUTENCAO CC") == "manutencao"
    assert classifica("CONTA MAX") == "manutencao"
    assert classifica("TARIFA BANCARIA MAX") == "manutencao"
    assert classifica("TAR CTA GARANTIDA") == "manutencao"
    # MENSALIDADE sozinha e operacao (escola, condominio): so tarifa com marcador
    assert classifica("PIX PAGAMENTO MENSALIDADE ESCOLAR") is None
    assert classifica("TARIFA MENSALIDADE PACOTE") == "manutencao"


def test_boleto_descritores_reais_de_cobranca():
    assert classifica("TAR CUSTAS COBRANCA") == "boleto"
    assert classifica("CUSTAS COBRANCA") == "boleto"
    assert classifica("TAR COBRANCA EXP") == "boleto"


def test_pix_pagto_pix_so_com_marcador():
    # com marcador de tarifa -> tarifa
    assert classifica("TARIFA PAGTO PIX") == "pix"
    assert classifica("TARIFA PAGTO. PIX") == "pix"


def test_pix_pagto_pix_sozinho_e_operacao_ignorada():
    # PAGTO PIX sem marcador de tarifa e a OPERACAO, nao a tarifa.
    assert classifica("PAGTO PIX FORNECEDOR") is None
    assert classifica("PAGTO. PIX") is None


def test_cambio_nova_categoria():
    assert classifica("TAR OPE") == "cambio"
    assert classifica("TAR CAMB") == "cambio"
    assert classifica("TARIFA ENVIO OPE") == "cambio"
    assert classifica("TARIFA AVULSA ENVIO") == "cambio"
    # envio de Pix com tarifa avulsa e Pix, nao cambio (pix vem antes de cambio na ordem)
    assert classifica("TARIFA AVULSA ENVIO PIX") == "pix"
    assert classifica("CARTA CIRCULARIZADORA") == "cambio"


def test_cambio_ope_exige_o_tar():
    # OPE sem o prefixo TAR (ex.: descricao de operacao) nao vira tarifa de cambio.
    assert classifica("OPE 12345 LIQUIDACAO") is None


# --- Bug 7: prefixo TARIFA (nao so TAR) casa as categorias especificas ---

def test_prefixo_tarifa_por_extenso_casa_categoria_certa():
    assert classifica("TARIFA MANUTENCAO") == "manutencao"
    assert classifica("TARIFA TED") == "transferencia"
    assert classifica("TARIFA TRANSFERENCIA") == "transferencia"
    assert classifica("TARIFA BOLETO") == "boleto"
    assert classifica("TARIFA CUSTODIA") == "custodia"
    assert classifica("TARIFA CARTAO") == "cartao"
    assert classifica("TARIFA SAQUE") == "saque_extrato"
    assert classifica("TARIFA CAMB") == "cambio"
    assert classifica("TARIFA OPE") == "cambio"


def test_prefixo_tarifa_nao_quebra_ambiguidade():
    # ampliar TAR->TARIFA no reconhecimento nao pode transformar operacao em tarifa.
    assert classifica("TED 50000,00 PAGAMENTO FORNECEDOR") is None
    assert classifica("LIQUIDACAO DE BOLETO 5000,00") is None
    assert classifica("PAGTO PIX FORNECEDOR") is None
    assert classifica("OPE 12345 LIQUIDACAO") is None


# --- v0.1.2 (D2): termo generico dentro de uma operacao, sem marcador, nao e tarifa ---

def test_termo_generico_dentro_de_operacao_sem_marcador_nao_e_tarifa():
    assert classifica("PIX ENVIADO CESTA BASICA X") is None
    assert classifica("BOLETO ANUIDADE CONSELHO X") is None
    assert classifica("PIX ENVIADO CONTA MAX LTDA") is None
    assert classifica("PIX ENVIADO CONTA CERTA ME") is None
    assert classifica("TED CUSTODIA X") is None
    # limite aceito na spec (D2): tarifa real escrita com palavra de operacao e sem TAR deixa de somar
    assert classifica("PAGTO ANUIDADE CARTAO") is None


def test_veto_de_operacao_preserva_tarifa_e_termo_sozinho():
    assert classifica("PIX ENVIADO MARIA TAR") == "outra_tarifa"
    assert classifica("CUSTAS COBRANCA BOLETO") == "boleto"
    assert classifica("SEGUNDA VIA BOLETO") == "saque_extrato"
    assert classifica("TAR CESTA") == "manutencao"
    assert classifica("CESTA EXPRESSO") == "manutencao"
    assert classifica("ANUIDADE CARTAO") == "cartao"


def test_quadro_da_peca_tarifa_pix_pj_mantem_a_classe():
    # site/src/content/aprender/2026-11-05-tarifa-pix-pj/index.md:39-48 (classe medida na v0.1.1)
    quadro = {
        "PIX ENVIADO": None,
        "PIX RECEBIDO": None,
        "PAGTO PIX": None,
        "PIX QR LIQ ESTATICO": None,
        "TARIFA PIX ENVIO": "pix",
        "TAR PIX PJ": "pix",
        "TARIFA AVULSA ENVIO PIX": "pix",
        "TARIFA PIX RECEBIDO QR CHECKOUT": "pix",
        "TAR PIX QR LIQ ESTATICO": "pix",
        "PAGTO PIX TARIFA": "pix",
        "PIX ENVIADO TARIFA": "outra_tarifa",
    }
    assert {nome: classifica(nome) for nome in quadro} == quadro
