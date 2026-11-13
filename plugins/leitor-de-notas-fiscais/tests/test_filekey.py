from engine.filekey import file_key, _slug


def test_chave_50_digitos_primaria():
    k = file_key(chave_acesso="NFS" + "3" * 50, modelo="NFSe")
    assert k == "3" * 50


def test_chave_44_digitos_nfe():
    k = file_key(chave_acesso="9" * 44, modelo="NFe")
    assert k == "9" * 44


def test_fallback_composto_quando_sem_chave():
    k = file_key(
        chave_acesso=None, modelo="NFSe", uf="SP", municipio_ibge="3550308",
        cnpj_prestador="11.222.333/0001-81", numero="123", aaaamm="202603",
    )
    assert k == "NFSE_SP_3550308_11222333000181_123_202603"


def test_slug_remove_caracteres():
    assert _slug("Razão/Social 01") == "RazaoSocial-01"


def test_serie_entra_na_reserva_so_quando_existe():
    base = dict(chave_acesso=None, modelo="NFe", cnpj_prestador="11222333000181", numero="123", aaaamm="202603")
    assert file_key(**base) == "NFE___11222333000181_123_202603"  # sem serie, o formato nao muda
    assert file_key(**base, serie="2") == "NFE___11222333000181_123_202603_2"
    assert file_key(**base, serie="A_1") == "NFE___11222333000181_123_202603_A-1"  # "_" separa partes: nao pode vir da serie
