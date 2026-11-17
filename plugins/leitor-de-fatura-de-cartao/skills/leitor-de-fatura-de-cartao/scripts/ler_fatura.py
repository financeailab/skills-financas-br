# -*- coding: utf-8 -*-
"""CLI de integracao: PDF de fatura de cartao corporativo -> CSV/XLSX.

Fia os modulos-folha do motor (detector -> parser por emissor -> prova de
completude -> emissores) numa unica fatia end-to-end, antifragil (nunca
pendura, nunca estoura stacktrace cru pro usuario) e respeitando o fosso de
privacidade (o motor nao faz chamada de rede; stdout so mostra AGREGADOS,
nunca lancamento a lancamento).

Modo unico:
    python ler_fatura.py <fatura.pdf> [--saida <base>]
        [--formato csv|xlsx|todos] [--emissor auto|itau|bradesco|generico]

Modo lote (ate 12 faturas de uma pasta -> 1 CSV/XLSX consolidado + resumo + excecoes):
    python ler_fatura.py --lote <pasta> --csv <out.csv> [--xlsx <out.xlsx>]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from decimal import Decimal

# scripts/engine no path (fia os modulos-folha planos: modelo, detector, bancos.*, ...)
_ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import detector  # noqa: E402
import emit_csv  # noqa: E402
import emit_xlsx  # noqa: E402
import lote  # noqa: E402
from bancos import bradesco, generico, itau  # noqa: E402
from modelo import BAIXA_CONFIANCA, FaturaParsed, LAYOUT_DESCONHECIDO, OK, TOTAL_NAO_FECHA  # noqa: E402
from prova_total import validar as validar_total  # noqa: E402

ERRO_TIMEOUT = "PDF MUITO GRANDE"
ERRO_LEITURA = "ERRO DE LEITURA"

# Exit codes por veredicto (SPEC-00 §6): distintos p/ automacao decidir sem parsear stdout.
_EXIT_POR_VEREDICTO = {
    OK: 0,
    TOTAL_NAO_FECHA: 2,
    LAYOUT_DESCONHECIDO: 3,
    BAIXA_CONFIANCA: 4,
}
_EXIT_ERRO = 1

_PARSERS = {"itau": itau.parse, "bradesco": bradesco.parse, "generico": generico.parse}
_FORMATOS_VALIDOS = ("csv", "xlsx", "todos")
_EMISSORES_VALIDOS = ("auto", "itau", "bradesco", "generico")

_ORCAMENTO_EXTRACAO_S = 30.0


def _extrair_paginas(pdf_path: str, orcamento_s: float = _ORCAMENTO_EXTRACAO_S) -> list:
    """Abre o PDF com pdfplumber e devolve `paginas` = list[{"texto","words"}].

    Orcamento de tempo simples: se a extracao pagina-a-pagina passar do orcamento,
    levanta TimeoutError (tratado pelo chamador) em vez de pendurar num PDF gigante.
    """
    import pdfplumber

    t0 = time.monotonic()
    paginas = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            if time.monotonic() - t0 > orcamento_s:
                raise TimeoutError("PDF muito grande (mais de 30 s de extracao): divida a fatura")
            paginas.append({"texto": pg.extract_text() or "", "words": pg.extract_words()})
    return paginas


def _montar_resumo(fatura: FaturaParsed, arquivos: dict) -> dict:
    """Resumo AGREGADO (nunca lancamento a lancamento) para stdout/retorno."""
    return {
        "emissor": fatura.emissor,
        "portadores": list(fatura.portadores),
        "vencimento": fatura.vencimento.strftime("%d/%m/%Y") if fatura.vencimento else "",
        "n_lancamentos": len(fatura.lancamentos),
        "n_encargos": len(fatura.encargos),
        "total_calculado": fatura.total_calculado,
        "total_fatura": fatura.total_fatura,
        "veredicto": fatura.veredicto,
        "aviso": fatura.aviso,
        "arquivos": arquivos,
    }


def ler(pdf_path: str, saida: str | None = None, formato: str = "todos",
        emissor: str = "auto") -> dict:
    """Le `pdf_path` (fatura em PDF) e emite CSV/XLSX. Escreve os arquivos pedidos
    em disco (base `saida`, default = nome do PDF sem extensao) e devolve um
    dict-resumo (agregado). Antifragil: qualquer excecao vira um resumo com
    veredicto de erro, nunca propaga stacktrace."""
    if formato not in _FORMATOS_VALIDOS:
        raise ValueError(f"formato invalido: {formato!r} (use um de {_FORMATOS_VALIDOS})")
    if emissor not in _EMISSORES_VALIDOS:
        raise ValueError(f"emissor invalido: {emissor!r} (use um de {_EMISSORES_VALIDOS})")

    if saida is None:
        saida = os.path.splitext(pdf_path)[0]

    try:
        paginas = _extrair_paginas(pdf_path)
    except TimeoutError:
        aviso = "PDF muito grande (mais de 30 s de extracao): divida a fatura"  # texto fixo, sem str(e)
        fatura = FaturaParsed(veredicto=ERRO_TIMEOUT, aviso=aviso)
        resumo = _montar_resumo(fatura, {})
        resumo["erro"] = aviso
        return resumo
    except Exception as e:  # noqa: BLE001 — PDF corrompido/ilegivel: nunca propaga stacktrace cru
        aviso = f"nao consegui ler o PDF ({type(e).__name__})"
        fatura = FaturaParsed(veredicto=ERRO_LEITURA, aviso=aviso)
        resumo = _montar_resumo(fatura, {})
        resumo["erro"] = aviso
        return resumo

    try:
        nome_emissor = detector.detectar(paginas) if emissor == "auto" else emissor
        parse = _PARSERS.get(nome_emissor, generico.parse)
        fatura = parse(paginas)
        validar_total(fatura)

        formatos_a_gerar = ("csv", "xlsx") if formato == "todos" else (formato,)
        arquivos = {}
        if "csv" in formatos_a_gerar:
            path = f"{saida}.csv"
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(emit_csv.emit(fatura))
            arquivos["csv"] = path
        if "xlsx" in formatos_a_gerar:
            path = f"{saida}.xlsx"
            emit_xlsx.emit(fatura, path)
            arquivos["xlsx"] = path

        return _montar_resumo(fatura, arquivos)
    except Exception as e:  # noqa: BLE001 — antifragil: qualquer falha do pipeline vira resumo de erro
        aviso = f"erro ao ler a fatura ({type(e).__name__})"
        fatura = FaturaParsed(veredicto=LAYOUT_DESCONHECIDO, aviso=aviso)
        resumo = _montar_resumo(fatura, {})
        resumo["erro"] = aviso
        return resumo


def _fmt_valor(v: Decimal | None) -> str:
    return f"R$ {v:.2f}" if v is not None else "(nao encontrado)"


def _imprimir_resumo(resumo: dict) -> None:
    print("=" * 60)
    print("RESUMO DA LEITURA")
    print("=" * 60)
    print(f"Emissor:            {resumo['emissor'] or '(nao identificado)'}")
    print(f"Portadores:         {len(resumo['portadores'])}")
    print(f"Vencimento:         {resumo['vencimento'] or '-'}")
    print(f"Lancamentos:        {resumo['n_lancamentos']}")
    print(f"Encargos:           {resumo['n_encargos']}")
    print(f"Total calculado:    {_fmt_valor(resumo['total_calculado'])}")
    print(f"Total da fatura:    {_fmt_valor(resumo['total_fatura'])}")
    print("-" * 60)
    print(f"VEREDICTO: {resumo['veredicto']}")
    if resumo.get("aviso"):
        print(f"Aviso: {resumo['aviso']}")
    if resumo.get("erro"):
        print(f"Erro: {resumo['erro']}")
    if resumo.get("arquivos"):
        print("-" * 60)
        print("Arquivos gerados:")
        for fmt, path in resumo["arquivos"].items():
            print(f"  .{fmt}: {path}")
    print("=" * 60)


def _imprimir_resumo_lote(resumo: dict, excecoes: list, arquivos: dict) -> None:
    print("=" * 60)
    print("RESUMO DO LOTE")
    print("=" * 60)
    print(f"Total de arquivos:  {resumo['total_arquivos']}")
    print(f"Processadas:        {resumo['processadas']}")
    print(f"Duplicatas (hash):  {resumo['duplicatas']}")
    print(f"Excedentes (limite):{resumo['excedentes']}")
    print("-" * 60)
    for ver, n in sorted(resumo["por_veredicto"].items()):
        print(f"  {ver}: {n}")
    if excecoes:
        print("-" * 60)
        print("Excecoes (veredicto != OK):")
        for nome, veredicto, aviso in excecoes:
            print(f"  {nome}: {veredicto} ({aviso})")
    if arquivos:
        print("-" * 60)
        print("Arquivos gerados:")
        for fmt, path in arquivos.items():
            print(f"  .{fmt}: {path}")
    print("=" * 60)


def _rodar_lote(pasta: str, csv_out: str | None, xlsx_out: str | None) -> int:
    processadas, duplicatas, excedentes = lote.processar_pasta(pasta)
    resumo = lote.resumo_agregado(processadas, duplicatas, excedentes)
    excecoes = lote.listar_excecoes(processadas)

    arquivos = {}
    if csv_out:
        lote.exportar_csv_consolidado(processadas, csv_out)
        arquivos["csv"] = csv_out
    if xlsx_out:
        lote.exportar_xlsx_consolidado(processadas, resumo, xlsx_out)
        arquivos["xlsx"] = xlsx_out

    _imprimir_resumo_lote(resumo, excecoes, arquivos)

    if not processadas:
        return _EXIT_ERRO
    # exit code do lote: pior veredicto entre as faturas processadas (nunca esconde falha)
    piores = [_EXIT_POR_VEREDICTO.get(fatura.veredicto, _EXIT_ERRO) for _, fatura in processadas]
    return max(piores)


def main(argv: list | None = None) -> int:
    import logging
    import warnings

    # warning/log de biblioteca vai ao stderr sem passar pelo handler e pode trazer texto do arquivo
    # shortcut: troca warnings e logging do processo inteiro, trocar por catch_warnings se main() for chamado embutido
    warnings.showwarning = lambda message, category, *a, **k: print(
        f"[aviso] uma biblioteca emitiu {category.__name__}; detalhe omitido (pode trazer texto do arquivo)", file=sys.stderr)
    logging.disable(logging.CRITICAL)

    parser = argparse.ArgumentParser(
        prog="ler_fatura.py",
        description="Le fatura de cartao corporativo em PDF e emite lancamentos em CSV/XLSX (o motor nao faz chamada de rede).",
    )
    parser.add_argument("pdf", nargs="?", help="caminho da fatura em PDF (modo unico)")
    parser.add_argument("--saida", default=None, help="base do nome dos arquivos de saida (modo unico)")
    parser.add_argument("--formato", choices=_FORMATOS_VALIDOS, default="todos")
    parser.add_argument("--emissor", choices=_EMISSORES_VALIDOS, default="auto")
    parser.add_argument("--lote", metavar="PASTA", help="varre a pasta (ate 12 PDFs) e consolida")
    parser.add_argument("--csv", metavar="OUT.csv", help="caminho do CSV consolidado (modo --lote)")
    parser.add_argument("--xlsx", metavar="OUT.xlsx", help="caminho do XLSX consolidado (modo --lote)")
    args = parser.parse_args(argv)

    if args.lote:
        if not (args.csv or args.xlsx):
            parser.error("no modo --lote informe --csv e/ou --xlsx para gerar o consolidado")
        return _rodar_lote(args.lote, args.csv, args.xlsx)

    if not args.pdf:
        parser.error("informe uma <fatura.pdf> ou --lote <pasta>")

    resumo = ler(args.pdf, saida=args.saida, formato=args.formato, emissor=args.emissor)
    _imprimir_resumo(resumo)

    if resumo["veredicto"] in (ERRO_TIMEOUT, ERRO_LEITURA):
        return _EXIT_ERRO
    return _EXIT_POR_VEREDICTO.get(resumo["veredicto"], _EXIT_ERRO)


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
