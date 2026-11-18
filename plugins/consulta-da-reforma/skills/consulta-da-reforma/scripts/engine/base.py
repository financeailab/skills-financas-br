# -*- coding: utf-8 -*-
"""Monta o banco SQLite das tabelas oficiais da reforma (Receita Federal, calculadora-rtc, MIT) sem Java.

Os .sql de tabelas/flyway-sql sao copia byte a byte do repositorio da Receita; o manifesto fixa o sha256 de
cada um. A ordem e a regra de transacao reproduzem o Flyway (spike docs/projetos-futuros/SPIKE-consulta-
reforma-tabelas-rf-2026-11.md, secao 2). Caminhos com joinpath: o teste de "sem calculo" proibe `/` em scripts/.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from pathlib import Path

TABELAS = Path(__file__).resolve().parents[2].joinpath("tabelas")
SQLITE_MINIMO = (3, 35, 0)  # as migracoes usam ALTER TABLE ... DROP COLUMN
_PRAGMA_FK = re.compile(r"(?im)^\s*PRAGMA\s+foreign_keys")
_NUM_V = re.compile(r"V(\d+)__")


class CopiaInvalida(Exception):
    """A copia embutida nao confere. Uma subclasse por causa: o CLI trata por tipo, sem ler o texto da excecao."""


class SqliteAntigo(CopiaInvalida):
    pass


class ArquivosDivergentes(CopiaInvalida):
    pass


class CacheInvalido(CopiaInvalida):
    pass


class LinhaAmbigua(CopiaInvalida):
    pass


class ManifestoInvalido(CopiaInvalida):
    pass


_CAMPOS_TEXTO = ("fonte", "caminho", "commit_sql", "commit_head", "data_commit_sql", "data_copia", "versao_base",
                 "licenca")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VERSAO_BASE = re.compile(r"V\d{4}")
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


def ler_manifesto(tabelas: Path = TABELAS) -> dict:
    """Le e valida o manifesto: ausente, ilegivel ou incompleto vira ManifestoInvalido (o CLI sai com 3)."""
    try:
        m = json.loads(tabelas.joinpath("MANIFESTO.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ManifestoInvalido() from None
    if not isinstance(m, dict) or not all(isinstance(m.get(c), str) for c in _CAMPOS_TEXTO):
        raise ManifestoInvalido()
    arquivos = m.get("arquivos")
    if not isinstance(arquivos, dict) or not arquivos or not all(
            isinstance(k, str) and isinstance(v, str) and _SHA256.fullmatch(v) for k, v in arquivos.items()):
        raise ManifestoInvalido()
    if not (_SHA1.fullmatch(m["commit_sql"]) and _SHA1.fullmatch(m["commit_head"])
            and _VERSAO_BASE.fullmatch(m["versao_base"])):
        raise ManifestoInvalido()
    for campo in ("data_commit_sql", "data_copia"):
        if not _DATA.fullmatch(m[campo]):
            raise ManifestoInvalido()
        try:
            datetime.date.fromisoformat(m[campo])
        except ValueError:
            raise ManifestoInvalido() from None
    return m


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(x) for x in texto.split("."))


def conferir(tabelas: Path, manifesto: dict, versao_sqlite: str = sqlite3.sqlite_version) -> None:
    if _versao(versao_sqlite) < SQLITE_MINIMO:
        raise SqliteAntigo()
    sql = tabelas.joinpath("flyway-sql")
    # so .sql conta, como no manifesto: .DS_Store ou Thumbs.db do sistema nao travam a skill; .sql a mais, sim
    presentes = {p.relative_to(sql).as_posix() for p in sql.rglob("*.sql") if p.is_file()}
    if presentes != set(manifesto["arquivos"]):
        raise ArquivosDivergentes()
    for rel, sha in manifesto["arquivos"].items():
        if hashlib.sha256(sql.joinpath(rel).read_bytes()).hexdigest() != sha:
            raise ArquivosDivergentes()


def ordem_flyway(sql: Path) -> list[Path]:
    """beforeMigrate, B0001, V0002..Vn por numero (nao por texto), afterMigrate."""
    criacao, manutencao = sql.joinpath("criacao"), sql.joinpath("manutencao")
    numero = lambda p: int(_NUM_V.match(p.name).group(1))
    return [criacao.joinpath("beforeMigrate.sql"), *sorted(criacao.glob("B[0-9]*.sql")),
            *sorted(manutencao.glob("V[0-9]*.sql"), key=numero), criacao.joinpath("afterMigrate.sql")]


def _aplicar(con: sqlite3.Connection, ordem: list[Path]) -> None:
    for p in ordem:
        texto = p.read_text(encoding="utf-8")
        # Flyway no SQLite: script com PRAGMA foreign_keys roda fora de transacao; os demais, cada um numa
        # transacao (o PRAGMA defer_foreign_keys de V0011, V0013, V0027, V0035 e V0041 so vale dentro dela)
        if not _PRAGMA_FK.search(texto):
            texto = f"BEGIN;\n{texto}\nCOMMIT;"
        con.executescript(texto)


def caminho_banco(manifesto: dict, cache_dir: str | os.PathLike) -> Path:
    # a chave cobre as tabelas e o proprio motor: versao nova da montagem nao reusa banco montado pela antiga
    # shortcut: bancos de versoes antigas ficam na pasta do cache (5 MB cada); apagar os antigos se alguem reclamar de espaco
    chave = json.dumps(manifesto["arquivos"], sort_keys=True).encode("utf-8") + Path(__file__).read_bytes()
    h = hashlib.sha256(chave).hexdigest()[:12]
    return Path(cache_dir).joinpath(f"consulta-reforma-{manifesto['commit_sql'][:8]}-{h}.db")


def pasta_cache(base_dir: str | os.PathLike | None = None) -> Path:
    """Pasta do cache, so do usuario. No Windows a pasta temporaria ja e do usuario (%LOCALAPPDATA%/Temp); no
    POSIX o /tmp e compartilhado: subpasta 0700 do usuario, e pasta alheia (dono, permissao, link) nao e usada:
    o motor monta numa pasta nova so desta execucao, para nunca abrir banco que outro usuario plantou."""
    base_dir = Path(base_dir or tempfile.gettempdir())
    if os.name != "posix":
        return base_dir
    pasta = base_dir.joinpath(f"consulta-reforma-{os.getuid()}")
    try:
        pasta.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = pasta.lstat()
    if pasta.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        # shortcut: sem reuso, cada execucao monta de novo (0,8 s) e deixa a pasta; limpar ao sair se o caso aparecer
        return Path(tempfile.mkdtemp(prefix="consulta-reforma-"))
    return pasta


def _uri_ro(caminho: Path) -> str:
    return caminho.resolve().as_uri() + "?mode=ro"  # as_uri trata espaco no caminho do Windows


def banco_confere(caminho: Path, versao_base: str) -> bool:
    if not caminho.is_file():
        return False
    try:
        con = sqlite3.connect(_uri_ro(caminho), uri=True)
        try:
            topo = con.execute("SELECT VRBD_VERSAO_BASE_DADO FROM VERSAO_BASE_DADO ORDER BY VRBD_ID DESC LIMIT 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return False
    return bool(topo) and str(topo[0]).upper() == versao_base.upper()


def montar(tabelas: Path, destino: Path, versao_base: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=destino.stem + "-", suffix=".tmp", dir=destino.parent)
    os.close(fd)
    tmp = Path(nome)
    try:
        con = sqlite3.connect(tmp)
        try:
            _aplicar(con, ordem_flyway(tabelas.joinpath("flyway-sql")))
            con.commit()
        finally:
            con.close()  # fechada antes de publicar: no Windows, arquivo aberto nao e renomeado
        try:
            os.replace(tmp, destino)
        except PermissionError:
            # outro processo publicou e mantem o destino aberto (Windows): reusa o dele, se conferir
            if not banco_confere(destino, versao_base):
                raise CacheInvalido()
    finally:
        tmp.unlink(missing_ok=True)


def sem_acento(texto):
    """Sem acento, sem caixa e com espacos colapsados (a busca compara termo e descricao assim)."""
    if texto is None:
        return None
    sem = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).casefold()
    return " ".join(sem.split())


def abrir(tabelas: Path = TABELAS, cache_dir: str | os.PathLike | None = None,
          versao_sqlite: str = sqlite3.sqlite_version) -> sqlite3.Connection:
    """Confere a copia, monta o banco na primeira vez (cache por manifesto) e abre so leitura."""
    manifesto = ler_manifesto(tabelas)
    conferir(tabelas, manifesto, versao_sqlite)
    destino = caminho_banco(manifesto, Path(cache_dir) if cache_dir else pasta_cache())
    if not banco_confere(destino, manifesto["versao_base"]):
        montar(tabelas, destino, manifesto["versao_base"])
    con = sqlite3.connect(_uri_ro(destino), uri=True)
    con.create_function("sem_acento", 1, sem_acento, deterministic=True)
    return con
