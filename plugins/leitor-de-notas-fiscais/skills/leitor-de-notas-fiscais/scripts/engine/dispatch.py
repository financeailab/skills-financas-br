from __future__ import annotations

from engine.avaliacao import avaliar_nfe, avaliar_nfse
from engine.parsers._helpers import _local, dec
from engine.parsers._safe_xml import parse as parse_xml_seguro
from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.parsers.xml_nfe import parse_nfe
from engine.parsers.xml_sp import parse_nfse_sp
from engine.router import Familia, classificar

_PARSERS = {
    Familia.NFSE_NACIONAL: parse_nfse_nacional,
    Familia.NFSE_ABRASF: parse_nfse_abrasf,
    Familia.NFSE_SP: parse_nfse_sp,
    Familia.NFE: parse_nfe,
}


# Elementos que marcam uma nota em cada familia (o maior total vale: o mesmo elemento pode estar aninhado em outro).
_MARCAS_DE_NOTA = {
    Familia.NFSE_NACIONAL: ("infNFSe",),
    Familia.NFSE_ABRASF: ("CompNfse", "InfNfse", "InfRps", "InfDeclaracaoPrestacaoServico"),
    Familia.NFSE_SP: ("NFe", "ChaveNFe", "ChaveNFeRPS"),
    Familia.NFE: ("NFe",),  # o infNFe tambem aparece no CT-e (infDoc); o NFe so na propria nota
}


def _recusar_envelope_com_varias_notas(fam: Familia, xml_str: str) -> None:
    """Os parsers leem UMA nota por arquivo (o 1o campo achado): envelope com varias perderia as outras em silencio."""
    contagem: dict[str, int] = {}
    for el in parse_xml_seguro(xml_str).iter():
        nome = _local(el.tag)
        contagem[nome] = contagem.get(nome, 0) + 1
    n = max(contagem.get(m, 0) for m in _MARCAS_DE_NOTA[fam])
    if n == 0:  # CT-e, evento ou formato sem a nota: o parser pegaria campos soltos
        raise ValueError("nao achei a nota fiscal no arquivo (CT-e, evento ou outro documento); confira o arquivo")
    if n > 1:
        raise ValueError(f"o arquivo traz {n} notas num envelope so; separe uma nota por arquivo")


_RETENCOES_FEDERAIS_ABRASF = ("ValorIr", "ValorPis", "ValorCofins", "ValorCsll", "ValorInss")
MOTIVO_RETENCAO_FEDERAL = ("Retenções federais (IR, PIS, COFINS, CSLL ou INSS) no XML não são lidas: "
                           "confira o valor líquido na nota")


def marcar_limites_do_xml(fam: Familia, xml_str: str, rel: dict) -> None:
    """O parser ABRASF nao le as retencoes federais: com valor > 0 (ou ilegivel) a nota nao se auto-aprova."""
    if fam != Familia.NFSE_ABRASF:
        return
    for el in parse_xml_seguro(xml_str).iter():
        if _local(el.tag) in _RETENCOES_FEDERAIS_ABRASF and el.text and el.text.strip():
            v = dec(el.text.strip())
            if v is None or v > 0:
                rel["motivos"] = rel["motivos"] + [MOTIVO_RETENCAO_FEDERAL]
                rel["forcar_conferir"] = True
                return


def parsear(xml_str: str):
    """Classifica e parseia -> (Familia, modelo). Retorna (familia, None) se não reconhecida."""
    fam = classificar(xml_str)
    parser = _PARSERS.get(fam)
    if parser:
        _recusar_envelope_com_varias_notas(fam, xml_str)
    return (fam, parser(xml_str)) if parser else (fam, None)


def processar(xml_str: str, tomador_ref=None) -> dict:
    """Roteia o XML para o parser da família certa e avalia. Anota `familia` no relatório.

    `tomador_ref` (opcional) so e repassado ao ramo NFS-e (avaliar_nfe nao usa contexto de tomador).
    """
    fam, modelo = parsear(xml_str)
    if modelo is None:
        return {"familia": fam.value, "erro": "familia nao reconhecida", "banda": "BAIXA"}
    if fam == Familia.NFE:
        rel = avaliar_nfe(modelo)
    else:
        rel = avaliar_nfse(modelo, tomador_ref=tomador_ref)
    rel["familia"] = fam.value
    marcar_limites_do_xml(fam, xml_str, rel)
    return rel
