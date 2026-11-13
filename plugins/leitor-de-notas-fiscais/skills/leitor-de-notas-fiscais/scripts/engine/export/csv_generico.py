from __future__ import annotations

import csv
import io
import re

# Ordem das colunas do CSV genérico BR (grão título). Campos "a preencher" incluídos.
COLUNAS = (
    "arquivo_origem", "chave_arquivo", "familia", "tipo_documento",
    "fornecedor_cnpj", "fornecedor_nome", "emitente_endereco", "destinatario_endereco",
    "intermediario_doc", "intermediario_nome",
    "numero", "serie", "data_emissao", "vencimento",
    "valor_total", "valor_recebido", "valor_liquido", "moeda", "valor_origem", "iss_valor", "iss_retido",
    "iss_tipo_retencao", "iss_municipio_incidencia", "iss_recolher_tomador",
    "nota_enderecada_a_voce", "alerta_retencao",
    "ret_irrf", "ret_csll", "ret_pis", "ret_cofins", "ret_inss",
    "ret_inss_base", "ret_inss_aliquota", "ret_federal_total",
    "qtd_itens", "cfops_distintos", "tem_desconto_item", "ncm_predominante", "descricao_resumida",
    "natureza_operacao", "cancelada",
    "natureza", "centro_custo", "status", "confianca_nota", "motivos",
)

_ISO_DATA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _data_br(v) -> str:
    """ISO (2026-03-15T...) -> dd/mm/aaaa. Se não casar, devolve o texto como veio."""
    if not v:
        return ""
    m = _ISO_DATA.match(str(v))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(v)


def _dec_br(v) -> str:
    """Decimal/str '1000.00' -> '1000,00' (vírgula decimal, sem R$ nem milhar)."""
    if v is None or v == "":
        return ""
    return str(v).replace(".", ",")


_DATAS = {"data_emissao", "vencimento"}
# Namespace de COLUNA do CSV (diferente do _DECIMAIS de extracao, que e nome de campo do model):
# tem valor_total/confianca_nota, que nao sao campo de model. Mantido explicito de proposito, MAS
# protegido por tests/test_decimais_fonte_unica.py::test_csv_decimais_nao_diverge_dos_valores_reais
# (toda coluna que recebe um Decimal numa linha real precisa estar aqui).
_DECIMAIS = {"valor_total", "valor_recebido", "valor_liquido", "valor_origem", "iss_valor",
             "ret_irrf", "ret_csll", "ret_pis", "ret_cofins", "ret_inss",
             "ret_inss_base", "ret_inss_aliquota", "ret_federal_total",
             "confianca_nota"}


# copiado de capturador-de-notas/motor/engine/base.py (neutralizar_formula): texto de terceiro nao vira formula no Excel
_GATILHOS_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _neutralizar_formula(v: str) -> str:
    return "'" + v if v[:1] in _GATILHOS_FORMULA else v


def _fmt(coluna: str, valor) -> str:
    if coluna in _DECIMAIS:  # numero: o "-" de valor negativo nao e gatilho
        return _dec_br(valor)
    texto = _data_br(valor) if coluna in _DATAS else ("" if valor is None else str(valor))
    return _neutralizar_formula(texto)


formatar_valor = _fmt  # alias publico (boundary estavel p/ outros modulos)


def exportar_csv(linhas: list[dict], colunas=COLUNAS) -> str:
    """Serializa as linhas em CSV BR (separador ';', UTF-8, sem R$)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(colunas)
    for ln in linhas:
        w.writerow([_fmt(c, ln.get(c)) for c in colunas])
    return buf.getvalue()


def exportar_excecoes(linhas: list[dict]) -> list[dict]:
    """Só as linhas que precisam de conferência (status != auto-aprovada), com motivo PT."""
    return [
        {"arquivo_origem": ln.get("arquivo_origem"), "chave_arquivo": ln.get("chave_arquivo"),
         "confianca_nota": ln.get("confianca_nota"), "motivo": ln.get("motivos") or "confiança abaixo do limiar"}
        for ln in linhas if ln.get("status") != "auto-aprovada"
    ]
