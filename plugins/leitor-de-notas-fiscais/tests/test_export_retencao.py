from decimal import Decimal

from engine.export.linha import montar_linha
from engine.export.csv_generico import COLUNAS, exportar_csv
from engine.model import Campo, Confianca, Fonte, NFSeServico


def _c(v):
    return Campo(valor=v, confianca=Confianca(score=1.0, fonte=Fonte.XML))


def test_linha_traz_retencao_e_alerta_recolhimento():
    nf = NFSeServico(
        emitente_cnpj=_c("11222333000181"),
        valor_servicos=_c(Decimal("10000.00")),
        iss_valor=_c(Decimal("500.00")),
        iss_tipo_retencao=_c("retido_tomador"),
        iss_municipio_incidencia=_c("3550308"),
        ret_federal_total=_c(Decimal("1115.00")),
    )
    rel = {"score_documento": 0.95, "banda": "ALTA", "file_key": "k",
           "iss_obrigacao_recolhimento_tomador": True, "motivos": []}
    linha = montar_linha(nf, rel, "nota.xml")
    assert linha["iss_tipo_retencao"] == "retido_tomador"
    assert linha["iss_municipio_incidencia"] == "3550308"
    assert linha["iss_recolher_tomador"] == "Sim"
    assert linha["ret_federal_total"] == Decimal("1115.00")


def test_colunas_novas_no_csv():
    for col in ("iss_tipo_retencao", "iss_municipio_incidencia", "iss_recolher_tomador", "ret_federal_total"):
        assert col in COLUNAS
    # smoke: serializa sem quebrar
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"))
    rel = {"score_documento": 0.5, "banda": "BAIXA", "file_key": "k",
           "iss_obrigacao_recolhimento_tomador": False, "motivos": []}
    csv = exportar_csv([montar_linha(nf, rel, "n.xml")])
    assert "iss_recolher_tomador" in csv.splitlines()[0]
