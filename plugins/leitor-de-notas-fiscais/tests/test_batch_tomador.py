from engine.batch import processar_lote
from engine.model import TomadorReferencia
from tests.test_extracao_tomador import NACIONAL

REF = TomadorReferencia(cnpj="22222222000122", municipio_ibge="3550308")


def test_batch_propaga_tomador_ref():
    # com o contexto, o relatorio das NFS-e do lote tem a chave do cruzamento
    res = processar_lote([("nota.xml", NACIONAL)], perfil="generico", tomador_ref=REF)
    # a nota nacional do fixture e endereçada a 22222222000122 (== REF) -> True
    linha = res["linhas"][0]
    assert linha["nota_enderecada_a_voce"] == "Sim"
