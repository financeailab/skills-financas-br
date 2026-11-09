# -*- coding: utf-8 -*-
"""Lote N:1 (conservador) + override de saldo do extrato.

Achados do teste com dado REAL (2026-06-15, docs/exemplos): o banco lanca UM debito
= SOMA de varios titulos do mesmo dia (ex.: Banco Exemplo, amortizacao + juros). E quirk de
banco que zera o LEDGERBAL (Bradesco/Santander/BB) -> amarracao precisa de saldo manual.

Guarda conservadora (decisao do owner): so forma lote quando os titulos do dia tem a
MESMA contraparte/CNPJ e somam EXATO. "Casar errado e pior que deixar pendente."

Rodar:  python tests/test_lote_e_saldo.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from reconcile import match_banco, resumo_privado          # noqa: E402
import conciliar                                            # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _raz(d, v, cnpj=None, nome="", doc=None):
    return {"data": d, "valor": Decimal(v), "doc": doc, "identificador": None,
            "contraparte": nome, "cpf_cnpj": cnpj, "descricao": nome}


def _ext(d, v, desc=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "descricao": desc,
            "contraparte": desc, "cpf_cnpj": None, "identificador": None}


D = date(2026, 3, 16)


@caso("lote: 2 titulos da MESMA contraparte/dia que somam o debito -> CONCILIADO_LOTE")
def _():
    ext = [_ext(D, "-78517.30", "LIQUIDACAO DE CONTRATO")]
    raz = [_raz(D, "-55000.00", "01233144000150", "BANCO EXEMPLO S A"),
           _raz(D, "-23517.30", "01233144000150", "BANCO EXEMPLO S A")]
    c = match_banco(ext, raz)
    st = [l.status for l in c.lancamentos if l.lado == "EXTRATO"]
    assert st == ["CONCILIADO_LOTE"], st
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 1, c.contagem
    assert c.contagem.get("PENDENTE_EXTRATO", 0) == 0, c.contagem
    assert c.contagem.get("PENDENTE_RAZAO", 0) == 0, c.contagem


@caso("lote expoe os componentes (titulos que somaram o debito) p/ o relatorio local")
def _():
    ext = [_ext(D, "-78517.30", "LIQUIDACAO DE CONTRATO")]
    raz = [_raz(D, "-55000.00", "01233144000150", "BANCO EXEMPLO S A"),
           _raz(D, "-23517.30", "01233144000150", "BANCO EXEMPLO S A")]
    c = match_banco(ext, raz)
    lote = [l for l in c.lancamentos if l.status == "CONCILIADO_LOTE"][0]
    assert sorted(lote.componentes) == [0, 1], lote.componentes


@caso("guarda conservadora: contrapartes DIFERENTES nao formam lote (anti falso-positivo)")
def _():
    ext = [_ext(D, "-100.00", "PAGAMENTO")]
    raz = [_raz(D, "-60.00", "11111111000111", "FORNECEDOR A"),
           _raz(D, "-40.00", "22222222000122", "FORNECEDOR B")]
    c = match_banco(ext, raz)
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 0, c.contagem
    assert c.contagem.get("PENDENTE_EXTRATO", 0) == 1, c.contagem
    assert c.contagem.get("PENDENTE_RAZAO", 0) == 2, c.contagem


@caso("lote respeita a janela: mesma contraparte/soma mas fora da janela nao casa")
def _():
    ext = [_ext(date(2026, 3, 20), "-100.00", "LIQUIDACAO")]
    raz = [_raz(date(2026, 3, 1), "-50.00", "01233144000150", "BANCO EXEMPLO S A"),
           _raz(date(2026, 3, 1), "-50.00", "01233144000150", "BANCO EXEMPLO S A")]
    c = match_banco(ext, raz, janela_dias=3)
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 0, c.contagem


@caso("lote nao rouba um match 1:1: titulo unico que casa exato continua CONCILIADO")
def _():
    # debito -50 casa 1:1 com o titulo -50; nao deve virar lote nem consumir os outros
    ext = [_ext(D, "-50.00", "PAGAMENTO")]
    raz = [_raz(D, "-50.00", "01233144000150", "BANCO EXEMPLO S A"),
           _raz(D, "-30.00", "01233144000150", "BANCO EXEMPLO S A")]
    c = match_banco(ext, raz)
    st = [l.status for l in c.lancamentos if l.lado == "EXTRATO"]
    assert st == ["CONCILIADO"], st
    assert c.contagem.get("PENDENTE_RAZAO", 0) == 1, c.contagem   # o -30 sobra


@caso("taxa_conciliacao conta o lote como conciliado")
def _():
    ext = [_ext(D, "-78517.30", "LIQ")]
    raz = [_raz(D, "-55000.00", "01233144000150", "EXEMPLO"),
           _raz(D, "-23517.30", "01233144000150", "EXEMPLO")]
    c = match_banco(ext, raz)
    r = resumo_privado(c)
    assert r["taxa_conciliacao_pct"] == 100.0, r["taxa_conciliacao_pct"]


# ---- override de saldo do extrato (quirk BALAMT=0) ----

@caso("saldo efetivo: BALAMT zerado sem override -> None + aviso")
def _():
    saldo, aviso = conciliar._saldo_extrato_efetivo(Decimal("0.00"), None)
    assert saldo is None, saldo
    assert aviso, "esperava aviso de saldo ausente/zerado"


@caso("saldo efetivo: override vence o BALAMT zerado")
def _():
    saldo, aviso = conciliar._saldo_extrato_efetivo(Decimal("0.00"), Decimal("1234.56"))
    assert saldo == Decimal("1234.56"), saldo
    assert not aviso, aviso


@caso("saldo efetivo: BALAMT real e usado quando nao ha override")
def _():
    saldo, aviso = conciliar._saldo_extrato_efetivo(Decimal("4126503.18"), None)
    assert saldo == Decimal("4126503.18"), saldo
    assert not aviso, aviso


@caso("saldo efetivo: BALAMT ausente (None) sem override -> None + aviso")
def _():
    saldo, aviso = conciliar._saldo_extrato_efetivo(None, None)
    assert saldo is None, saldo
    assert aviso, "esperava aviso de saldo ausente"


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
    print(f"==> LOTE + SALDO OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
