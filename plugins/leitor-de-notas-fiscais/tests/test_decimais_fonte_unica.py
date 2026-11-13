from engine.model import CAMPOS_DECIMAIS, NFSeServico, NFeProduto, DocumentoBase
from engine.extracao import _DECIMAIS as EXTRACAO_DECIMAIS


def test_campos_decimais_cobre_os_campodec_do_model():
    # toda anotacao CampoDec do model esta no conjunto canonico
    esperados = set()
    for cls in (DocumentoBase, NFSeServico, NFeProduto):
        for nome, f in cls.model_fields.items():
            if "Decimal" in str(f.annotation):
                esperados.add(nome)
    assert esperados.issubset(set(CAMPOS_DECIMAIS))


def test_extracao_usa_a_fonte_unica():
    assert set(EXTRACAO_DECIMAIS) == set(CAMPOS_DECIMAIS)


def test_csv_decimais_nao_diverge_dos_valores_reais():
    # toda coluna do csv que recebe um Decimal numa linha real esta em _DECIMAIS do csv
    from decimal import Decimal
    from engine.export.csv_generico import _DECIMAIS as CSV_DECIMAIS
    from engine.export.linha import montar_linha
    from engine.model import Campo, Confianca, Fonte
    def _c(v): return Campo(valor=v, confianca=Confianca(score=0.9, fonte=Fonte.PDF))
    nf = NFSeServico(emitente_cnpj=_c("11222333000181"), valor_servicos=_c(Decimal("100.00")),
                     iss_valor=_c(Decimal("5.00")), valor_recebido=_c(Decimal("120.00")))
    linha = montar_linha(nf, {"banda": "ALTA", "motivos": [], "score_documento": 0.9, "file_key": "k"}, "n.pdf")
    decimais_na_linha = {k for k, v in linha.items() if isinstance(v, Decimal)}
    assert decimais_na_linha.issubset(set(CSV_DECIMAIS)), f"colunas decimais fora do _DECIMAIS do csv: {decimais_na_linha - set(CSV_DECIMAIS)}"
