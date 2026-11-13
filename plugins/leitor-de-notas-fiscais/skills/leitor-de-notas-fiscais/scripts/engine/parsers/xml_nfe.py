from __future__ import annotations

from engine.model import NFeProduto
from engine.parsers._helpers import _find_text, _local, campo_xml, dec, find_text_em_grupo
from engine.parsers._safe_xml import parse as parse_xml_seguro
from engine.parsers.itens_nfe import agregar_itens


def _vals_local(el, nome: str) -> list[str]:
    """Textos (strip) de todos os descendentes cujo local-name == nome (namespace-aware)."""
    return [x.text.strip() for x in el.iter()
            if _local(x.tag) == nome and x.text and x.text.strip()]


def _esta_cancelada(root) -> bool:
    """Cancelamento HOMOLOGADO no XML NF-e (capture-only). Duas formas validas:

    1) Status da propria nota: cStat em (101, 151) (101 = Cancelamento homologado;
       151 = Cancelamento extemporaneo homologado).
    2) EVENTO de cancelamento homologado: dentro de UM mesmo bloco de evento
       (`procEventoNFe`/`retEvento`), tpEvento == 110111 E cStat == 135 (evento registrado).

    O escopo do (2) ao mesmo bloco e o cStat homologado evitam falso-positivo: tpEvento 110111
    SOZINHO (requisicao que pode estar rejeitada) nao basta; CC-e (110110 + 135) nao dispara;
    cStat 100/107 (autorizado/webservice) nao dispara. Tudo via `_local` (imune a prefixo de ns).
    Se nada disso constar, sai False (cancelamento e evento externo -> o carimbo no PDF cobre).
    """
    if any(c in ("101", "151") for c in _vals_local(root, "cStat")):
        return True
    for ev in root.iter():
        if _local(ev.tag) in ("procEventoNFe", "retEvento"):
            if "110111" in _vals_local(ev, "tpEvento") and "135" in _vals_local(ev, "cStat"):
                return True
    return False


def parse_nfe(xml_str: str) -> NFeProduto:
    """Parser deterministico do leiaute NF-e 55 (namespace .../nfe)."""
    root = parse_xml_seguro(xml_str)
    inf = next((el for el in root.iter() if _local(el.tag) == "infNFe"), root)
    chave = inf.attrib.get("Id")
    agg = agregar_itens(root)
    cancelada = _esta_cancelada(root)

    def _tot(tag: str):
        return dec(find_text_em_grupo(root, ("ICMSTot",), (tag,)))

    return NFeProduto(
        cancelada=cancelada,
        chave_acesso=campo_xml(chave) if chave else None,
        numero=campo_xml(_find_text(root, "nNF")),
        serie=campo_xml(_find_text(root, "serie")),
        natureza_operacao=campo_xml(_find_text(root, "natOp")),
        emitente_cnpj=campo_xml(_find_text(root, "CNPJ")),
        emitente_nome=campo_xml(_find_text(root, "xNome")),
        total_produtos=campo_xml(_tot("vProd")),
        frete=campo_xml(_tot("vFrete")),
        seguro=campo_xml(_tot("vSeg")),
        outras_despesas=campo_xml(_tot("vOutro")),
        desconto=campo_xml(_tot("vDesc")),
        total_nota=campo_xml(_tot("vNF")),
        ipi_total=campo_xml(_tot("vIPI")),
        icmsst_total=campo_xml(_tot("vST")),
        data_emissao=campo_xml(_find_text(root, "dhEmi")),
        qtd_itens=campo_xml(agg["qtd_itens"]),
        cfops_distintos=campo_xml(agg["cfops_distintos"]) if agg["cfops_distintos"] else None,
        tem_desconto_item=campo_xml(agg["tem_desconto_item"]),
        ncm_predominante=campo_xml(agg["ncm_predominante"]) if agg["ncm_predominante"] else None,
        descricao_resumida=campo_xml(agg["descricao_resumida"]) if agg["descricao_resumida"] else None,
    )
