# -*- coding: utf-8 -*-
"""Alargamento declarado (spec Ponytail E3 §2.1): a canonica de normalize.py passou a
aceitar o sufixo '-' (convencao Itau, ex.: "187,65-"). Antes, `_val()` engolia o
ValueError e a linha caia em n_ignoradas; agora ela entra como transacao. Este teste
trava o alargamento no caminho tabular (CSV/XLSX/HTML compartilham `ingest_tabular_rows`).

Rodar:  python tests/test_csv_sufixo_itau.py
"""
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
sys.path.insert(0, ENGINE)

from ingest_extrato import ingest_tabular_rows  # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


@caso("CSV com sufixo '-' (convencao Itau): entra como transacao, nao cai em n_ignoradas")
def _():
    rows = [
        ["Data", "Historico", "Valor"],
        ["01/09/2026", "TED RECEBIDA", "100,00"],
        ["02/09/2026", "PAGAMENTO FORNECEDOR", "50,00"],
        ["03/09/2026", "TAR MANUTENCAO CESTA", "187,65-"],
    ]
    r = ingest_tabular_rows(rows)
    assert r["status"] == "OK", r
    assert r["n_ignoradas"] == 0, r
    assert len(r["transacoes"]) == 3, r["transacoes"]
    por_desc = {t["descricao"]: t["valor"] for t in r["transacoes"]}
    assert por_desc["TAR MANUTENCAO CESTA"] == Decimal("-187.65"), por_desc


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
    print(f"==> CSV SUFIXO ITAU OK: {len(casos)} caso(s) travado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
