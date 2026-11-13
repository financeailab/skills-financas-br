from __future__ import annotations

from engine.fiscal.lc116 import obriga_retencao_tomador
from engine.model import NFSeServico, TomadorReferencia
from engine.normalizacao import retido_por_tipo


def _digitos(s: str | None) -> str:
    return "".join(ch for ch in s if ch.isdigit()) if s else ""


def _val(campo):
    return campo.valor if (campo is not None and campo.valor is not None) else None


def cruzar_tomador(nf: NFSeServico, ref: TomadorReferencia) -> dict:
    """Cruza a nota com a referencia do tomador (CNPJ + municipio IBGE da nossa empresa).

    Campos None = desconhecido (faltou dado de um dos lados): nunca afirma no escuro.
    """
    nosso_cnpj = _digitos(ref.cnpj)
    nosso_mun = (ref.municipio_ibge or "").strip()

    dest = _digitos(_val(nf.destinatario_doc))
    # endereçamento casa pela RAIZ do CNPJ (8 primeiros dígitos): filial 0002 e a
    # mesma empresa que a matriz 0001. None = falta dado de um dos lados.
    enderecado = (dest[:8] == nosso_cnpj[:8]) if (len(dest) >= 8 and len(nosso_cnpj) >= 8) else None

    inc = (_val(nf.iss_municipio_incidencia) or "").strip()
    incidencia_confere = (inc == nosso_mun) if (inc and nosso_mun) else None

    tipo = _val(nf.iss_tipo_retencao)
    declara_retido = retido_por_tipo(tipo)  # True p/ tomador E intermediario (usado no alerta §2)
    recolhe_tomador = tipo == "retido_tomador"  # SO o tomador recolhe (intermediario = resp. do intermediario)

    if recolhe_tomador and incidencia_confere is False:
        recolhe = False  # tomador retido, mas incidencia em outro municipio (inconsistente)
    else:
        recolhe = recolhe_tomador

    alerta = (
        declara_retido is False
        and incidencia_confere is True
        and obriga_retencao_tomador(_val(nf.codigo_servico))
    )

    motivos = []
    if enderecado is False:
        motivos.append("Nota nao endereçada ao seu CNPJ: confira se a nota e sua")
    if recolhe_tomador and incidencia_confere is False:
        motivos.append("Nota diz ISS retido pelo tomador mas a incidencia e em outro municipio: confira")
    if alerta:
        motivos.append("ISS nao destacado, mas o servico pode obrigar retencao no seu municipio (LC116 §2): confira")
    if recolhe:
        motivos.append("ISS retido pelo tomador: recolher por guia (nao pagar o valor cheio ao fornecedor)")

    return {
        "enderecado_a_nos": enderecado,
        "municipio_incidencia_confere": incidencia_confere,
        "iss_obrigacao_recolhimento_tomador": recolhe,
        "alerta_retencao_nao_destacada": alerta,
        "motivos_tomador": motivos,
    }
