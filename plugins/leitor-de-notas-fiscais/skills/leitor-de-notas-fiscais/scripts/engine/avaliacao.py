from __future__ import annotations

import re
from decimal import Decimal

from engine.confidence import banda, score_documento
from engine.cruzamento import cruzar_tomador
from engine.documentos import cnpj_dv_valido
from engine.filekey import file_key
from engine.invariants import (
    invariante_iss,
    invariante_liquido_nfse,
    invariante_total_nfe,
)
from engine.model import Fonte, NFeProduto, NFSeServico
from engine.normalizacao import iss_e_retido
from engine.sinais import sinal_cfop_direcao


def _z(c) -> Decimal:
    return c.valor if c and c.valor is not None else Decimal("0")


def _cnpj_ok(campo) -> bool:
    return cnpj_dv_valido(campo.valor) if campo and campo.valor else False


def _score(campo, invariante_ok: bool | None = None, dv_ok: bool | None = None) -> float:
    """Score base = o que o proprio Campo carrega (XML=1.0, PDF=0.7-0.9); invariante/DV so ajustam p/ baixo."""
    base = campo.confianca.score if (campo is not None and campo.confianca is not None) else 0.5
    if invariante_ok is False:
        base = min(base, 0.3)
    if dv_ok is False:
        base = min(base, 0.3)
    return round(base, 2)


def _motivos_ilegiveis(modelo) -> list[str]:
    """Motivos de campos decimais ilegiveis (sinalizados em _campo_pdf) p/ propagar ao relatorio."""
    motivos = []
    for nome in type(modelo).model_fields:
        campo = getattr(modelo, nome, None)
        conf = getattr(campo, "confianca", None) if campo is not None else None
        mot = getattr(conf, "motivo", None) if conf is not None else None
        if mot and "ilegivel" in mot.lower():
            motivos.append(f"{nome}: {mot}")
    return motivos


def _propagar_ilegiveis(relatorio: dict, modelo) -> dict:
    """Se algum campo veio ilegivel, rebaixa o doc (nao auto-aprova) e anexa os motivos."""
    ileg = _motivos_ilegiveis(modelo)
    if ileg:
        relatorio["motivos"] = relatorio["motivos"] + ileg
        relatorio["score_documento"] = min(relatorio["score_documento"], 0.3)
        relatorio["banda"] = banda(relatorio["score_documento"])
    return relatorio


def _partes_reserva(nf) -> dict:
    """Partes da chave de reserva (nota sem chave de acesso): sem elas, toda nota sem chave sairia com a mesma."""
    def v(c):
        return c.valor if c is not None and c.valor is not None else None
    return {"municipio_ibge": v(nf.municipio_ibge), "cnpj_prestador": v(nf.emitente_cnpj),
            "numero": v(nf.numero), "serie": v(nf.serie), "aaaamm": str(v(nf.data_emissao) or "")[:7]}


def avaliar_nfse(nf: NFSeServico, tomador_ref=None, aliquota_opcional: bool = False) -> dict:
    iss = invariante_iss(_z(nf.iss_base), _z(nf.iss_aliquota), _z(nf.iss_valor))
    retido = iss_e_retido(nf.iss_retido.valor if nf.iss_retido else None)
    tipo_ret = nf.iss_tipo_retencao.valor if nf.iss_tipo_retencao else None
    recolhe_tomador = tipo_ret == "retido_tomador"
    retencoes = (
        (_z(nf.iss_valor) if retido else Decimal("0"))
        + _z(nf.ret_irrf)
        + _z(nf.ret_csll)
        + _z(nf.ret_pis)
        + _z(nf.ret_cofins)
        + _z(nf.ret_inss)
    )
    cnpj_ok = _cnpj_ok(nf.emitente_cnpj)
    s_cnpj = _score(nf.emitente_cnpj, dv_ok=cnpj_ok)

    # ISS ausente no Simples Nacional = recolhido no DAS (nao destacado): nao penaliza.
    # ISS ausente fora do Simples = suspeito (penaliza 0.5). ISS presente = score normal.
    tem_iss = nf.iss_valor is not None and nf.iss_valor.valor is not None
    scores = [s_cnpj]
    # Sem valor de servico legivel nao ha o que lancar: nao auto-aprova (ISS ausente no Simples nao dispensa o valor).
    tem_valor = nf.valor_servicos is not None and nf.valor_servicos.valor is not None
    scores.append(_score(nf.valor_servicos) if tem_valor else 0.3)
    # NFS-e nacional sem pAliqAplic no XML: o ISS nao e conferivel (informativo, nao rebaixa).
    aliq_ausente = tem_iss and aliquota_opcional and (nf.iss_aliquota is None or nf.iss_aliquota.valor is None)
    if tem_iss:
        # Simples Nacional: ISS e informativo (recolhido no DAS) -> nao valida a invariante.
        inv_iss = None if (nf.simples_nacional or nf.iss_nao_exigivel or aliq_ausente) else iss.ok
        scores.append(_score(nf.iss_valor, invariante_ok=inv_iss))
    elif not (nf.simples_nacional or nf.iss_nao_exigivel):
        scores.append(0.5)

    tem_liquido = nf.valor_liquido is not None and nf.valor_liquido.valor is not None
    if tem_liquido:
        liq = invariante_liquido_nfse(_z(nf.valor_servicos), _z(nf.deducoes), retencoes, _z(nf.valor_liquido))
        liquido_ok = liq.ok
        liq_motivo = liq.motivo
        scores.append(_score(nf.valor_liquido, invariante_ok=liq.ok))
    else:
        liquido_ok = None
        liq_motivo = None
    doc = score_documento(scores)

    chave_arq = file_key(nf.chave_acesso.valor if nf.chave_acesso else None, "NFSe", **_partes_reserva(nf))
    # Simples (ou ISS nao exigivel): ISS informativo -> nao emite o motivo de ISS-nao-fecha (seria falso-erro).
    iss_motivo = None if (nf.simples_nacional or nf.iss_nao_exigivel or aliq_ausente) else iss.motivo
    motivos = [m for m in (iss_motivo, liq_motivo) if m]
    if not tem_valor:
        motivos.append("Valor do servico ausente ou ilegivel: conferir")
    if aliq_ausente and not (nf.simples_nacional or nf.iss_nao_exigivel):  # Simples ja explica o ISS
        motivos.append("Aliquota de ISS nao veio no XML: ISS nao conferido")
    if nf.simples_nacional:
        motivos.append("Simples Nacional: ISS recolhido no DAS (nao destacado na nota)")
    if nf.iss_nao_exigivel and not nf.simples_nacional:
        motivos.append("ISS nao exigivel (imunidade/nao-incidencia/exportacao): nao destacado por direito")
    # Nota CANCELADA: capture-only -> nunca auto-aprova, mas NAO rebaixa o score/banda.
    # Escopo do sinal de NFS-e: vem do CARIMBO no PDF (meta `cancelada`). O XML de NFS-e dos
    # layouts suportados (nacional/ABRASF/SP) NAO carrega status de cancelamento inline -- o
    # cancelamento de NFS-e e evento na prefeitura, fora do XML da nota -> o carimbo no PDF cobre.
    forcar_conferir = False
    if getattr(nf, "cancelada", False):
        motivos.append("Nota CANCELADA: nao pagar / nao lancar")
        forcar_conferir = True
    relatorio = {
        "iss_ok": None if aliq_ausente else iss.ok, "liquido_ok": liquido_ok, "cnpj_ok": cnpj_ok,
        "score_documento": doc, "banda": banda(doc), "file_key": chave_arq,
        "iss_obrigacao_recolhimento_tomador": recolhe_tomador,
        "motivos": motivos,
        "forcar_conferir": forcar_conferir,
    }
    if tomador_ref is not None:
        cz = cruzar_tomador(nf, tomador_ref)
        relatorio["iss_obrigacao_recolhimento_tomador"] = cz["iss_obrigacao_recolhimento_tomador"]
        relatorio["enderecado_a_nos"] = cz["enderecado_a_nos"]
        relatorio["municipio_incidencia_confere"] = cz["municipio_incidencia_confere"]
        relatorio["alerta_retencao_nao_destacada"] = cz["alerta_retencao_nao_destacada"]
        relatorio["motivos"] = motivos + cz["motivos_tomador"]
        # Alerta §2 (retencao nao destacada) = risco fiscal real (voce pode dever o ISS): rebaixa pra conferir,
        # p/ cair nas excecoes (decisao owner 2026-06-24). Inconsistencia/recolhimento NAO setam esse flag -> intactos.
        # So rebaixa se a nota e NOSSA ou desconhecida (enderecado_a_nos is not False): o risco §2 (dever o ISS)
        # so e nosso quando a nota e nossa; nota comprovadamente de outro CNPJ nao deve ser rebaixada por §2.
        if (
            relatorio.get("alerta_retencao_nao_destacada")
            and relatorio.get("enderecado_a_nos") is not False
        ):
            relatorio["score_documento"] = min(relatorio["score_documento"], 0.3)
            relatorio["banda"] = banda(relatorio["score_documento"])
    elif recolhe_tomador:
        relatorio["motivos"] = motivos + [
            "ISS retido pelo tomador: recolher por guia (nao pagar o valor cheio ao fornecedor)"
        ]
    return _propagar_ilegiveis(relatorio, nf)


def avaliar_nfe(nf: NFeProduto) -> dict:
    cnpj_ok = _cnpj_ok(nf.emitente_cnpj)
    s_cnpj = _score(nf.emitente_cnpj, dv_ok=cnpj_ok)
    motivos = []
    tem_total = nf.total_nota is not None and nf.total_nota.valor is not None
    if not tem_total:
        # NF-e sem bloco de total (ICMSTot/vNF): incompleta -> nao auto-aprovar (achado P2 Codex)
        motivos.append("NF-e sem bloco de total (ICMSTot/vNF): nota incompleta, conferir")
        total_ok = False
        s_tot = 0.3
    else:
        tot = invariante_total_nfe(
            _z(nf.total_produtos), _z(nf.frete), _z(nf.seguro), _z(nf.outras_despesas),
            _z(nf.desconto), _z(nf.total_nota), _z(nf.ipi_total), _z(nf.icmsst_total),
        )
        total_ok = tot.ok
        s_tot = _score(nf.total_nota, invariante_ok=tot.ok)
        if tot.motivo:
            motivos.append(tot.motivo)
    doc = score_documento([s_tot, s_cnpj])

    chave_arq = file_key(nf.chave_acesso.valor if nf.chave_acesso else None, "NFe", **_partes_reserva(nf))
    sinal = sinal_cfop_direcao(nf.cfops_distintos.valor if nf.cfops_distintos else None)
    forcar_conferir = False
    if sinal:
        motivos.append(sinal)
        forcar_conferir = True
    # Natureza da operacao (natOp) = SINAL de sentido. Capture-only: sinaliza p/ conferir, NAO inverte
    # valor nem mexe no score/banda (uma devolucao com total que fecha continua ALTA).
    nat = nf.natureza_operacao.valor if nf.natureza_operacao else None
    if nat and re.search(r"devolu|retorno|remessa", nat, re.I):
        motivos.append(
            "Operacao de devolucao/retorno: o valor pode ser credito (nao debito), confira o sentido"
        )
        forcar_conferir = True
    # Nota CANCELADA (carimbo): capture-only -> nunca auto-aprova, mas NAO rebaixa o score/banda.
    if getattr(nf, "cancelada", False):
        motivos.append("Nota CANCELADA: nao pagar / nao lancar")
        forcar_conferir = True
    relatorio = {
        "total_ok": total_ok, "cnpj_ok": cnpj_ok,
        "score_documento": doc, "banda": banda(doc), "file_key": chave_arq,
        "motivos": motivos,
        "forcar_conferir": forcar_conferir,
    }
    return _propagar_ilegiveis(relatorio, nf)
