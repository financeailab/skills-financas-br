"""Fixtures sinteticas (dados ficticios) dos 3 cenarios do cruzamento do tomador (o fosso).
Exercitam recolhimento qualificado, alerta LC116 §2 e inconsistencia de municipio."""

NOSSO_CNPJ = "11444777000161"
NOSSO_MUN = "3550308"   # Sao Paulo (IBGE)
OUTRO_MUN = "3304557"   # Rio de Janeiro (IBGE)


def _nfse(tipo, mun, cod, valor="10000.00", iss="500.00"):
    return {"classe": "nfse", "campos": {
        "emitente_cnpj": {"valor": "11222333000181", "rotulo_exato": True},
        "emitente_nome": {"valor": "Fornecedor Servicos Ltda", "rotulo_exato": True},
        "valor_servicos": {"valor": valor, "rotulo_exato": True},
        "iss_base": {"valor": valor, "rotulo_exato": True},
        "iss_aliquota": {"valor": "5.00", "rotulo_exato": True},
        "iss_valor": {"valor": iss, "rotulo_exato": True},
        "iss_tipo_retencao": {"valor": tipo, "rotulo_exato": True},
        "iss_municipio_incidencia": {"valor": mun, "rotulo_exato": True},
        "codigo_servico": {"valor": cod, "rotulo_exato": True},
        "destinatario_doc": {"valor": NOSSO_CNPJ, "rotulo_exato": True}}}


# (a) retido pelo tomador, incidencia no nosso municipio -> recolhe por guia (auto-aprovada + motivo)
CRUZ_RETIDO_NOSSO = {"arquivo": "cruz-a-retido-nosso.pdf", "extracao": _nfse("retido_tomador", NOSSO_MUN, "0101")}
# (b) nao retido, servico LC116 §2 (0702 construcao civil), incidencia no nosso municipio -> alerta -> conferir
CRUZ_ALERTA_P2 = {"arquivo": "cruz-b-alerta-p2.pdf", "extracao": _nfse("nao_retido", NOSSO_MUN, "0702")}
# (c) retido pelo tomador, mas incidencia em OUTRO municipio -> inconsistencia (auto-aprovada + motivo)
CRUZ_INCONSISTENTE = {"arquivo": "cruz-c-inconsistente.pdf", "extracao": _nfse("retido_tomador", OUTRO_MUN, "0101")}

FIXTURES_CRUZAMENTO = [CRUZ_RETIDO_NOSSO, CRUZ_ALERTA_P2, CRUZ_INCONSISTENTE]
