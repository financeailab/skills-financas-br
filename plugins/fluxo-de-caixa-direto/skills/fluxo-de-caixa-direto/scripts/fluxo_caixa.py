# -*- coding: utf-8 -*-
"""Fluxo de Caixa Direto: CLI (SPEC-00 §1).

Junta os extratos OFX (multi-conta) com as contas a pagar/a receber do ERP,
categoriza pelo dicionario BR e devolve o realizado por categoria + a projecao
rolante de N semanas, com alertas. O motor nao faz chamada de rede.

Uso:
  python fluxo_caixa.py --extratos <pasta-ou-arquivos .ofx> \
      [--pagar contas-a-pagar.csv|.xlsx] [--receber contas-a-receber.csv|.xlsx] \
      [--perfil omie|generico] [--semanas 13] [--data-base AAAA-MM-DD] \
      [--contas-proprias contas.txt] [--dicionario dicionario-categorias.csv] \
      [--saida pasta] [--xlsx] [--csv] [--json]

Exit codes: 0 ok · 2 erro de entrada (arquivo/perfil) · 3 nenhum lancamento lido.
Na tela sai so contagem, saldo total, numero de linha e o que foi digitado; o detalhe
fica nos arquivos de saida.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))

from ingest_ofx import ingest_extratos            # noqa: E402
from ingest_erp import ler_titulos                 # noqa: E402
from categorizador import carregar_dicionario       # noqa: E402
from dfc import montar                              # noqa: E402
from export_xlsx import (                           # noqa: E402
    exportar_xlsx, exportar_csv, exportar_json, XlsxIndisponivel, FRASE_HONESTIDADE,
)
from normalize import parse_data                    # noqa: E402
from recusa import Recusa                           # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Fluxo de Caixa Direto: realizado por categoria + projecao rolante de N semanas (ERP x extrato).")
    ap.add_argument("--extratos", nargs="+", required=True,
                     help="pasta(s) e/ou arquivo(s) .ofx dos extratos bancarios")
    ap.add_argument("--pagar", help="contas a pagar (CSV ou XLSX)")
    ap.add_argument("--receber", help="contas a receber (CSV ou XLSX)")
    ap.add_argument("--perfil", choices=("generico", "omie"), default="generico",
                     help="perfil de coluna dos titulos a pagar/receber (default: generico)")
    ap.add_argument("--semanas", type=int, default=13, help="horizonte da projecao em semanas (default: 13)")
    ap.add_argument("--data-base", help="data-base da projecao, AAAA-MM-DD (default: hoje)")
    ap.add_argument("--contas-proprias",
                     help="arquivo texto com 1 identificador de conta propria por linha (marca Transferencias Internas)")
    ap.add_argument("--dicionario", help="CSV categoria,keyword customizado (default: dicionario-categorias.csv do motor)")
    ap.add_argument("--saida", default="resultado", help="pasta de saida (default: resultado/)")
    ap.add_argument("--xlsx", action="store_true", help="gera XLSX (default quando nenhuma saida e pedida explicitamente)")
    ap.add_argument("--csv", action="store_true", help="gera CSV (1 por aba)")
    ap.add_argument("--json", action="store_true", help="gera JSON com tudo")
    return ap


def _ler_contas_proprias(caminho: str | None) -> list[str]:
    if not caminho:
        return []
    if not os.path.isfile(caminho):
        raise Recusa(f"arquivo de contas proprias nao encontrado: {caminho}")  # caminho digitado
    with open(caminho, encoding="utf-8-sig") as f:
        return [linha.strip() for linha in f if linha.strip()]


def main(argv=None) -> int:
    import logging
    import warnings
    # console do operador pode ser cp1252/cp850 (Windows) -> blinda print de acento
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    # warning/log de biblioteca (openpyxl) vai ao stderr sem passar pelo handler e pode trazer texto do arquivo
    # shortcut: troca warnings e logging do processo inteiro, trocar por catch_warnings se main() for chamado embutido
    warnings.showwarning = lambda message, category, *a, **k: print(
        f"[aviso] uma biblioteca emitiu {category.__name__}; detalhe omitido (pode trazer texto do arquivo)", file=sys.stderr)
    logging.getLogger().addHandler(logging.NullHandler())

    args = _build_parser().parse_args(argv)

    try:
        res_ofx = ingest_extratos(args.extratos)
    except Recusa as e:
        print(f"[ERRO] {e}")  # saida-ok: Recusa leva so o caminho digitado, nunca texto do arquivo
        return 2
    except OSError:
        print("[ERRO] nao consegui ler um dos extratos informados (permissao ou arquivo em uso).")
        return 2

    if not res_ofx.lancamentos:
        if res_ofx.ilegiveis:  # tem transacao, mas nenhuma legivel: a mensagem diz quantas (Gate 2, passe 4)
            print(f"[ERRO] nenhum lancamento legivel: {sum(res_ofx.ilegiveis.values())} ignorado(s) por data ou "
                  "valor ilegivel. Exporte o extrato de novo do banco e tente de novo.")
        else:
            print("[ERRO] nenhum lancamento lido dos extratos informados. Confira se os arquivos "
                  ".ofx existem e tem transacoes, e tente de novo.")
        return 3

    if args.data_base:
        try:
            data_base = parse_data(args.data_base)
        except ValueError:
            print(f"[ERRO] --data-base invalida: {args.data_base!r}. Use o formato AAAA-MM-DD.")
            return 2
    else:
        data_base = date.today()

    try:
        contas_proprias = _ler_contas_proprias(args.contas_proprias)
    except Recusa as e:
        print(f"[ERRO] {e}")  # saida-ok: Recusa leva so o caminho digitado, nunca texto do arquivo
        return 2
    except (OSError, UnicodeDecodeError):
        print("[ERRO] nao consegui ler o arquivo de contas proprias (use texto UTF-8, 1 conta por linha).")
        return 2

    titulos: list[dict] = []
    projecao_vazia = not (args.pagar or args.receber)
    if projecao_vazia:
        print("[AVISO] nenhum --pagar/--receber informado: rodando so o realizado. A projecao fica vazia.")
    else:
        for caminho, tipo in ((args.pagar, "pagar"), (args.receber, "receber")):
            if not caminho:
                continue
            if not os.path.isfile(caminho):
                print(f"[ERRO] arquivo de titulos a {tipo} nao encontrado: {caminho}")
                return 2
            try:
                titulos += ler_titulos(caminho, perfil=args.perfil, tipo=tipo)
            except Recusa as e:
                print(f"[ERRO] {e}")  # saida-ok: Recusa leva so linha, coluna logica e perfil, nunca a celula
                return 2
            except Exception:  # arquivo corrompido ou num formato que o leitor nao entende
                print(f"[ERRO] nao consegui ler o arquivo de titulos a {tipo}: confira se e um CSV ou XLSX valido.")
                return 2

    try:
        dicionario = carregar_dicionario(args.dicionario)
    except OSError as e:
        print(f"[ERRO] nao consegui ler o dicionario de categorias ({args.dicionario or 'default'}): {e.strerror}")
        return 2
    except (UnicodeDecodeError, ValueError):
        print(f"[ERRO] dicionario de categorias ilegivel ({args.dicionario or 'default'}): use CSV UTF-8 com as colunas categoria,keyword.")
        return 2

    resultado = montar(res_ofx.lancamentos, titulos, res_ofx.contas, data_base, 0 if projecao_vazia else args.semanas,
                        dicionario, contas_proprias=contas_proprias)
    for conta_id, n in res_ofx.ilegiveis.items():  # lancamento ignorado nunca some calado (Gate 2, passe 3)
        resultado.alertas.append({
            "tipo": "LANCAMENTO_ILEGIVEL",
            "detalhe": f"conta {conta_id}: {n} lancamento(s) do OFX ignorado(s) por data ou valor ilegivel; "
                       "confira no extrato do banco",
        })

    os.makedirs(args.saida, exist_ok=True)
    gera_algo_explicito = args.xlsx or args.csv or args.json
    quer_xlsx = args.xlsx or not gera_algo_explicito  # default: XLSX se nada foi pedido

    saidas_geradas = []
    if quer_xlsx:
        try:
            saidas_geradas.append(
                exportar_xlsx(resultado, data_base, os.path.join(args.saida, "fluxo-de-caixa.xlsx")))
        except XlsxIndisponivel:
            print("[AVISO] openpyxl nao instalado; instale openpyxl ou use --csv/--json.")
    if args.csv:
        saidas_geradas += exportar_csv(resultado, data_base, os.path.join(args.saida, "csv"))
    if args.json:
        saidas_geradas.append(
            exportar_json(resultado, data_base, os.path.join(args.saida, "fluxo-de-caixa.json")))

    print("== FLUXO DE CAIXA DIRETO ==")
    print(f"  extratos: {len(res_ofx.arquivos_lidos)} arquivo(s) | {len(res_ofx.contas)} conta(s) | "
          f"{len(res_ofx.lancamentos)} lancamento(s)")
    if res_ofx.ilegiveis:
        print(f"  [!] {sum(res_ofx.ilegiveis.values())} lancamento(s) ignorado(s) por data ou valor ilegivel "
              "(ver Alertas)")
    print(f"  saldo atual: R$ {resultado.saldo_inicial}")
    if projecao_vazia:
        print("  projecao: vazia (sem titulos a pagar/receber)")
    else:
        negativas = [s for s in resultado.semanas if s["saldo"] < 0]
        print(f"  titulos em aberto: {len(resultado.titulos_em_aberto)}")
        if negativas:
            print(f"  [!] {len(negativas)} semana(s) com saldo projetado negativo")
    if resultado.alertas:
        print(f"  alertas: {len(resultado.alertas)} (ver aba/arquivo Alertas)")
    for caminho in saidas_geradas:
        print(f"  saida: {caminho}")
    print(f"  {FRASE_HONESTIDADE}")

    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.unraisablehook = lambda _u: None
    _codigo = 2
    try:
        _codigo = main()
    except SystemExit as _e:
        _codigo = _e.code
    except BaseException:
        try:
            _sys.stderr.write("erro inesperado; o detalhe nao e impresso para nao expor o arquivo\n")
        except BaseException:
            pass
    raise SystemExit(_codigo if _codigo.__class__ is int else (0 if _codigo is None else 2))
