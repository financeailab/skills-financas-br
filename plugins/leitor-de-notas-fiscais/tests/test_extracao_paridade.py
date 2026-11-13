from decimal import Decimal
from engine.extracao import montar_nfse_de_extracao


def test_extracao_paridade():
    nf = montar_nfse_de_extracao({
        "emitente_endereco": {"valor": "Av X, 1 - SP", "rotulo_exato": True},
        "destinatario_endereco": {"valor": "Av Y, 2 - SP", "rotulo_exato": True},
        "intermediario_doc": {"valor": "11444777000161", "rotulo_exato": True},
        "intermediario_nome": {"valor": "Plataforma Y", "rotulo_exato": True},
        "ret_inss_base": {"valor": "1000.00", "rotulo_exato": True},
        "ret_inss_aliquota": {"valor": "11.00", "rotulo_exato": True},
        "valor_recebido": {"valor": "14943.31", "rotulo_exato": True},
    })
    assert nf.emitente_endereco.valor == "Av X, 1 - SP"
    assert nf.intermediario_doc.valor == "11444777000161"
    assert nf.ret_inss_base.valor == Decimal("1000.00")     # convertido
    assert nf.valor_recebido.valor == Decimal("14943.31")   # convertido
