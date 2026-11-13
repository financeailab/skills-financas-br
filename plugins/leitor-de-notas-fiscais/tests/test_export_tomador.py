from engine.export.linha import montar_linha
from engine.export.csv_generico import COLUNAS
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_colunas_tomador_no_csv():
    assert "nota_enderecada_a_voce" in COLUNAS
    assert "alerta_retencao" in COLUNAS


def test_linha_traz_enderecamento_e_alerta():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"))
    rel = {"score_documento": 0.5, "banda": "BAIXA", "file_key": "k", "motivos": [],
           "enderecado_a_nos": False, "alerta_retencao_nao_destacada": True}
    linha = montar_linha(nf, rel, "n.xml")
    assert linha["nota_enderecada_a_voce"] == "Não"
    assert linha["alerta_retencao"] == "Sim"


def test_linha_sem_contexto_deixa_vazio():
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"))
    rel = {"score_documento": 0.9, "banda": "ALTA", "file_key": "k", "motivos": []}
    linha = montar_linha(nf, rel, "n.xml")
    assert linha["nota_enderecada_a_voce"] == ""   # desconhecido/sem contexto
    assert linha["alerta_retencao"] == ""
