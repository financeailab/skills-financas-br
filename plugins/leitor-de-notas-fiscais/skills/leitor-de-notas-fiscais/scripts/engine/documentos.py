from __future__ import annotations


def _digitos(s: str) -> list[int]:
    return [int(c) for c in s if c.isdigit()]


def _dv(nums: list[int], pesos: list[int]) -> int:
    s = sum(d * p for d, p in zip(nums, pesos))
    r = s % 11
    return 0 if r < 2 else 11 - r


def cnpj_dv_valido(cnpj: str) -> bool:
    n = _digitos(cnpj)
    if len(n) != 14 or len(set(n)) == 1:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = _dv(n[:12], p1)
    dv2 = _dv(n[:12] + [dv1], p2)
    return dv1 == n[12] and dv2 == n[13]


def cpf_dv_valido(cpf: str) -> bool:
    n = _digitos(cpf)
    if len(n) != 11 or len(set(n)) == 1:
        return False
    dv1 = _dv(n[:9], list(range(10, 1, -1)))
    dv2 = _dv(n[:9] + [dv1], list(range(11, 1, -1)))
    return dv1 == n[9] and dv2 == n[10]
