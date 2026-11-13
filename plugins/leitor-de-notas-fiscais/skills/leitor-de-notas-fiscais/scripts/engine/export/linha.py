from __future__ import annotations

from engine.model import NFeProduto, NFSeServico

# Campos exigidos pelo arquivo de carga (AP) que NÃO vêm da nota (vêm da condição de
# pagamento) — entram sinalizados "a preencher" (§17.3), nunca inventados.
_A_PREENCHER = ("vencimento", "natureza", "centro_custo")


def _v(campo):
    return campo.valor if (campo is not None and campo.valor is not None) else None


def montar_linha(modelo, relatorio: dict, arquivo_origem: str) -> dict:
    """Converte (modelo canônico + relatório de avaliação) numa linha de carga (grão título)."""
    linha = {
        "arquivo_origem": arquivo_origem,
        "chave_arquivo": relatorio.get("file_key"),
        "familia": relatorio.get("familia"),
        "fornecedor_cnpj": _v(modelo.emitente_cnpj),
        "fornecedor_nome": _v(modelo.emitente_nome),
        "numero": _v(modelo.numero),
        "serie": _v(modelo.serie),
        "data_emissao": _v(modelo.data_emissao),
    }
    if isinstance(modelo, NFSeServico):
        linha["valor_total"] = _v(modelo.valor_servicos)
        linha["valor_liquido"] = _v(modelo.valor_liquido)
        linha["iss_valor"] = _v(modelo.iss_valor)
        _ret = _v(modelo.iss_retido)
        linha["iss_retido"] = "Sim" if _ret == "true" else ("Não" if _ret is not None else None)
        linha["iss_tipo_retencao"] = _v(modelo.iss_tipo_retencao)
        linha["iss_municipio_incidencia"] = _v(modelo.iss_municipio_incidencia)
        for c in ("qtd_itens", "cfops_distintos", "tem_desconto_item", "ncm_predominante", "descricao_resumida"):
            linha[c] = None
    elif isinstance(modelo, NFeProduto):
        linha["valor_total"] = _v(modelo.total_nota)
        # NF-e nao tem vLiq no XML; usa o total da nota (retencoes federais nao sao extraidas hoje)
        linha["valor_liquido"] = _v(modelo.total_nota)
        linha["iss_valor"] = None
        linha["iss_retido"] = None
        linha["iss_tipo_retencao"] = None
        linha["iss_municipio_incidencia"] = None
        linha["qtd_itens"] = _v(modelo.qtd_itens)
        linha["cfops_distintos"] = _v(modelo.cfops_distintos)
        _td = _v(modelo.tem_desconto_item)
        linha["tem_desconto_item"] = "Sim" if _td else ("Não" if _td is not None else None)
        linha["ncm_predominante"] = _v(modelo.ncm_predominante)
        linha["descricao_resumida"] = _v(modelo.descricao_resumida)
    else:  # descope v1: so NFS-e/NF-e chegam aqui (batch rejeita o resto antes)
        raise ValueError(f"modelo fora do escopo do leitor (so NFS-e/NF-e): {type(modelo).__name__}")
    linha["ret_federal_total"] = _v(modelo.ret_federal_total)
    linha["iss_recolher_tomador"] = "Sim" if relatorio.get("iss_obrigacao_recolhimento_tomador") else "Não"
    linha["ret_irrf"] = _v(modelo.ret_irrf)
    linha["ret_csll"] = _v(modelo.ret_csll)
    linha["ret_pis"] = _v(modelo.ret_pis)
    linha["ret_cofins"] = _v(modelo.ret_cofins)
    linha["ret_inss"] = _v(modelo.ret_inss)
    _end = relatorio.get("enderecado_a_nos")
    linha["nota_enderecada_a_voce"] = "Sim" if _end is True else ("Não" if _end is False else "")
    linha["alerta_retencao"] = "Sim" if relatorio.get("alerta_retencao_nao_destacada") else ""
    linha["natureza_operacao"] = _v(getattr(modelo, "natureza_operacao", None))
    linha["cancelada"] = "Sim" if getattr(modelo, "cancelada", False) else ""
    linha["confianca_nota"] = relatorio.get("score_documento")
    linha["status"] = (
        "auto-aprovada"
        if relatorio.get("banda") == "ALTA" and not relatorio.get("forcar_conferir")
        else "conferir"
    )
    linha["motivos"] = "; ".join(relatorio.get("motivos", []))
    for c in _A_PREENCHER:
        linha[c] = ""  # a preencher (não vem da nota)
    # natureza_operacao capturada (NF-e) surfa no campo `natureza` que o ERP lê como Categoria
    # (perfis omie/contaazul); senão `natureza` segue "" (a preencher). O usuário pode sobrescrever.
    _nat_op = _v(getattr(modelo, "natureza_operacao", None))
    if _nat_op:
        linha["natureza"] = _nat_op
    linha["tipo_documento"] = getattr(modelo, "tipo_documento", None) or relatorio.get("tipo_documento")
    _venc = getattr(modelo, "vencimento", None)
    if _venc is not None and _venc.valor:
        linha["vencimento"] = _venc.valor   # NFS-e/NF-e trazem vencimento real (Fatura/Duplicata)
    linha.setdefault("moeda", None)
    linha.setdefault("valor_origem", None)
    # campos de paridade (getattr seguro: NF-e nao tem intermediario/valor_recebido)
    for _campo in ("emitente_endereco", "destinatario_endereco", "ret_inss_base", "ret_inss_aliquota"):
        _v_ = getattr(modelo, _campo, None)
        linha[_campo] = _v_.valor if (_v_ is not None and _v_.valor is not None) else None
    for _campo in ("intermediario_doc", "intermediario_nome", "valor_recebido"):
        _v_ = getattr(modelo, _campo, None)
        linha[_campo] = _v_.valor if (_v_ is not None and _v_.valor is not None) else None
    return linha
