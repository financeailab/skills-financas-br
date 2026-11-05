# -*- coding: utf-8 -*-
"""Classificacao das pendencias nas categorias do operador (a "cauda" que nao fecha).

Valida que o motor rotula cada pendencia (tarifa/IOF, rendimento, Pix orfao, liquido
adquirente, cheque nao compensado, deposito em transito) — o que a analista quer p/
"explicar cada pendencia". Casos diretos + integracao no gabarito sintetico.

Rodar:  python tests/test_classificacao_pendencias.py
"""
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
sys.path.insert(0, ENGINE)

from ingest_ofx import parse_ofx                    # noqa: E402
from ingest_tabular import read_tabular             # noqa: E402
from normalize import parse_valor, parse_data, norm_doc  # noqa: E402
from reconcile import match_banco, classifica_pendencia, resumo_privado  # noqa: E402

FIX = os.path.join(HERE, "fixtures")

# --- casos diretos (lado, valor, descricao) -> categoria esperada ---
CASOS = [
    ("EXTRATO", "-45,00", "TAR PACOTE SERVICOS", "TARIFA_IOF"),
    ("EXTRATO", "-12,30", "IOF", "TARIFA_IOF"),
    ("EXTRATO", "3,20", "RENDIMENTO/JUROS", "RENDIMENTO"),
    ("EXTRATO", "1240,00", "PIX RECEBIDO", "PIX_ORFAO"),
    ("EXTRATO", "9760,00", "CRED REDE RECEBIVEIS LIQUIDO", "LIQUIDO_ADQUIRENTE"),
    ("EXTRATO", "-200,00", "PAGAMENTO FORNECEDOR X", "A_LANCAR"),
    ("RAZAO", "-430,00", "Cheque 5004 fornecedor Teta", "CHEQUE_NAO_COMPENSADO"),
    ("RAZAO", "900,00", "Deposito cliente Kappa (em transito)", "DEPOSITO_TRANSITO"),
    ("RAZAO", "-670,00", "Pagto fornecedor Iota", "EM_TRANSITO"),
]

GAB_INTEGRACAO = {
    "TARIFA_IOF": 2, "RENDIMENTO": 1, "CHEQUE_NAO_COMPENSADO": 1, "DEPOSITO_TRANSITO": 1,
}


def razao_canon(linhas):
    return [{"data": parse_data(r["Data"]), "valor": parse_valor(r["Valor"]),
             "doc": norm_doc(r.get("Documento")), "descricao": (r.get("Historico") or "").strip()}
            for r in linhas]


def main() -> int:
    ok = True

    print("== casos diretos ==")
    for lado, val, desc, esp in CASOS:
        got = classifica_pendencia(lado, parse_valor(val), desc)
        bom = got == esp
        ok = ok and bom
        print(f"  {('OK' if bom else 'XX'):>2}  {lado:<8}{val:>10}  {desc[:30]:<32} -> {got} (esp {esp})")

    print("\n== integracao (gabarito sintetico) ==")
    ext = parse_ofx(os.path.join(FIX, "extrato_sintetico.ofx"))
    razao = razao_canon(read_tabular(os.path.join(FIX, "razao_sintetico.csv")))
    c = match_banco(ext.transacoes, razao,
                    saldo_extrato_final=ext.saldo_final, saldo_razao_final=Decimal("12467.50"))
    pend = {k: v["qtd"] for k, v in resumo_privado(c)["pendencias_por_categoria"].items()}
    print(f"  pendencias_por_categoria: {pend}")
    for k, esp in GAB_INTEGRACAO.items():
        bom = pend.get(k, 0) == esp
        ok = ok and bom
        print(f"  {('OK' if bom else 'XX'):>2}  {k:<24} {pend.get(k, 0)} (esp {esp})")
    # nenhuma categoria inesperada
    extra = set(pend) - set(GAB_INTEGRACAO)
    if extra:
        ok = False
        print(f"  XX  categorias inesperadas: {extra}")

    print("\n" + ("==> CLASSIFICACAO OK: pendencias rotuladas nas categorias do operador."
                  if ok else "==> FALHOU (ver XX)."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
