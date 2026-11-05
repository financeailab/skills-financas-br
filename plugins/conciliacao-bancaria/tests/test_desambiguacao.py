# -*- coding: utf-8 -*-
"""Desambiguacao por identificador — prova que contraparte/CNPJ/CPF ganham o par certo.

Caso real e perigoso: dois lancamentos de MESMO VALOR no MESMO DIA. So por valor+data
o pareamento e arbitrario (e pode casar errado). Com CNPJ/contraparte, casa certo.

Aqui a ORDEM e montada para o baseline (sem enriquecimento) ERRAR — provando que o
campo extra paga o custo. Rodar:  python tests/test_desambiguacao.py
"""
import copy
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine"))

from normalize import extrai_cpf_cnpj      # noqa: E402
from reconcile import match_banco          # noqa: E402

D = date(2026, 1, 10)
V = Decimal("-1000.00")

# razao: ordem proposital (XYZ primeiro) p/ o baseline FIFO errar
razao = [
    {"data": D, "valor": V, "doc": "5001", "identificador": None,
     "contraparte": "XYZ SERVICOS", "cpf_cnpj": "98765432000111", "descricao": ""},
    {"data": D, "valor": V, "doc": "5002", "identificador": None,
     "contraparte": "ABC MATERIAIS", "cpf_cnpj": "12345678000190", "descricao": ""},
]
# extrato: ABC primeiro; PIX traz o CNPJ no MEMO -> extraido deterministicamente
memo_abc = "PIX ENVIADO 12.345.678/0001-90 ABC MATERIAIS LTDA"
memo_xyz = "PIX ENVIADO XYZ SERVICOS 98.765.432/0001-11"
extrato = [
    {"data": D, "valor": V, "doc": None, "identificador": None,
     "contraparte": memo_abc, "cpf_cnpj": extrai_cpf_cnpj(memo_abc), "descricao": memo_abc},
    {"data": D, "valor": V, "doc": None, "identificador": None,
     "contraparte": memo_xyz, "cpf_cnpj": extrai_cpf_cnpj(memo_xyz), "descricao": memo_xyz},
]


def pares(conc):
    """{contraparte do extrato -> cpf_cnpj do razao pareado}."""
    m = {}
    for l in conc.lancamentos:
        if l.lado == "EXTRATO" and l.par_idx is not None:
            m[l.registro["contraparte"]] = razao[l.par_idx]["cpf_cnpj"]
    return m


def main() -> int:
    ok = True

    # 0) extracao de CPF/CNPJ do MEMO funciona
    assert_cnpj = extrai_cpf_cnpj(memo_abc) == "12345678000190" and extrai_cpf_cnpj(memo_xyz) == "98765432000111"
    print(f"extrai_cpf_cnpj do MEMO: {'OK' if assert_cnpj else 'XX'}")
    ok = ok and assert_cnpj

    # 1) COM enriquecimento -> cada extrato casa com o razao de MESMO CNPJ
    enr = pares(match_banco(extrato, razao))
    certo = all(extrai_cpf_cnpj(cp) == cnpj for cp, cnpj in enr.items())
    print(f"\ncom enriquecimento (CNPJ desempata):")
    for cp, cnpj in enr.items():
        print(f"  {cp[:34]:<36} -> razao CNPJ {cnpj}  {'OK' if extrai_cpf_cnpj(cp)==cnpj else 'XX <<<'}")
    print(f"  => {'CASOU CERTO' if certo else 'CASOU ERRADO'}")
    ok = ok and certo

    # 2) baseline SEM enriquecimento (remove contraparte/cnpj) -> FIFO casa ERRADO
    ext0 = copy.deepcopy(extrato)
    raz0 = copy.deepcopy(razao)
    for r in ext0 + raz0:
        r["contraparte"], r["cpf_cnpj"] = "", None
    base = match_banco(ext0, raz0)
    # mapeia extrato (por descricao original) -> cnpj do razao pareado (do razao ORIGINAL)
    base_map = {}
    for l in base.lancamentos:
        if l.lado == "EXTRATO" and l.par_idx is not None:
            base_map[l.registro["descricao"]] = razao[l.par_idx]["cpf_cnpj"]
    baseline_erra = any(extrai_cpf_cnpj(desc) != cnpj for desc, cnpj in base_map.items())
    print(f"\nbaseline sem enriquecimento (FIFO/valor+data):")
    for desc, cnpj in base_map.items():
        print(f"  {desc[:34]:<36} -> razao CNPJ {cnpj}  {'erra' if extrai_cpf_cnpj(desc)!=cnpj else 'acerta'}")
    print(f"  => {'ERRA (esperado: enriquecimento paga o custo)' if baseline_erra else 'acertou por sorte'}")
    ok = ok and baseline_erra

    print("\n" + ("==> DESAMBIGUACAO OK: identificador escolhe o par certo onde valor+data e ambiguo."
                  if ok else "==> FALHOU."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
