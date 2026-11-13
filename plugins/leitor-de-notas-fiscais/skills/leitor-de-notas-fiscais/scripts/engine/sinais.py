from __future__ import annotations

# Direção pela 1a casa do CFOP. Entrada (compra/retorno/devolução p/ nós): 1/2/3.
# Saída (venda/remessa do fornecedor): 5/6/7. Misturar as duas na MESMA nota é anômalo
# numa nota de fornecedor (AP) e pede conferência. É um sinal, não uma invariante aritmética.
_ENTRADA = {"1", "2", "3"}
_SAIDA = {"5", "6", "7"}


def sinal_cfop_direcao(cfops_distintos: str | None) -> str | None:
    """Recebe a string ", "-joined de cfops_distintos (ex.: "1102, 5102").
    Retorna um motivo em PT se a nota tem CFOP de entrada E de saída; senão None.
    Não mexe em score financeiro (CFOP não é campo financeiro)."""
    if not cfops_distintos:
        return None
    primeiras = {c.strip()[0] for c in cfops_distintos.split(",") if c.strip()}
    tem_entrada = bool(primeiras & _ENTRADA)
    tem_saida = bool(primeiras & _SAIDA)
    if tem_entrada and tem_saida:
        return "CFOPs de direções diferentes (entrada e saída) na mesma nota: confira"
    return None
