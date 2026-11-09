# -*- coding: utf-8 -*-
"""Controle AGREGADO de lote (SISPAG sem nº de remessa).

Quando o banco tem débitos de lote (SISPAG) que não casam por falta da remessa no razão,
o motor entrega uma FIGURA DE CONTROLE: total dos débitos de lote × total dos títulos de
saída pendentes + a diferença. Não pareia linha-a-linha (seria falso-positivo); dá à
analista o "bate no agregado?" e aponta a remessa p/ o detalhe. Só somas → seguro p/ a IA.

Rodar:  python tests/test_controle_lote.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
sys.path.insert(0, ENGINE)

from reconcile import match_banco, resumo_privado          # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _raz(d, v, nome=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "identificador": None,
            "contraparte": nome, "cpf_cnpj": None, "descricao": nome, "lote": None}


def _ext(d, v, desc=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "descricao": desc,
            "contraparte": desc, "cpf_cnpj": None, "identificador": None}


D = date(2026, 3, 16)


@caso("controle de lote agrega debitos SISPAG vs titulos de saida pendentes")
def _():
    ext = [_ext(D, "-5000.00", "SISPAG FORNECEDORES")]
    raz = [_raz(D, "-3000.00", "ALFA"), _raz(D, "-1800.00", "BETA")]
    c = match_banco(ext, raz)
    cl = resumo_privado(c)["controle_lote"]
    assert cl is not None, "esperava controle_lote"
    assert cl["qtd_debitos_lote"] == 1, cl
    assert cl["total_debitos_lote"] == "-5000.00", cl
    assert cl["qtd_titulos_pendentes"] == 2, cl
    assert cl["total_titulos_pendentes"] == "-4800.00", cl
    assert cl["diferenca"] == "-200.00", cl


@caso("sem debito de lote -> controle_lote ausente (None)")
def _():
    ext = [_ext(D, "-50.00", "COMPRA MERCADO")]
    c = match_banco(ext, [])
    assert resumo_privado(c).get("controle_lote") is None, resumo_privado(c).get("controle_lote")


@caso("controle de lote conta so SAIDAS pendentes do razao (ignora entradas)")
def _():
    ext = [_ext(D, "-5000.00", "SISPAG FORNECEDORES")]
    raz = [_raz(D, "-4800.00", "ALFA"), _raz(D, "1000.00", "GAMA")]  # +1000 = entrada pendente
    c = match_banco(ext, raz)
    cl = resumo_privado(c)["controle_lote"]
    assert cl["qtd_titulos_pendentes"] == 1, cl
    assert cl["total_titulos_pendentes"] == "-4800.00", cl
    assert cl["diferenca"] == "-200.00", cl


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn(); print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}"); print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}"); print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas)); return 1
    print(f"==> CONTROLE DE LOTE OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
