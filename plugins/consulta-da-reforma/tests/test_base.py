# -*- coding: utf-8 -*-
"""Montagem do banco (V2, V4, V7): integridade da copia, SQLite minimo, ordem do Flyway, cache e concorrencia."""
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

import base
from conftest import TABELAS

TAB = Path(TABELAS)


def _copia(tmp_path):
    destino = tmp_path.joinpath("tab")
    shutil.copytree(TAB, destino)
    return destino


def test_ordem_flyway():
    ordem = [p.name for p in base.ordem_flyway(TAB.joinpath("flyway-sql"))]
    assert len(ordem) == len(base.ler_manifesto(TAB)["arquivos"]) == len(set(ordem))
    assert ordem[0] == "beforeMigrate.sql" and ordem[1].startswith("B0001") and ordem[-1] == "afterMigrate.sql"
    assert ordem.index("V0010__estrutura_carga_tabelas_dfe.sql") > ordem.index("V0009__aliquota_uniforme_setorial.sql")


def test_manifesto_confere_com_a_copia():
    m = base.ler_manifesto(TAB)
    base.conferir(TAB, m)
    assert len(m["commit_sql"]) == 40 and m["arquivos"]  # o commit fixado e conferido contra a Receita pelo V2


def test_byte_alterado_recusa_sem_criar_banco(tmp_path):
    tab = _copia(tmp_path)
    alvo = tab.joinpath("flyway-sql", "manutencao", "V0059__habilitacao_820.sql")
    alvo.write_bytes(alvo.read_bytes() + b" ")
    cache = tmp_path.joinpath("cache")
    with pytest.raises(base.ArquivosDivergentes):
        base.abrir(tab, cache_dir=cache)
    assert not cache.exists() or not list(cache.iterdir())


def test_arquivo_a_mais_recusa(tmp_path):
    tab = _copia(tmp_path)
    tab.joinpath("flyway-sql", "manutencao", "V0060__intruso.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(base.ArquivosDivergentes):
        base.conferir(tab, base.ler_manifesto(tab))


def test_arquivo_faltando_recusa(tmp_path):
    tab = _copia(tmp_path)
    tab.joinpath("flyway-sql", "manutencao", "V0059__habilitacao_820.sql").unlink()
    with pytest.raises(base.ArquivosDivergentes):
        base.conferir(tab, base.ler_manifesto(tab))


def test_arquivo_do_sistema_nao_trava(tmp_path):
    tab = _copia(tmp_path)  # o Finder do macOS cria .DS_Store; o Explorer, Thumbs.db
    tab.joinpath("flyway-sql", ".DS_Store").write_bytes(b"\x00")
    tab.joinpath("flyway-sql", "manutencao", "Thumbs.db").write_bytes(b"\x00")
    base.conferir(tab, base.ler_manifesto(tab))


@pytest.mark.parametrize("versao, recusa", [("3.34.1", True), ("3.35.0", False), ("3.49.1", False)])
def test_sqlite_minimo(versao, recusa):
    if recusa:
        with pytest.raises(base.SqliteAntigo):
            base.conferir(TAB, base.ler_manifesto(TAB), versao)
    else:
        base.conferir(TAB, base.ler_manifesto(TAB), versao)


def test_segunda_abertura_reusa_o_cache(tmp_path):
    base.abrir(cache_dir=tmp_path).close()
    destino = base.caminho_banco(base.ler_manifesto(), tmp_path)
    antes = destino.stat().st_mtime_ns
    base.abrir(cache_dir=tmp_path).close()
    assert destino.stat().st_mtime_ns == antes


def test_publicacao_concorrente_com_destino_aberto(tmp_path):
    m = base.ler_manifesto()
    vencedor = base.abrir(cache_dir=tmp_path)  # mantem o destino aberto, como outro processo faria
    try:
        base.montar(TAB, base.caminho_banco(m, tmp_path), m["versao_base"])  # nao pode falhar
    finally:
        vencedor.close()
    assert not list(tmp_path.glob("*.tmp"))
    assert base.banco_confere(base.caminho_banco(m, tmp_path), m["versao_base"])


def test_destino_invalido_e_replace_falhando(tmp_path, monkeypatch):
    m = base.ler_manifesto()
    destino = base.caminho_banco(m, tmp_path)
    destino.write_bytes(b"nao e banco")

    def recusa(*_a):
        raise PermissionError()

    monkeypatch.setattr(base.os, "replace", recusa)
    with pytest.raises(base.CacheInvalido):
        base.montar(TAB, destino, m["versao_base"])
    assert not list(tmp_path.glob("*.tmp"))


def _atualizar():
    spec = importlib.util.spec_from_file_location("atualizar", TAB.joinpath("atualizar.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_atualizar_reproduz_o_manifesto():
    m = base.ler_manifesto()
    novo = _atualizar().gerar_manifesto(TAB.joinpath("flyway-sql"), m["commit_sql"], m["commit_head"],
                                        m["data_commit_sql"], m["data_copia"])
    assert novo == m


def test_atualizar_esvazia_antes_de_copiar(tmp_path, monkeypatch):
    mod = _atualizar()
    clone = tmp_path.joinpath("clone")
    shutil.copytree(TAB.joinpath("flyway-sql"), clone.joinpath("flyway", "sql"))
    clone.joinpath("flyway", "sql", "manutencao", "V0059__habilitacao_820.sql").unlink()  # a Receita apagou
    aqui = tmp_path.joinpath("tabelas")
    shutil.copytree(TAB.joinpath("flyway-sql"), aqui.joinpath("flyway-sql"))
    monkeypatch.setattr(mod, "AQUI", aqui)
    sha = "a" * 40
    assert mod.main([str(clone), "--commit-sql", sha, "--commit-head", sha, "--data-commit", "2026-12-01"]) == 0
    m = json.loads(aqui.joinpath("MANIFESTO.json").read_text(encoding="utf-8"))
    assert "manutencao/V0059__habilitacao_820.sql" not in m["arquivos"] and m["versao_base"] == "V0058"
    assert not aqui.joinpath("flyway-sql", "manutencao", "V0059__habilitacao_820.sql").exists()


def test_atualizar_recusa_sha_curto(tmp_path, monkeypatch):
    mod = _atualizar()
    monkeypatch.setattr(mod, "AQUI", tmp_path)
    assert mod.main([str(tmp_path), "--commit-sql", "8c538c9b", "--commit-head", "a" * 40,
                     "--data-commit", "2026-10-22"]) == 2
    assert not os.listdir(tmp_path)


def test_atualizar_copia_so_sql_e_preserva_a_copia_se_o_clone_e_invalido(tmp_path, monkeypatch):
    mod = _atualizar()
    clone = tmp_path.joinpath("clone")
    shutil.copytree(TAB.joinpath("flyway-sql"), clone.joinpath("flyway", "sql"))
    clone.joinpath("flyway", "sql", "manutencao", "README.md").write_text("nota", encoding="utf-8")
    aqui = tmp_path.joinpath("tabelas")
    shutil.copytree(TAB.joinpath("flyway-sql"), aqui.joinpath("flyway-sql"))
    monkeypatch.setattr(mod, "AQUI", aqui)
    sha = "b" * 40
    assert mod.main([str(clone), "--commit-sql", sha, "--commit-head", sha, "--data-commit", "2026-12-01"]) == 0
    assert not aqui.joinpath("flyway-sql", "manutencao", "README.md").exists()
    m = json.loads(aqui.joinpath("MANIFESTO.json").read_text(encoding="utf-8"))
    base.conferir(aqui, m)  # a copia nova confere com o manifesto novo
    antes = sorted(p.name for p in aqui.joinpath("flyway-sql").rglob("*.sql"))
    shutil.rmtree(clone.joinpath("flyway", "sql", "manutencao"))
    assert mod.main([str(clone), "--commit-sql", sha, "--commit-head", sha, "--data-commit", "2026-12-01"]) == 2
    assert sorted(p.name for p in aqui.joinpath("flyway-sql").rglob("*.sql")) == antes
    assert not aqui.joinpath("flyway-sql.novo").exists()


def test_chave_do_cache_inclui_o_motor():
    m = base.ler_manifesto()
    assert base.caminho_banco(m, "x") == base.caminho_banco(m, "x")
    assert base.caminho_banco(m, "x").name.startswith(f"consulta-reforma-{m['commit_sql'][:8]}-")


@pytest.mark.skipif(os.name != "posix", reason="no Windows a pasta temporaria ja e do usuario")
def test_pasta_cache_do_usuario(tmp_path):
    pasta = base.pasta_cache(tmp_path)
    assert pasta == tmp_path.joinpath(f"consulta-reforma-{os.getuid()}")
    assert pasta.stat().st_mode & 0o777 == 0o700
    assert base.pasta_cache(tmp_path) == pasta  # reusa a propria


@pytest.mark.skipif(os.name != "posix", reason="no Windows a pasta temporaria ja e do usuario")
def test_pasta_cache_aberta_a_outros_nao_e_usada(tmp_path):
    aberta = tmp_path.joinpath(f"consulta-reforma-{os.getuid()}")
    aberta.mkdir()
    aberta.chmod(0o777)
    outra = base.pasta_cache(tmp_path)
    assert outra != aberta and outra.name.startswith("consulta-reforma-")


@pytest.mark.skipif(os.name != "posix", reason="no Windows a pasta temporaria ja e do usuario")
def test_pasta_cache_que_e_link_nao_e_usada(tmp_path):
    alvo = tmp_path.joinpath("alvo")
    alvo.mkdir(mode=0o700)
    tmp_path.joinpath(f"consulta-reforma-{os.getuid()}").symlink_to(alvo, target_is_directory=True)
    assert base.pasta_cache(tmp_path) != tmp_path.joinpath(f"consulta-reforma-{os.getuid()}")


@pytest.mark.skipif(os.name == "posix", reason="so no Windows (trocar os.name quebraria o pathlib no Linux)")
def test_pasta_cache_no_windows_e_a_temporaria(tmp_path):
    assert base.pasta_cache(tmp_path) == tmp_path


def test_vigencias_da_base_sao_aaaa_mm_dd(con):
    # as consultas comparam vigencia como texto (BETWEEN); '2028-01-01 00:00:00' perderia o primeiro dia
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    ruins = []
    for tab in tabelas:
        for col in [c[1] for c in con.execute(f"PRAGMA table_info({tab})") if c[1].endswith("_VIGENCIA")]:
            ruins += con.execute(f"SELECT '{tab}.{col}', {col} FROM {tab} WHERE {col} IS NOT NULL "
                                 f"AND {col} NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchall()
    assert not ruins, ruins[:5]


def test_atualizar_falha_na_troca_devolve_a_copia_antiga(tmp_path, monkeypatch):
    # no Windows, arquivo aberto faz a troca falhar; a copia antiga volta inteira
    mod = _atualizar()
    clone = tmp_path.joinpath("clone")
    shutil.copytree(TAB.joinpath("flyway-sql"), clone.joinpath("flyway", "sql"))
    aqui = tmp_path.joinpath("tabelas")
    shutil.copytree(TAB.joinpath("flyway-sql"), aqui.joinpath("flyway-sql"))
    antes = sorted(p.relative_to(aqui).as_posix() for p in aqui.rglob("*.sql"))
    monkeypatch.setattr(mod, "AQUI", aqui)
    original = Path.rename

    def recusa_o_estagio(self, alvo):
        if self.name == "flyway-sql.novo":
            raise PermissionError("arquivo aberto")
        return original(self, alvo)

    monkeypatch.setattr(Path, "rename", recusa_o_estagio)
    sha = "c" * 40
    with pytest.raises(PermissionError):
        mod.main([str(clone), "--commit-sql", sha, "--commit-head", sha, "--data-commit", "2026-12-01"])
    assert sorted(p.relative_to(aqui).as_posix() for p in aqui.rglob("*.sql") if "flyway-sql.novo" not in p.parts) == antes
    assert not aqui.joinpath("flyway-sql.velho").exists()
