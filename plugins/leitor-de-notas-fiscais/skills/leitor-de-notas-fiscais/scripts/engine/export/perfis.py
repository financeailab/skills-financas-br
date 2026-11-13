from __future__ import annotations

import csv
import io

from engine.export.csv_generico import COLUNAS, formatar_valor

# Cada perfil: lista de (cabeçalho do ERP, campo canônico da linha). Campo None = coluna vazia (a preencher no ERP).
PERFIS: dict[str, list[tuple[str, str | None]]] = {
    "generico": [(c, c) for c in COLUNAS],
    "omie": [
        ("Razão Social", "fornecedor_nome"),
        ("CNPJ/CPF", "fornecedor_cnpj"),
        ("Número Documento", "numero"),
        ("Data de Vencimento", "vencimento"),
        ("Valor", "valor_total"),
        ("Categoria", "natureza"),
        ("Conta Corrente", None),
        ("Observação", "motivos"),
    ],
    "contaazul": [
        ("Descrição", "fornecedor_nome"),
        ("Valor", "valor_total"),
        ("Data de competência", "data_emissao"),
        ("Data de vencimento", "vencimento"),
        ("Categoria", "natureza"),
        ("Cliente/Fornecedor", "fornecedor_cnpj"),
        ("Observações", "motivos"),
    ],
}


def exportar_perfil(linhas: list[dict], perfil: str = "generico") -> str:
    """Gera o CSV no layout de colunas do ERP escolhido."""
    mapa = PERFIS.get(perfil, PERFIS["generico"])
    cabecalhos = [titulo for titulo, _campo in mapa]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(cabecalhos)
    for ln in linhas:
        w.writerow([formatar_valor(campo, ln.get(campo)) if campo else "" for _titulo, campo in mapa])
    return buf.getvalue()
