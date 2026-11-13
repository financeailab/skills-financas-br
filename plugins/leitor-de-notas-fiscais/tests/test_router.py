from pathlib import Path

from engine.router import Familia, classificar

FIX = Path(__file__).parent / "fixtures"


def _read(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_classifica_nacional():
    assert classificar(_read("nfse_nacional_exemplo.xml")) == Familia.NFSE_NACIONAL


def test_classifica_nfe():
    assert classificar(_read("nfe_exemplo.xml")) == Familia.NFE


def test_classifica_desconhecido():
    assert classificar("<x/>") == Familia.DESCONHECIDO
    assert classificar("isto nao e xml") == Familia.DESCONHECIDO


def test_classifica_abrasf_por_namespace():
    xml = '<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><InfNfse/></CompNfse>'
    assert classificar(xml) == Familia.NFSE_ABRASF


def test_classifica_abrasf_por_tag_sem_namespace():
    assert classificar("<CompNfse><InfNfse/></CompNfse>") == Familia.NFSE_ABRASF


def test_abrasf_com_tag_infnfse_filha_nao_vira_nacional():
    # namespace ABRASF tem prioridade: nao deve cair em NFSE_NACIONAL por causa da tag-filha
    xml = '<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd"><InfNfse><infNFSe/></InfNfse></CompNfse>'
    assert classificar(xml) == Familia.NFSE_ABRASF


def test_classifica_sp_por_namespace():
    xml = '<NFe xmlns="http://www.prefeitura.sp.gov.br/nfe"><ChaveNFe/></NFe>'
    assert classificar(xml) == Familia.NFSE_SP


def test_sp_nao_vira_nfe_apesar_da_raiz_NFe():
    # raiz <NFe> igual a da NF-e, mas namespace de SP -> NFSE_SP, nao NFE
    xml = '<NFe xmlns="http://www.prefeitura.sp.gov.br/nfe"><NumeroNFe>1</NumeroNFe></NFe>'
    assert classificar(xml) == Familia.NFSE_SP
