from engine.batch import processar_extracoes
from tests.fixtures_status_natureza import NFSE_PDF_CANCELADA


def test_carga_traz_natureza_e_cancelada():
    # via processar_extracoes (PDF) p/ ter a linha de carga
    nfe = {"classe": "nfe", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
           "total_nota": {"valor": "500,00"}, "total_produtos": {"valor": "500,00"},
           "natureza_operacao": {"valor": "DEVOLUCAO DE MERCADORIA"}}}
    l = processar_extracoes([("d.pdf", nfe)])["linhas"][0]
    assert "DEVOLUCAO" in (l.get("natureza_operacao") or "")
    assert processar_extracoes([("c.pdf", NFSE_PDF_CANCELADA)])["linhas"][0]["cancelada"] == "Sim"


def test_natureza_capturada_vai_pro_categoria_do_perfil_erp():
    # natOp capturada deve surfar no campo `natureza` (= Categoria nos perfis omie/contaazul),
    # senao o dado capturado se perde no export pra exatamente as NF-e que essa captura adiciona.
    nfe = {"classe": "nfe", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
           "total_nota": {"valor": "500,00"}, "total_produtos": {"valor": "500,00"},
           "natureza_operacao": {"valor": "DEVOLUCAO DE MERCADORIA"}}}
    l = processar_extracoes([("d.pdf", nfe)])["linhas"][0]
    assert l["natureza"] == "DEVOLUCAO DE MERCADORIA"           # agora preenchido (era "")
    assert l["natureza_operacao"] == "DEVOLUCAO DE MERCADORIA"  # sinal explicito mantido


def test_sem_natureza_capturada_segue_a_preencher():
    nfe = {"classe": "nfe", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
           "total_nota": {"valor": "500,00"}, "total_produtos": {"valor": "500,00"}}}
    l = processar_extracoes([("n.pdf", nfe)])["linhas"][0]
    assert l["natureza"] in (None, "")   # a preencher


def test_natureza_capturada_no_csv_do_perfil_omie():
    # contrato do perfil ERP: a coluna "Categoria" (<- natureza) recebe o capturado.
    from engine.export.perfis import exportar_perfil
    nfe = {"classe": "nfe", "campos": {"emitente_cnpj": {"valor": "11222333000181"},
           "total_nota": {"valor": "500,00"}, "total_produtos": {"valor": "500,00"},
           "natureza_operacao": {"valor": "DEVOLUCAO DE MERCADORIA"}}}
    linhas = processar_extracoes([("d.pdf", nfe)])["linhas"]
    csv = exportar_perfil(linhas, "omie")
    assert "Categoria" in csv.splitlines()[0]
    assert "DEVOLUCAO DE MERCADORIA" in csv.splitlines()[1]
