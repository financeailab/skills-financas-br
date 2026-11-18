# -*- coding: utf-8 -*-
"""Atualiza a copia embutida a partir de um clone de ReceitaFederal/calculadora-rtc-regime-regular.

    python atualizar.py <clone> --commit-sql <sha> --commit-head <sha> --data-commit AAAA-MM-DD

O clone tem de ser feito sem conversao de fim de linha (no Windows o Git troca LF por CRLF e o sha256 deixa de ser
o dos arquivos oficiais): git clone --config core.autocrlf=false <url> <clone>.
Os tres valores saem do clone (o script nao chama git):
    git -C <clone> log -1 --format=%H -- flyway/sql      -> --commit-sql
    git -C <clone> rev-parse HEAD                        -> --commit-head
    git -C <clone> log -1 --format=%cs -- flyway/sql     -> --data-commit
Esvazia tabelas/flyway-sql, copia os .sql de flyway/sql byte a byte e regrava MANIFESTO.json. Depois, rode a
suite do motor (o oraculo) antes de publicar a versao nova.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FONTE = "https://github.com/ReceitaFederal/calculadora-rtc-regime-regular"
LICENCA = "MIT, Copyright (c) 2026 Receita Federal do Brasil (texto em tabelas/LICENSE)"
_SHA = re.compile(r"[0-9a-f]{40}")
_NUM_V = re.compile(r"V(\d+)__")


def gerar_manifesto(sql: Path, commit_sql: str, commit_head: str, data_commit: str, hoje: str) -> dict:
    arquivos = {p.relative_to(sql).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(sql.rglob("*.sql"))}
    ultima = max(int(_NUM_V.match(Path(r).name).group(1)) for r in arquivos if _NUM_V.match(Path(r).name))
    return {"fonte": FONTE, "caminho": "flyway/sql", "commit_sql": commit_sql, "commit_head": commit_head,
            "data_commit_sql": data_commit, "data_copia": hoje, "versao_base": f"V{ultima:04d}",
            "licenca": LICENCA, "arquivos": arquivos}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atualizar.py")
    p.add_argument("clone")
    p.add_argument("--commit-sql", required=True)
    p.add_argument("--commit-head", required=True)
    p.add_argument("--data-commit", required=True)
    a = p.parse_args(argv)
    origem = Path(a.clone).joinpath("flyway", "sql")
    if not (_SHA.fullmatch(a.commit_sql) and _SHA.fullmatch(a.commit_head)):
        print("--commit-sql e --commit-head precisam do SHA completo (40 caracteres hexadecimais).")
        return 2
    try:
        datetime.date.fromisoformat(a.data_commit)
    except ValueError:
        print("--data-commit precisa ser AAAA-MM-DD.")
        return 2
    if not (origem.joinpath("criacao", "B0001__sistema_tributario_completo.sql").is_file()
            and origem.joinpath("manutencao").is_dir()):
        print("O clone nao tem flyway/sql/criacao/B0001__sistema_tributario_completo.sql e flyway/sql/manutencao/.")
        return 2
    destino, estagio = AQUI.joinpath("flyway-sql"), AQUI.joinpath("flyway-sql.novo")
    shutil.rmtree(estagio, ignore_errors=True)
    for sql in origem.rglob("*.sql"):  # so .sql: o manifesto e a conferencia do motor contam exatamente estes
        alvo = estagio.joinpath(sql.relative_to(origem))
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sql, alvo)  # bytes iguais aos do clone
    manifesto = gerar_manifesto(estagio, a.commit_sql, a.commit_head, a.data_commit,
                                datetime.date.today().isoformat())
    # a copia antiga so sai depois da nova completa: falha no meio nao deixa a skill sem tabelas. Ela sai por
    # rename, que no Windows recusa inteiro se um arquivo esta aberto (o rmtree apagava pela metade)
    velho = AQUI.joinpath("flyway-sql.velho")
    shutil.rmtree(velho, ignore_errors=True)
    if destino.exists():
        destino.rename(velho)
    try:
        estagio.rename(destino)
    except OSError:
        velho.rename(destino)  # devolve a copia antiga inteira
        raise
    shutil.rmtree(velho, ignore_errors=True)  # arquivo que a Receita apagou some da copia
    AQUI.joinpath("MANIFESTO.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")  # LF, a convencao do repo, tambem no Windows
    print(f"Copia atualizada: {len(manifesto['arquivos'])} arquivos, base {manifesto['versao_base']}. Rode a suite.")
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
