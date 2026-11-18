# -*- coding: utf-8 -*-
"""Consulta da Reforma: comandos fixos sobre as tabelas oficiais da reforma tributaria (Receita Federal, MIT).

    python consultar.py cclasstrib <codigo> [--grupo cbs-ibs|is] [--data AAAA-MM-DD]
    python consultar.py referencia [--data AAAA-MM-DD]
    python consultar.py ncm <codigo> [--data ...]          python consultar.py nbs <codigo> [--data ...]
    python consultar.py vinculo (--ncm C | --nbs C) --cclasstrib C [--grupo ...] [--data ...]
    python consultar.py simples [<cAtivSN>] [--data ...]
    python consultar.py buscar <termo> [--em cclasstrib|ncm|nbs] [--data ...]
    python consultar.py sobre

Toda saida comeca pelo cabecalho (consulta de tabela, nao parecer; data da copia). Saida: 0 achou, 1 sem
resultado, 2 entrada invalida, 3 copia das tabelas que nao confere. A entrada nunca e ecoada.
"""
from __future__ import annotations

import argparse
import datetime
import decimal
import os
import re
import sqlite3
import sys

_ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import base  # noqa: E402
import consultas  # noqa: E402

OK, SEM_RESULTADO, ENTRADA, COPIA = 0, 1, 2, 3
DIAS_AVISO = 60
LINHA_1 = "Consulta de tabela oficial da Receita Federal (calculadora-rtc, MIT). Não é parecer tributário."
SEM_MANIFESTO = "O manifesto da cópia das tabelas está ausente, ilegível ou incompleto (tabelas/MANIFESTO.json). Reinstale a skill; nada foi consultado."
FORMATOS = ("Entrada inválida. Formatos: cClassTrib com 6 dígitos; NCM de 2 a 8 dígitos; NBS com 9 dígitos; "
            "cAtivSN com 2 dígitos; termo de 3 a 60 letras, dígitos ou espaços; data AAAA-MM-DD. "
            "Comandos: cclasstrib, referencia, ncm, nbs, vinculo, simples, buscar, sobre.")
SEM_BANCO = ("Não consegui montar ou abrir o banco das tabelas oficiais nesta máquina (pasta temporária sem espaço ou "
             "sem permissão, ou um SQLite que não executa o SQL oficial). Nada foi consultado; não é problema do código "
             "digitado.")
COPIA_TEXTO = {
    base.SqliteAntigo: "O SQLite deste Python é anterior a 3.35, e as tabelas oficiais precisam dele. Atualize o Python; nada foi consultado.",
    base.ArquivosDivergentes: "A cópia das tabelas embutida não confere com o manifesto (arquivo alterado, faltando ou a mais). Reinstale a skill; nada foi consultado.",
    base.CacheInvalido: "O banco montado em cache não confere. Apague os arquivos consulta-reforma-*.db da pasta temporária e rode de novo.",
    base.ManifestoInvalido: SEM_MANIFESTO,
    base.LinhaAmbigua: "A tabela oficial devolveu mais de uma linha onde a calculadora espera uma. Nada foi respondido; avise o mantenedor da skill.",
}
GRUPO_NOME = {"cbs-ibs": "CBS/IBS", "is": "Imposto Seletivo"}


class _EntradaInvalida(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # o argparse ecoaria a entrada; aqui sai texto fixo
        raise _EntradaInvalida()


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="consultar.py", description="Consulta das tabelas oficiais da reforma (Receita Federal).")
    sub = p.add_subparsers(dest="comando", required=True, parser_class=_Parser)
    data = argparse.ArgumentParser(add_help=False)
    data.add_argument("--data")
    grupo = argparse.ArgumentParser(add_help=False)
    grupo.add_argument("--grupo", choices=list(consultas.GRUPOS), default="cbs-ibs")
    sub.add_parser("cclasstrib", parents=[data, grupo]).add_argument("codigo")
    sub.add_parser("referencia", parents=[data])
    sub.add_parser("ncm", parents=[data]).add_argument("codigo")
    sub.add_parser("nbs", parents=[data]).add_argument("codigo")
    v = sub.add_parser("vinculo", parents=[data, grupo])
    alvo = v.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--ncm")
    alvo.add_argument("--nbs")
    v.add_argument("--cclasstrib", required=True)
    sub.add_parser("simples", parents=[data]).add_argument("codigo", nargs="?")
    b = sub.add_parser("buscar", parents=[data])
    b.add_argument("termo")
    b.add_argument("--em", choices=["cclasstrib", "ncm", "nbs"], default="cclasstrib")
    sub.add_parser("sobre")
    return p


def codigo_valido(texto: str | None, tamanhos) -> str | None:
    s = (texto or "").replace(".", "")
    return s if s.isascii() and s.isdigit() and len(s) in tamanhos else None


def termo_valido(texto: str) -> str | None:
    t = " ".join(base.sem_acento(texto).split())
    return t if re.fullmatch(r"[a-z0-9 ]{3,60}", t) else None


def data_valida(texto: str | None, hoje: datetime.date) -> str | None:
    if texto is None:
        return hoje.isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return None
    try:
        return datetime.date.fromisoformat(texto).isoformat()
    except ValueError:
        return None


def br(iso: str) -> str:
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def num(v) -> str:
    """Valor como veio, sem arredondar (o `:g` cortava em 6 digitos); valor nao numerico sai como texto."""
    try:
        texto = format(decimal.Decimal(str(v)).normalize(), "f")
    except decimal.InvalidOperation:
        return str(v)
    return texto.replace(".", ",")


def cabecalho(manifesto: dict, hoje: datetime.date) -> list[str]:
    linhas = [LINHA_1, f"Cópia das tabelas de {br(manifesto['data_copia'])} (commit {manifesto['commit_sql'][:8]} "
                       f"de {br(manifesto['data_commit_sql'])}, base {manifesto['versao_base']})."]
    dias = (hoje - datetime.date.fromisoformat(manifesto["data_copia"])).days
    if dias > DIAS_AVISO:
        linhas.append(f"Atenção: esta cópia tem {dias} dias; a Receita muda estas tabelas com frequência. "
                      "Confira se há versão nova da skill.")
    return linhas


def _cclasstrib(con, a, data) -> int:
    cc = codigo_valido(a.codigo, (6,))
    if cc is None:
        raise _EntradaInvalida()
    r = consultas.classificacao(con, cc, data, a.grupo)
    if r is None:
        print(f"Nenhuma cClassTrib com esse código no grupo {GRUPO_NOME[a.grupo]} nesta data.")
        return SEM_RESULTADO
    print(f"cClassTrib: {r['codigo']} (grupo {GRUPO_NOME[a.grupo]})")
    print(f"Descrição: {r['descricao']}")
    print(f"CST: {r['cst']} ({r['cst_descricao']})")
    reducoes = "; ".join(f"{s} {num(v)}%" for s, v in r["reducoes"] if v is not None)
    print(f"Redução: {reducoes or 'nenhuma linha de redução na base oficial'}")
    for curto, ref in r["fundamentos"]:
        ref_limpa = " ".join((ref or "").replace("\\n", " ").split())
        print(f"Fundamentação: {curto or ''} {ref_limpa}".rstrip())
    fim = f"até {br(r['fim'])}" if r["fim"] else "sem fim"
    print(f"Vigência: desde {br(r['inicio'])}, {fim}")
    return OK


def _referencia(con, a, data) -> int:
    linhas = consultas.referencia(con, data)
    if not linhas:
        ini, fim = consultas.faixa(con, "ALIQUOTA_REFERENCIA", "ALRE")
        faixa = f"de {br(ini)} a {br(fim)}" if ini and fim else (f"desde {br(ini)}" if ini else "nenhuma data")
        print(f"A base oficial não traz alíquota de referência para esta data (só há {faixa}). "
              "Fora disso, a própria calculadora pede a alíquota informada (docs/exemplos.md da Receita).")
        return SEM_RESULTADO
    print("Alíquotas de referência: " + "; ".join(f"{s} {num(v)}%" for s, v in linhas))
    return OK


def _texto_is(linha, tipo: str) -> str | None:
    """Linha (valor,) do ad valorem ou (valor, unidade) do ad rem; a unidade vem da tabela (ex.: Vintena de cigarro)."""
    if linha is None:
        return None
    if linha[0] is None:
        return f"alíquota {tipo} não definida na base oficial"
    if tipo == "ad valorem":
        return f"alíquota {tipo} {num(linha[0])}%"
    unidade = (linha[1] if len(linha) > 1 else None) or "unidade da tabela"
    return f"alíquota {tipo} {num(linha[0])} por {unidade.lower()}"


def _ncm_nbs(con, a, data, tipo: str) -> int:
    cd = codigo_valido(a.codigo, range(2, 9) if tipo == "ncm" else (9,))
    if cd is None:
        raise _EntradaInvalida()
    r = consultas.ncm(con, cd, data) if tipo == "ncm" else consultas.nbs(con, cd, data)
    if r is None:
        print(f"Nenhuma {tipo.upper()} com esse código vigente nesta data.")
        return SEM_RESULTADO
    print(f"{tipo.upper()}: {cd}")
    for c, d in r["niveis"]:
        print(f"  {c} {d}")
    partes = [t for t in (_texto_is(r["is_ad_valorem"], "ad valorem"), _texto_is(r.get("is_ad_rem"), "ad rem")) if t]
    inicio = consultas.inicio_is(con)
    if partes:
        texto = f"incide ({'; '.join(partes)})"
    elif inicio and data < inicio:  # antes do IS existir, "sem incidencia" leria como resposta definitiva
        texto = (f"ainda não vige nesta data (na base oficial, começa em {br(inicio)}); "
                 "para ver a incidência, consulte com --data a partir dessa data")
    elif r.get("is_subitens"):
        texto = "incide em subitens desta NCM nesta data; consulte a NCM com 8 dígitos"
    elif r.get("is_fim"):
        texto = (f"a base oficial traz linhas do Imposto Seletivo para esta NCM só até {br(r['is_fim'])}; "
                 "nada a afirmar nesta data")
    else:
        texto = "sem incidência na base oficial"
    print("Imposto Seletivo: " + texto)
    return OK


def _vinculo(con, a, data) -> int:
    tipo = "ncm" if a.ncm is not None else "nbs"
    cd = codigo_valido(a.ncm if tipo == "ncm" else a.nbs, range(2, 9) if tipo == "ncm" else (9,))
    cc = codigo_valido(a.cclasstrib, (6,))
    if cd is None or cc is None:
        raise _EntradaInvalida()
    r = consultas.vinculo(con, tipo, cd, cc, data, a.grupo)
    if r is None:
        print(f"Nenhuma cClassTrib com esse código no grupo {GRUPO_NOME[a.grupo]} nesta data.")
        return SEM_RESULTADO
    if r == consultas.CODIGO_INEXISTENTE:
        print(f"Nenhuma {tipo.upper()} com esse código vigente nesta data.")
        return SEM_RESULTADO
    if r == consultas.INCOMPLETO:
        print(f"Esta cClassTrib tem lista de {tipo.upper()}: informe o código completo (NCM com 8 dígitos, NBS com 9).")
        return ENTRADA
    alvo = f"{tipo.upper()} {cd} na cClassTrib {cc} (grupo {GRUPO_NOME[a.grupo]})"
    if r == consultas.SEM_LISTA:
        print(f"Vínculo: {alvo}: a cClassTrib não tem lista de {tipo.upper()} nesta data (a calculadora não restringe o código).")
        return OK
    print(f"Vínculo: {alvo}: {'vinculada' if r == consultas.VINCULADA else 'não vinculada'}.")
    return OK


def _simples(con, a, data) -> int:
    cd = None
    if a.codigo is not None:
        cd = codigo_valido(a.codigo, (2,))
        if cd is None:
            raise _EntradaInvalida()
    linhas = consultas.simples(con, data, cd)
    if not linhas:
        ini, _fim = consultas.faixa(con, "ATIVIDADE_SIMPLES_NACIONAL", "ATSN")
        if cd is not None and consultas.simples(con, data):
            print("Nenhuma atividade do Simples Nacional com esse código nesta data.")
        else:
            print("Nenhuma atividade do Simples Nacional vigente nesta data"
                  + (f" (na base oficial, o catálogo começa em {br(ini)})." if ini else "."))
        return SEM_RESULTADO
    for cod, desc, sem_fr, com_fr, rotulo in linhas:
        if sem_fr is None:
            anexo = "sem anexo"
        elif com_fr:
            anexo = f"anexo {sem_fr}, ou {com_fr} com Fator R"
        else:
            anexo = f"anexo {rotulo or sem_fr}"
        print(f"{cod}: {anexo}. {desc}")
    return OK


def _buscar(con, a, data) -> int:
    termo = termo_valido(a.termo)
    if termo is None:
        raise _EntradaInvalida()
    total, linhas = consultas.buscar(con, termo, data, a.em)
    if not total:
        print("Nenhum código vigente com esse termo na descrição.")
        return SEM_RESULTADO
    print(f"Encontrados {total}; mostrando {len(linhas)}:")
    for cod, desc in linhas:
        print(f"{cod}: {desc}")
    return OK


def _sobre(manifesto: dict) -> int:
    print(f"Fonte: {manifesto['fonte']} ({manifesto['caminho']}), commit {manifesto['commit_sql']}.")
    print(f"Licença das tabelas: {manifesto['licenca']}. Crédito: Receita Federal do Brasil.")
    print("Esta skill: Finance AI Lab, Apache-2.0. Ela só lê as tabelas; não faz cálculo de imposto.")
    return OK


COMANDOS = {"cclasstrib": _cclasstrib, "referencia": _referencia, "vinculo": _vinculo, "simples": _simples,
            "buscar": _buscar, "ncm": lambda c, a, d: _ncm_nbs(c, a, d, "ncm"),
            "nbs": lambda c, a, d: _ncm_nbs(c, a, d, "nbs")}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console do Windows; dentro de main pela regra R3 do cheque
    hoje = datetime.date.today()
    try:
        manifesto = base.ler_manifesto()  # valida campos, tipos e datas
        linhas = cabecalho(manifesto, hoje)
    except base.ManifestoInvalido:
        print(LINHA_1)
        print(SEM_MANIFESTO)
        return COPIA
    for linha in linhas:
        print(linha)
    try:
        a = _parser().parse_args(argv)
        data = data_valida(getattr(a, "data", None), hoje)
        if data is None:
            raise _EntradaInvalida()
        if a.comando == "sobre":
            return _sobre(manifesto)
        print(f"Data consultada: {br(data)}.")
        con = base.abrir()
        try:
            return COMANDOS[a.comando](con, a, data)
        finally:
            con.close()
    except _EntradaInvalida:
        print(FORMATOS)
        return ENTRADA
    except base.CopiaInvalida as erro:
        print(COPIA_TEXTO.get(type(erro), "A cópia das tabelas não confere. Reinstale a skill; nada foi consultado."))
        return COPIA
    except (OSError, sqlite3.Error):
        print(SEM_BANCO)  # pasta sem espaco ou sem permissao, SQLite que nao executa o SQL oficial
        return COPIA


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
