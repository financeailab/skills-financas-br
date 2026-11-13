"""Achado 2 do Gate 2: envelope com mais de uma nota no mesmo arquivo vai para as excecoes, nunca vira so a 1a nota."""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.batch import processar_lote
from engine.dispatch import parsear

FIX = Path(__file__).parent / "fixtures"
NFE = (FIX / "nfe_exemplo.xml").read_text(encoding="utf-8")
ABR = (FIX / "nfse_abrasf_exemplo.xml").read_text(encoding="utf-8")
SP = (FIX / "nfse_sp_exemplo.xml").read_text(encoding="utf-8")
NAC = (FIX / "nfse_nacional_exemplo.xml").read_text(encoding="utf-8")


def _comp(num):
    return (f"<CompNfse><Nfse><InfNfse><Numero>{num}</Numero><Servico><Valores><ValorServicos>100.00</ValorServicos>"
            "</Valores></Servico></InfNfse></Nfse></CompNfse>")


def _abrasf(*comps):
    return ('<ConsultarNfseResposta xmlns="http://www.abrasf.org.br/nfse.xsd"><ListaNfse>'
            + "".join(comps) + "</ListaNfse></ConsultarNfseResposta>")


def _nfe(nnf):
    return (f'<NFe><infNFe Id="NFe{str(nnf) * 44}"><ide><nNF>{nnf}</nNF></ide></infNFe></NFe>')


def _sp(n):
    return (f"<NFe><ChaveNFe><NumeroNFe>{n}</NumeroNFe></ChaveNFe><ValorServicos>10.00</ValorServicos></NFe>")


def _nac(n):
    return f'<infNFSe Id="NFS{str(n) * 50}"><nNFSe>{n}</nNFSe></infNFSe>'


DOIS = {
    "abrasf": _abrasf(_comp(10), _comp(11)),
    "nfe": '<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe">' + _nfe(1) + _nfe(2) + "</enviNFe>",
    "sp": '<RetornoConsulta xmlns="http://www.prefeitura.sp.gov.br/nfe">' + _sp(1) + _sp(2) + "</RetornoConsulta>",
    "nacional": '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">' + _nac(1) + _nac(2) + "</NFSe>",
}


@pytest.mark.parametrize("familia", sorted(DOIS))
def test_envelope_com_duas_notas_vira_excecao_com_motivo_claro(familia):
    with pytest.raises(ValueError, match="2 notas"):
        parsear(DOIS[familia])
    r = processar_lote([("env.xml", DOIS[familia])])
    assert r["resumo"]["total"] == 0 and r["resumo"]["falhou"] == 1 and r["linhas"] == []
    motivo = r["excecoes"][0]["motivo"]
    assert "2 notas" in motivo and "uma nota por arquivo" in motivo


@pytest.mark.parametrize("xml", [NFE, ABR, SP, NAC], ids=["nfe", "abrasf", "sp", "nacional"])
def test_arquivo_de_uma_nota_segue_normal(xml):
    fam, modelo = parsear(xml)
    assert modelo is not None


def test_envelope_com_uma_nota_so_segue_normal():
    fam, modelo = parsear(_abrasf(_comp(10)))
    assert modelo is not None and modelo.numero.valor == "10"


def _rps2(num):  # ABRASF 2.x: o RPS traz InfDeclaracaoPrestacaoServico, com um Rps aninhado (IdentificacaoRps)
    return ("<Rps><InfDeclaracaoPrestacaoServico><Rps><IdentificacaoRps><Numero>" + str(num) + "</Numero>"
            "</IdentificacaoRps></Rps><Servico><Valores><ValorServicos>100.00</ValorServicos></Valores></Servico>"
            "</InfDeclaracaoPrestacaoServico></Rps>")


def _lote_rps2(*rps):
    return ('<EnviarLoteRpsEnvio xmlns="http://www.abrasf.org.br/nfse.xsd"><LoteRps><ListaRps>'
            + "".join(rps) + "</ListaRps></LoteRps></EnviarLoteRpsEnvio>")


def test_lote_rps_abrasf_2_com_duas_notas_vira_excecao():
    res = processar_lote([("lote.xml", _lote_rps2(_rps2(1), _rps2(2)).encode("utf-8"))])
    assert res["resumo"]["total"] == 0 and res["linhas"] == []
    assert "2 notas" in res["excecoes"][0]["motivo"]


def test_rps_abrasf_2_unico_com_rps_aninhado_segue_normal():
    res = processar_lote([("rps.xml", _lote_rps2(_rps2(1)).encode("utf-8"))])
    assert not any("envelope" in e["motivo"] or "nao achei" in e["motivo"] for e in res["excecoes"])


SEM_NOTA = {
    # CT-e cita as NF-e transportadas em infDoc/infNFe: o roteador o manda para a familia NF-e pela ancora
    "cte": ('<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte><infCTeNorm><infDoc>'
            "<infNFe><chave>" + "1" * 44 + "</chave></infNFe><infNFe><chave>" + "2" * 44 + "</chave></infNFe>"
            "</infDoc></infCTeNorm></infCte></CTe></cteProc>"),
    "evento": ('<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"><evento><infEvento>'
               "<tpEvento>110111</tpEvento></infEvento></evento></procEventoNFe>"),
}


@pytest.mark.parametrize("tipo", sorted(SEM_NOTA))
def test_xml_sem_a_nota_fiscal_vira_excecao_e_nao_linha(tipo):
    res = processar_lote([(tipo + ".xml", SEM_NOTA[tipo].encode("utf-8"))])
    assert res["resumo"]["total"] == 0 and res["linhas"] == []
    assert "nao achei a nota fiscal" in res["excecoes"][0]["motivo"]
