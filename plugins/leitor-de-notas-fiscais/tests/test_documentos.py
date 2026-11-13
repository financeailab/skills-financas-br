from engine.documentos import cnpj_dv_valido, cpf_dv_valido


def test_cnpj_valido():
    assert cnpj_dv_valido("11.222.333/0001-81") is True
    assert cnpj_dv_valido("11222333000181") is True


def test_cnpj_invalido():
    assert cnpj_dv_valido("11222333000180") is False   # DV errado
    assert cnpj_dv_valido("11111111111111") is False   # todos iguais
    assert cnpj_dv_valido("123") is False              # tamanho errado


def test_cpf_valido_e_invalido():
    assert cpf_dv_valido("529.982.247-25") is True
    assert cpf_dv_valido("52998224724") is False
