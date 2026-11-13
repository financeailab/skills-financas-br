"""Achado 8 do Gate 2: o guia de extracao de PDF diz o que o motor aceita para o total da NF-e."""
from __future__ import annotations

from pathlib import Path

from engine.model import NFeProduto

from tests.layout import PLUGIN, SCRIPTS

# publico: scripts/ler-nfse/; monorepo: motor/skills/ler-nfse/
_GUIAS = (Path(SCRIPTS) / "ler-nfse" / "extrair-pdf.md", Path(PLUGIN) / "skills" / "ler-nfse" / "extrair-pdf.md")
GUIA = next(p for p in _GUIAS if p.exists()).read_text(encoding="utf-8")
PARCELAS = ("frete", "seguro", "desconto", "outras_despesas", "ipi_total", "icmsst_total")


def test_guia_pede_as_parcelas_do_total_que_o_motor_soma():
    for c in PARCELAS:
        assert c in NFeProduto.model_fields  # o guia so pode pedir o que o motor le
        assert f"`{c}`" in GUIA, c


def test_guia_nao_diz_que_ipi_e_st_ficam_fora_do_total():
    assert "não** entram no total" not in GUIA and "NÃO soma IPI" not in GUIA
