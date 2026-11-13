from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TOLERANCIA = Decimal("0.02")  # 2 centavos de folga p/ arredondamento


@dataclass
class Resultado:
    ok: bool
    motivo: str | None = None


def _fecha(esperado: Decimal, obtido: Decimal) -> bool:
    return abs(esperado - obtido) <= TOLERANCIA


def invariante_iss(base: Decimal, aliquota: Decimal, valor: Decimal) -> Resultado:
    esperado = (base * aliquota / Decimal("100"))
    if _fecha(esperado, valor):
        return Resultado(ok=True)
    return Resultado(ok=False, motivo=f"ISS nao fecha: base x aliquota = {esperado:.2f}, declarado {valor:.2f}")


def invariante_liquido_nfse(
    servicos: Decimal, deducoes: Decimal, retencoes: Decimal, liquido: Decimal
) -> Resultado:
    esperado = servicos - deducoes - retencoes
    if _fecha(esperado, liquido):
        return Resultado(ok=True)
    return Resultado(ok=False, motivo=f"Liquido nao fecha: esperado {esperado:.2f}, declarado {liquido:.2f}")


def invariante_total_nfe(
    produtos: Decimal, frete: Decimal, seguro: Decimal, outras: Decimal,
    desconto: Decimal, total: Decimal,
    ipi: Decimal = Decimal("0"), icmsst: Decimal = Decimal("0"),
) -> Resultado:
    esperado = produtos + frete + seguro + outras - desconto + ipi + icmsst
    if _fecha(esperado, total):
        return Resultado(ok=True)
    return Resultado(ok=False, motivo=f"Total NF-e nao fecha: esperado {esperado:.2f}, declarado {total:.2f}")
