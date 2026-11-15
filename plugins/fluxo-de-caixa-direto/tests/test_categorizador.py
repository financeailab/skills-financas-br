# -*- coding: utf-8 -*-
"""categorizador.py: dicionario BR (SPEC-00 §3), precedencia contas-proprias >
keyword mais longa > ordem de tabela, e "Não classificado" quando nao bate
(invariante #6, SPEC-00 §8)."""
import gen_vectors as gv
from categorizador import (
    carregar_dicionario, categorizar,
    CATEGORIA_TRANSFERENCIAS, CATEGORIA_NAO_CLASSIFICADO,
)


def test_carregar_dicionario_default_tem_as_10_categorias():
    dic = carregar_dicionario()
    categorias = {c for c, _kw in dic}
    esperado = {
        "Recebimentos", "Fornecedores", "Impostos/Tributos", "Folha & Benefícios",
        "Aluguel/Ocupação", "Tarifas Bancárias", "Aplicações/Resgates",
        "Transferências Internas", "Fatura de Cartão",
    }
    assert esperado <= categorias
    for cat in esperado:
        assert sum(1 for c, _kw in dic if c == cat) >= 5, f"{cat} tem menos de 5 keywords"


def test_camada1_conta_propria_tem_precedencia_sobre_keyword():
    dic = carregar_dicionario()
    # "PIX ENVIADO" sozinho seria Fornecedores; com o identificador de conta
    # propria na descricao, tem que vencer como Transferencias Internas.
    descricao = "PIX ENVIADO CONTA PROPRIA 22222-2 APLICACAO INTERNA"
    categoria, regra = categorizar(descricao, dic, contas_proprias=["22222-2"])
    assert categoria == CATEGORIA_TRANSFERENCIAS
    assert regra == "conta-propria:22222-2"


def test_sem_contas_proprias_a_mesma_descricao_cai_pra_keyword():
    dic = carregar_dicionario()
    descricao = "PIX ENVIADO CONTA PROPRIA 22222-2 APLICACAO INTERNA"
    categoria, regra = categorizar(descricao, dic, contas_proprias=None)
    assert categoria == "Fornecedores"
    assert regra.startswith("keyword:Fornecedores:")


def test_empate_keyword_mais_longa_vence():
    dic = [("Categoria Curta", "PIX"), ("Categoria Longa", "PIX RECEBIDO")]
    categoria, regra = categorizar("PIX RECEBIDO CLIENTE ACME", dic)
    assert categoria == "Categoria Longa"
    assert regra == "keyword:Categoria Longa:PIX RECEBIDO"


def test_empate_mesmo_tamanho_usa_ordem_da_tabela():
    dic = [("Primeira Da Tabela", "ABC"), ("Segunda Da Tabela", "XYZ")]
    categoria, _regra = categorizar("prefixo ABC meio XYZ sufixo", dic)
    assert categoria == "Primeira Da Tabela"


def test_sem_match_retorna_nao_classificado():
    dic = carregar_dicionario()
    categoria, regra = categorizar("XPTO SERVICO ASSINATURA 123", dic)
    assert categoria == CATEGORIA_NAO_CLASSIFICADO
    assert regra == "sem-match"


def test_case_e_acento_insensitive():
    dic = carregar_dicionario()
    categoria, _regra = categorizar("recebimento via convênio bancário", dic)
    assert categoria == "Recebimentos"


def test_dicionario_customizado_via_arquivo(tmp_path):
    p = tmp_path / "custom.csv"
    p.write_text("categoria,keyword\nMinha Categoria,PALAVRA MAGICA\n", encoding="utf-8")
    dic = carregar_dicionario(str(p))
    categoria, regra = categorizar("contem PALAVRA MAGICA no meio", dic)
    assert categoria == "Minha Categoria"
    assert regra == "keyword:Minha Categoria:PALAVRA MAGICA"


def test_gabarito_completo_bate_categoria_esperada():
    """Roda o categorizador default nas 22 descricoes do gabarito (gen_vectors)
    e confere cada uma contra a categoria esperada, incluindo o caso de
    precedencia real (conta propria) e o Não classificado."""
    dic = carregar_dicionario()
    for descricao, esperada in gv.transacoes_realizadas_com_categoria():
        categoria, _regra = categorizar(descricao, dic, contas_proprias=gv.CONTAS_PROPRIAS)
        assert categoria == esperada, f"{descricao!r}: esperado {esperada!r}, veio {categoria!r}"
