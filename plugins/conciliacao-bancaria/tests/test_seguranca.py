# -*- coding: utf-8 -*-
"""Regressao de seguranca (PRD-SAN-07 S-06): cap de 100 MB nos ingests do motor.

Arquivo acima de MAX_FILE_SIZE e recusado ANTES de carregar em memoria (anti-OOM),
com ValueError de mensagem clara — o orquestrador (conciliar.py) ja converte
excecao de parse em erro legivel ao operador. Usa monkeypatch de os.path.getsize
(nao cria arquivo gigante de verdade).

Rodar:  python tests/test_seguranca.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine"))

import ingest_ofx       # noqa: E402
import ingest_tabular   # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


TAMANHO_FALSO = 101 * 1024 * 1024  # 101 MB > cap de 100 MB


class _getsize_falso:
    """Context manager: monkeypatch manual de os.path.getsize (restaura sempre)."""

    def __enter__(self):
        self._orig = os.path.getsize
        os.path.getsize = lambda caminho: TAMANHO_FALSO
        return self

    def __exit__(self, *exc):
        os.path.getsize = self._orig
        return False


@caso("parse_ofx recusa arquivo > 100 MB antes de ler (S-06)")
def _():
    with _getsize_falso():
        try:
            ingest_ofx.parse_ofx("extrato-falso.ofx")  # nem precisa existir: recusa antes do open
            assert False, "parse_ofx aceitou arquivo de 101 MB"
        except ValueError as e:
            assert "100 MB" in str(e), e


@caso("read_csv recusa arquivo > 100 MB antes de ler (S-06)")
def _():
    with _getsize_falso():
        try:
            ingest_tabular.read_csv("razao-falsa.csv")
            assert False, "read_csv aceitou arquivo de 101 MB"
        except ValueError as e:
            assert "100 MB" in str(e), e


@caso("read_tabular (rota xlsx) recusa > 100 MB sem depender de openpyxl (S-06)")
def _():
    with _getsize_falso():
        try:
            ingest_tabular.read_tabular("razao-falsa.xlsx")
            assert False, "read_tabular aceitou xlsx de 101 MB"
        except ValueError as e:
            assert "100 MB" in str(e), e


MINI_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL
<BANKACCTFROM><BANKID>001<ACCTID>999</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20240301
<TRNAMT>-10.00
<FITID>S1
<MEMO>TESTE SEGURANCA
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>100.00<DTASOF>20240331</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""


@caso("regressao: arquivo pequeno continua aceito (OFX + CSV)")
def _():
    with tempfile.TemporaryDirectory() as td:
        ofx = os.path.join(td, "mini.ofx")
        with open(ofx, "w", encoding="ascii") as f:
            f.write(MINI_OFX)
        e = ingest_ofx.parse_ofx(ofx)
        assert len(e.transacoes) == 1, f"txns={len(e.transacoes)}"

        csv_path = os.path.join(td, "mini.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("Data;Valor\n01/03/2024;10,00\n")
        linhas = ingest_tabular.read_csv(csv_path)
        assert linhas and linhas[0]["Data"] == "01/03/2024", linhas


def main() -> int:
    falhas = []
    for nome, fn in casos:
        try:
            fn()
            print(f"  OK   {nome}")
        except AssertionError as e:
            falhas.append(f"{nome}: {e}")
            print(f"  XX   {nome}  -> {e}")
        except Exception as e:                       # noqa: BLE001
            falhas.append(f"{nome}: EXCECAO {e}")
            print(f"  XX   {nome}  -> EXCECAO {e}")
    print()
    if falhas:
        print("==> FALHOU:\n  - " + "\n  - ".join(falhas))
        return 1
    print(f"==> SEGURANCA OK: {len(casos)} casos (cap 100 MB + regressao).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
