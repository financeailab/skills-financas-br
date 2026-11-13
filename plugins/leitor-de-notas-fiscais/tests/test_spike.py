from pathlib import Path

from engine.spike import processar_nfse, processar_nfe

FIXDIR = Path(__file__).parent / "fixtures"


def test_spike_nfse_bate_gabarito():
    rel = processar_nfse((FIXDIR / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8"))
    # gabarito conhecido
    assert rel["iss_ok"] is True
    assert rel["liquido_ok"] is True
    assert rel["cnpj_ok"] is True
    assert rel["score_documento"] == 1.0
    assert rel["banda"] == "ALTA"
    assert len([c for c in rel["file_key"] if c.isdigit()]) == 50


def test_spike_nfe_bate_gabarito():
    rel = processar_nfe((FIXDIR / "nfe_exemplo.xml").read_text(encoding="utf-8"))
    assert rel["total_ok"] is True
    assert rel["cnpj_ok"] is True
    assert rel["score_documento"] == 1.0
    assert len([c for c in rel["file_key"] if c.isdigit()]) == 44


def test_spike_detecta_iss_quebrado():
    # adultera o vISSQN -> invariante falha -> score derruba
    xml = (FIXDIR / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")
    xml_quebrado = xml.replace("<vISSQN>50.00</vISSQN>", "<vISSQN>49.00</vISSQN>")
    rel = processar_nfse(xml_quebrado)
    assert rel["iss_ok"] is False
    assert rel["banda"] == "BAIXA"
