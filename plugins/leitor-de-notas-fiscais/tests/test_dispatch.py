from pathlib import Path

from engine.dispatch import processar

FIX = Path(__file__).parent / "fixtures"


def _read(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_dispatch_abrasf_ponta_a_ponta():
    rel = processar(_read("nfse_abrasf_exemplo.xml"))
    assert rel["familia"] == "nfse_abrasf"
    assert rel["iss_ok"] is True and rel["liquido_ok"] is True
    assert rel["banda"] == "ALTA"


def test_dispatch_nacional():
    rel = processar(_read("nfse_nacional_exemplo.xml"))
    assert rel["familia"] == "nfse_nacional"
    assert rel["banda"] == "ALTA"


def test_dispatch_nfe():
    rel = processar(_read("nfe_exemplo.xml"))
    assert rel["familia"] == "nfe"
    assert rel["total_ok"] is True


def test_dispatch_desconhecido():
    rel = processar("<x/>")
    assert rel["familia"] == "desconhecido"
    assert "erro" in rel


def test_dispatch_sp_ponta_a_ponta():
    rel = processar(_read("nfse_sp_exemplo.xml"))
    assert rel["familia"] == "nfse_sp"
    assert rel["iss_ok"] is True          # 1000 x 5% (normalizado) = 50
    assert rel["liquido_ok"] is None       # SP sem liquido -> invariante pulado
    assert rel["banda"] == "ALTA"          # iss ok + cnpj ok
