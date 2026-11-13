import xml.etree.ElementTree as ET

from engine.parsers.aliases import ALIASES_ABRASF, ALIASES_SP, resolver_alias


def test_resolver_acha_primeiro_alias():
    root = ET.fromstring("<r><ValorServicos>1000.00</ValorServicos></r>")
    valor, usado = resolver_alias(root, ALIASES_ABRASF["valor_servicos"])
    assert valor == "1000.00"
    assert usado == "ValorServicos"


def test_resolver_tenta_aliases_em_ordem():
    root = ET.fromstring("<r><ValorLiquido>950.00</ValorLiquido></r>")
    valor, usado = resolver_alias(root, ALIASES_ABRASF["valor_liquido"])
    assert valor == "950.00"
    assert usado == "ValorLiquido"   # 2o alias, pois ValorLiquidoNfse ausente


def test_resolver_retorna_none_sem_match():
    root = ET.fromstring("<r><Outro>x</Outro></r>")
    valor, usado = resolver_alias(root, ALIASES_ABRASF["valor_servicos"])
    assert valor is None and usado is None


def test_aliases_sp_aliquota_e_base():
    root = ET.fromstring(
        "<NFe><ValorServicos>1000.00</ValorServicos><AliquotaServicos>0.05</AliquotaServicos></NFe>"
    )
    aliq, _ = resolver_alias(root, ALIASES_SP["iss_aliquota"])
    assert aliq == "0.05"
    # iss_base cai no fallback ValorServicos (SP nao emite BaseCalculo)
    base, usado = resolver_alias(root, ALIASES_SP["iss_base"])
    assert base == "1000.00" and usado == "ValorServicos"


def test_aliases_sp_cnpj_e_nome():
    root = ET.fromstring(
        "<NFe><CNPJ>11222333000181</CNPJ><RazaoSocialPrestador>X LTDA</RazaoSocialPrestador></NFe>"
    )
    cnpj, _ = resolver_alias(root, ALIASES_SP["emitente_cnpj"])
    nome, _ = resolver_alias(root, ALIASES_SP["emitente_nome"])
    assert cnpj == "11222333000181" and nome == "X LTDA"
