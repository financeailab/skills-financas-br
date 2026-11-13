from engine.model import TomadorReferencia


def test_tomador_referencia_basico():
    t = TomadorReferencia(cnpj="11.222.333/0001-81", municipio_ibge="3550308")
    assert t.cnpj == "11.222.333/0001-81"
    assert t.municipio_ibge == "3550308"
