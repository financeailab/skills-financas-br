# -*- coding: utf-8 -*-
"""ESTAGIO B — caminho bancario: parser OFX + match_banco + amarracao contra gabarito.

Interino: roda contra o cenario SINTETICO (fixtures/). Quando o Doug fornecer um par
REAL anonimizado (extrato OFX + razao), aponte OFX/RAZAO/GABARITO para ele e rode o
mesmo harness — a logica nao muda.

Rodar:  python tests/test_estagio_b_banco.py
"""
import json
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
sys.path.insert(0, ENGINE)

from ingest_ofx import parse_ofx           # noqa: E402
from ingest_tabular import read_tabular    # noqa: E402
from normalize import parse_valor, parse_data, norm_doc  # noqa: E402
from reconcile import match_banco          # noqa: E402

FIX = os.path.join(HERE, "fixtures")
OFX = os.path.join(FIX, "extrato_sintetico.ofx")
RAZAO = os.path.join(FIX, "razao_sintetico.csv")
GABARITO = os.path.join(FIX, "gabarito_sintetico.json")


def razao_para_canonico(linhas: list[dict]) -> list[dict]:
    """Mapeia as colunas da razao para o modelo canonico (+entrada / -saida)."""
    out = []
    for r in linhas:
        out.append({
            "data": parse_data(r["Data"]),
            "valor": parse_valor(r["Valor"]),
            "doc": norm_doc(r.get("Documento")),
            "descricao": (r.get("Historico") or "").strip(),
        })
    return out


def main() -> int:
    gab = json.load(open(GABARITO, encoding="utf-8"))
    esp = gab["esperado"]

    ext = parse_ofx(OFX)
    razao = razao_para_canonico(read_tabular(RAZAO))

    c = match_banco(
        ext.transacoes, razao,
        saldo_extrato_final=ext.saldo_final,
        saldo_razao_final=Decimal(gab["saldo_razao_final"]),
    )

    checks = []
    for status, qtd in esp["contagem"].items():
        checks.append((f"contagem[{status}]", c.contagem.get(status, 0), qtd))
    checks.append(("total_extrato", str(c.total_esquerdo), esp["total_extrato"]))
    checks.append(("total_razao", str(c.total_direito), esp["total_razao"]))
    checks.append(("saldo_extrato_final(OFX)", str(ext.saldo_final), esp["saldo_extrato_final"]))
    checks.append(("amarracao_fecha", c.integridade_ok, esp["amarracao_fecha"]))
    checks.append(("residuo", c.amarracao["residuo"], esp["residuo"]))

    print(f"OFX: banco={ext.banco} conta={ext.conta} | txns={len(ext.transacoes)} | razao={len(razao)}\n")
    print(f"{'check':<32}{'MOTOR':>14}{'GABARITO':>14}  OK?")
    allok = True
    for nome, got, exp in checks:
        ok = str(got) == str(exp)
        allok = allok and ok
        print(f"{nome:<32}{str(got):>14}{str(exp):>14}  {'OK' if ok else 'XX <<<'}")

    print("\n--- amarracao ---")
    for k, v in (c.amarracao or {}).items():
        print(f"  {k}: {v}")

    print("\n" + ("==> ESTAGIO B OK: parser OFX + match_banco + amarracao batem o gabarito sintetico."
                  if allok else "==> FALHOU. Ver linhas XX."))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
