from decimal import Decimal
from pathlib import Path

from engine.avaliacao import avaliar_nfse
from engine.dispatch import parsear
from engine.export.csv_generico import COLUNAS, _data_br, _dec_br, exportar_csv, exportar_excecoes
from engine.export.linha import montar_linha
from engine.export.perfis import exportar_perfil

FIX = Path(__file__).parent / "fixtures"


def _linha_nacional():
    xml = (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")
    fam, m = parsear(xml)
    return montar_linha(m, {**avaliar_nfse(m), "familia": fam.value}, "nota1.xml")


def test_formatacao_br():
    assert _data_br("2026-03-15T09:55:00-03:00") == "15/03/2026"
    assert _dec_br(Decimal("1000.00")) == "1000,00"
    assert _dec_br(None) == ""


def test_linha_de_carga_campos():
    ln = _linha_nacional()
    assert ln["fornecedor_cnpj"] == "11222333000181"
    assert ln["arquivo_origem"] == "nota1.xml"
    assert ln["status"] == "auto-aprovada"          # nacional fecha tudo -> ALTA
    assert ln["vencimento"] == ""                     # a preencher (não vem da nota)
    assert ln["natureza"] == "" and ln["centro_custo"] == ""


def test_csv_generico_formato():
    csv_str = exportar_csv([_linha_nacional()])
    linhas = csv_str.splitlines()
    assert linhas[0] == ";".join(COLUNAS)             # cabeçalho
    assert "15/03/2026" in linhas[1]                  # data BR
    assert "11222333000181" in linhas[1]


def test_perfil_omie():
    csv_str = exportar_perfil([_linha_nacional()], "omie")
    assert csv_str.splitlines()[0].startswith("Razão Social;CNPJ/CPF;")


def test_excecoes_so_pega_conferir():
    ln = _linha_nacional()           # auto-aprovada -> não vira exceção
    assert exportar_excecoes([ln]) == []
    ln["status"] = "conferir"
    assert len(exportar_excecoes([ln])) == 1
