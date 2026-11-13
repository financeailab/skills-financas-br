# -*- coding: utf-8 -*-
"""Leitor de Notas Fiscais (CLI da skill).

  validar       -> a nota/lote e legivel? (contagem por familia, sem nome de arquivo)
  processar     -> XML | pasta de XML | ZIP -> carga.csv + excecoes.csv + resumo.json
  processar-pdf -> extracoes do Claude (JSON) -> carga (caminho PDF/imagem)

PRIVACIDADE: no caminho XML o motor le a nota no disco e imprime so contagens. Quando roda pelo
Claude, o pedido, esse resumo e qualquer arquivo que o Claude abrir vao para a Anthropic. No caminho
PDF/imagem o Claude le o documento.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)  # engine/ e um subdir daqui (dev: raiz; pacote: scripts/)

from engine.batch import CAP_LOTE, Recusa, processar_extracoes, processar_lote, processar_zip  # noqa: E402
from engine.dispatch import parsear  # noqa: E402
from engine.export.csv_generico import exportar_csv  # noqa: E402
from engine.export.xlsx import exportar_xlsx  # noqa: E402


MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB — PRD-SAN-07 S-06 (anti-OOM em arquivo gigante)


def _checar_tamanho(caminho: str) -> None:
    """Recusa arquivo acima de 100 MB ANTES de carregar o conteúdo em memória."""
    tam = os.path.getsize(caminho)
    if tam > MAX_FILE_SIZE:
        raise Recusa(
            f"arquivo recusado: tem {tam // (1024 * 1024)} MB "
            f"(limite: {MAX_FILE_SIZE // (1024 * 1024)} MB)")


def _tomador(args):
    cnpj = getattr(args, "tomador_cnpj", None)
    mun = getattr(args, "tomador_municipio", None)
    if cnpj and mun:
        from engine.model import TomadorReferencia
        return TomadorReferencia(cnpj=cnpj, municipio_ibge=mun)
    return None


def _coletar(entrada: str):
    """Devolve ('zip', bytes) | ('xmls', [(nome, conteudo)])."""
    if entrada.lower().endswith(".zip"):
        _checar_tamanho(entrada)
        with open(entrada, "rb") as f:
            return "zip", f.read()
    if os.path.isdir(entrada):
        arqs = []
        # subpastas tambem, como no ZIP; o nome vira o caminho relativo (so no excecoes.csv e na carga locais)
        # shortcut: sem teto somado na pasta, trocar por um teto total (como o MAX_TOTAL_UNCOMPRESSED do ZIP) se
        # aparecer lote de pasta com arquivos grandes de verdade; hoje o pior caso e 50 x 100 MB em memoria.
        nomes = sorted(os.path.relpath(os.path.join(raiz, f), entrada).replace(os.sep, "/")
                       for raiz, _pastas, fs in os.walk(entrada) for f in fs if f.lower().endswith(".xml"))
        for i, nome in enumerate(nomes):
            if i >= CAP_LOTE:  # alem do corte: so o nome, sem abrir (o lote avisa "fora do limite")
                arqs.append((nome, None))
                continue
            caminho = os.path.join(entrada, nome)
            try:
                _checar_tamanho(caminho)
            except Recusa as e:  # arquivo grande da pasta vira excecao e o lote segue
                arqs.append((nome, e))  # saida-ok: Recusa leva so numeros e limites; vira linha do excecoes.csv local
                continue
            with open(caminho, "rb") as f:
                arqs.append((nome, f.read()))
        return "xmls", arqs
    _checar_tamanho(entrada)
    with open(entrada, "rb") as f:  # arquivo XML unico
        return "xmls", [(os.path.basename(entrada), f.read())]


def _escrever(out_dir: str, res: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "carga.csv"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(res["csv"])
    # planilha de trabalho do analista (ao lado do CSV, que nao muda)
    with open(os.path.join(out_dir, "carga.xlsx"), "wb") as f:
        f.write(exportar_xlsx(res["linhas"], res["resumo"]))
    caminho_exc = os.path.join(out_dir, "excecoes.csv")
    if res["excecoes"]:
        with open(caminho_exc, "w", encoding="utf-8-sig", newline="") as f:
            f.write(exportar_csv(res["excecoes"], colunas=("arquivo_origem", "chave_arquivo", "confianca_nota", "motivo")))
    elif os.path.exists(caminho_exc):  # rodada limpa na mesma pasta: o excecoes.csv antigo nao pode sobrar ao lado da carga nova
        os.remove(caminho_exc)
    with open(os.path.join(out_dir, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump(res["resumo"], f, ensure_ascii=False, indent=2)


def cmd_validar(args) -> int:
    tipo, dados = _coletar(args.entrada)
    if tipo == "zip":
        print("ZIP recebido: rode 'processar' para o lote.")
        return 0
    por_familia: dict[str, int] = {}
    nao_reconhecidas = fora = 0
    for _nome, conteudo in dados:
        if conteudo is None:
            fora += 1
            continue
        try:
            xml = conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo
            fam, modelo = parsear(xml)
        except Exception:  # arquivo ilegivel conta como nao reconhecido e o resto segue
            nao_reconhecidas += 1
            continue
        if modelo is None:
            nao_reconhecidas += 1
        else:
            por_familia[fam.value] = por_familia.get(fam.value, 0) + 1
    print(f"notas reconhecidas: {sum(por_familia.values())}")
    for fam, n in sorted(por_familia.items()):
        print(f"  familia={fam}: {n}")
    print(f"nao reconhecidas: {nao_reconhecidas}")
    if fora:
        print(f"fora do limite: {fora}")
    return 0


def _avisar_fora_do_limite(resumo: dict) -> None:
    n = resumo.get("fora_do_limite", 0)
    if n > 0:
        print(f"[!] {n} nota(s) acima do limite de {CAP_LOTE} por lote ficaram fora: "
              "veja o excecoes.csv e rode de novo com o resto")


def cmd_processar(args) -> int:
    tipo, dados = _coletar(args.entrada)
    ref = _tomador(args)
    if tipo == "zip":
        res = processar_zip(dados, perfil=args.perfil, tomador_ref=ref)
    else:
        res = processar_lote(dados, perfil=args.perfil, tomador_ref=ref)
    _escrever(args.out, res)
    print(json.dumps(res["resumo"], ensure_ascii=False, indent=2))
    _avisar_fora_do_limite(res["resumo"])
    print(f"\ncarga: {os.path.join(args.out, 'carga.csv')}")
    print(f"carga (planilha): {os.path.join(args.out, 'carga.xlsx')}")
    if res["excecoes"]:
        print(f"excecoes: {os.path.join(args.out, 'excecoes.csv')} ({len(res['excecoes'])})")
    return 0


def cmd_processar_pdf(args) -> int:
    _checar_tamanho(args.extracoes)
    with open(args.extracoes, "r", encoding="utf-8") as f:
        bruto = json.load(f)
    # aceita [{"arquivo":..., "extracao":{...}}] ou {"arquivo": {...}}
    if isinstance(bruto, dict):
        itens = list(bruto.items())
    else:
        itens = [(it.get("arquivo", f"doc{i}"), it.get("extracao", it)) for i, it in enumerate(bruto)]
    res = processar_extracoes(itens, perfil=args.perfil, tomador_ref=_tomador(args))
    _escrever(args.out, res)
    print(json.dumps(res["resumo"], ensure_ascii=False, indent=2))
    _avisar_fora_do_limite(res["resumo"])
    print(f"\ncarga: {os.path.join(args.out, 'carga.csv')}")
    print(f"carga (planilha): {os.path.join(args.out, 'carga.xlsx')}")
    return 0


def _parser():
    p = argparse.ArgumentParser(description="Leitor de Notas Fiscais.")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validar")
    v.add_argument("--entrada", required=True)
    for nome in ("processar", "processar-pdf"):
        sp = sub.add_parser(nome)
        sp.add_argument("--perfil", default="generico", choices=["generico", "omie", "contaazul"])
        sp.add_argument("--tomador-cnpj")
        sp.add_argument("--tomador-municipio")
        sp.add_argument("--out", default="resultado")
        if nome == "processar":
            sp.add_argument("--entrada", required=True, help="arquivo .xml | pasta | .zip")
        else:
            sp.add_argument("--extracoes", required=True, help="JSON de extracoes do Claude")
    return p


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _parser().parse_args(argv)
    try:
        return {"validar": cmd_validar, "processar": cmd_processar,
                "processar-pdf": cmd_processar_pdf}[args.cmd](args)
    except Recusa as e:  # recusa do proprio motor: texto fixo so com numeros e limites
        print(f"[erro] {e}", file=sys.stderr)  # saida-ok: Recusa leva so numeros e limites, nunca texto do arquivo
        return 2
    except zipfile.BadZipFile:
        print("[erro] ZIP ilegível", file=sys.stderr)
        return 2
    except json.JSONDecodeError:
        print("[erro] JSON de extrações ilegível", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("[erro] arquivo não está em UTF-8", file=sys.stderr)
        return 2
    except FileNotFoundError:  # o caminho e o que a pessoa digitou, mas o texto fica fixo como os outros
        print("[erro] caminho de entrada não encontrado", file=sys.stderr)
        return 2


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
