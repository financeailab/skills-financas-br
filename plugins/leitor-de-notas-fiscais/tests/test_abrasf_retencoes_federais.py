"""Achado 5 do Gate 2: o parser ABRASF (congelado) nao le IR/PIS/COFINS/CSLL/INSS retidos; a nota com retencao federal vai para conferir."""
from __future__ import annotations

import pytest

from engine.batch import processar_lote
from engine.dispatch import MOTIVO_RETENCAO_FEDERAL, processar


def _abrasf(extra="", liq=None):
    liqx = f"<ValorLiquidoNfse>{liq}</ValorLiquidoNfse>" if liq is not None else ""
    return (
        '<ConsultarNfseResposta xmlns="http://www.abrasf.org.br/nfse.xsd"><ListaNfse><CompNfse><Nfse><InfNfse>'
        "<Numero>10</Numero><DataEmissao>2026-03-10T10:00:00</DataEmissao><Servico><Valores>"
        f"<ValorServicos>1000.00</ValorServicos>{extra}<IssRetido>1</IssRetido><ValorIss>50.00</ValorIss>"
        f"<BaseCalculo>1000.00</BaseCalculo><Aliquota>0.05</Aliquota>{liqx}</Valores>"
        "<ItemListaServico>0101</ItemListaServico></Servico><PrestadorServico><IdentificacaoPrestador>"
        "<Cnpj>11222333000181</Cnpj></IdentificacaoPrestador><RazaoSocial>Exemplo Servicos LTDA</RazaoSocial></PrestadorServico>"
        "</InfNfse></Nfse></CompNfse></ListaNfse></ConsultarNfseResposta>"
    )


def _linha(xml):
    return processar_lote([("n.xml", xml)])["linhas"][0]


def test_5a_com_liquido_declarado_e_retencao_federal_vai_para_conferir():
    ln = _linha(_abrasf("<ValorIr>15.00</ValorIr>", liq="935.00"))
    assert ln["status"] == "conferir" and MOTIVO_RETENCAO_FEDERAL in ln["motivos"]


def test_5b_sem_liquido_declarado_e_retencao_federal_nao_se_auto_aprova():
    ln = _linha(_abrasf("<ValorIr>15.00</ValorIr>"))
    assert ln["status"] == "conferir" and MOTIVO_RETENCAO_FEDERAL in ln["motivos"]


@pytest.mark.parametrize("tag", ["ValorIr", "ValorPis", "ValorCofins", "ValorCsll", "ValorInss"])
def test_5c_qualquer_das_cinco_retencoes_dispara(tag):
    assert _linha(_abrasf(f"<{tag}>1.00</{tag}>"))["status"] == "conferir"


def test_5d_sem_retencao_federal_segue_auto_aprovada():
    ln = _linha(_abrasf(liq="950.00"))
    assert ln["status"] == "auto-aprovada" and MOTIVO_RETENCAO_FEDERAL not in ln["motivos"]


def test_valor_zero_nao_dispara():
    extra = "".join(f"<{t}>0.00</{t}>" for t in ("ValorIr", "ValorPis", "ValorCofins", "ValorCsll", "ValorInss"))
    assert _linha(_abrasf(extra, liq="950.00"))["status"] == "auto-aprovada"


def test_valor_ilegivel_dispara_na_duvida():
    assert _linha(_abrasf("<ValorIr>abc</ValorIr>"))["status"] == "conferir"


def test_processar_unitario_tambem_marca():
    rel = processar(_abrasf("<ValorInss>10.00</ValorInss>"))
    assert rel["forcar_conferir"] is True and MOTIVO_RETENCAO_FEDERAL in rel["motivos"]
