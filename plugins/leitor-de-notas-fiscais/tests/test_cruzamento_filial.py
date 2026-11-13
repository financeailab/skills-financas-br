from engine.cruzamento import cruzar_tomador
from engine.model import Campo, Confianca, Fonte, NFSeServico, TomadorReferencia


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


REF = TomadorReferencia(cnpj="11.444.777/0001-61", municipio_ibge="3550308")


def test_filial_diferente_ainda_e_nossa():
    nf = NFSeServico(destinatario_doc=_c("11444777000242"))   # filial 0002
    assert cruzar_tomador(nf, REF)["enderecado_a_nos"] is True


def test_outra_empresa_nao_e_nossa():
    nf = NFSeServico(destinatario_doc=_c("99999999000199"))
    assert cruzar_tomador(nf, REF)["enderecado_a_nos"] is False
