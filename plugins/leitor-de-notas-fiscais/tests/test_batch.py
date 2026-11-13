import io
import zipfile
from pathlib import Path

from engine.batch import CAP_LOTE, processar_zip

FIX = Path(__file__).parent / "fixtures"
_NOTAS = ["nfse_nacional_exemplo.xml", "nfse_abrasf_exemplo.xml", "nfse_sp_exemplo.xml", "nfe_exemplo.xml"]


def _zip(nomes):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i, f in enumerate(nomes):
            z.writestr(f"nota_{i}.xml", (FIX / f).read_text(encoding="utf-8"))
    return buf.getvalue()


def test_lote_processa_as_4_familias():
    r = processar_zip(_zip(_NOTAS), "generico")
    assert r["resumo"]["total"] == 4
    assert set(r["resumo"]["por_familia"]) == {"nfse_nacional", "nfse_abrasf", "nfse_sp", "nfe"}
    assert r["resumo"]["falhou"] == 0
    # CSV: cabeçalho + 4 linhas
    assert len(r["csv"].splitlines()) == 5


def test_lote_nota_invalida_vira_excecao_nao_derruba():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ok.xml", (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8"))
        z.writestr("lixo.xml", "<x/>")
    r = processar_zip(buf.getvalue(), "generico")
    assert r["resumo"]["total"] == 1
    assert r["resumo"]["falhou"] == 1
    assert any("não reconhecida" in e["motivo"] for e in r["excecoes"])


def test_cap_de_lote():
    assert CAP_LOTE == 50
    r = processar_zip(_zip(_NOTAS), "generico")
    assert r["resumo"]["fora_do_limite"] == 0


def test_cap_trunca_e_sinaliza():
    from engine.batch import processar_lote
    xml = (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")
    arquivos = [(f"nota_{i}.xml", xml.replace("01234567890123456789012345678901234567890123456789", f"{i:050d}")) for i in range(55)]
    r = processar_lote(arquivos, "generico")
    assert r["resumo"]["total"] == 50         # cap aplicado
    assert r["resumo"]["fora_do_limite"] == 5
    assert r["resumo"]["recebidas"] == 55
