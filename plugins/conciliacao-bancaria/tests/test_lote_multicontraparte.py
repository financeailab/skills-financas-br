# -*- coding: utf-8 -*-
"""Lote MULTI-CONTRAPARTE por chave de remessa (SISPAG) + classificacao LOTE_SISPAG.

Achado do dado real (2026-06-15): os debitos pendentes do Itau sao remessas SISPAG
(MEMO "SISPAG FORNECEDORES") que somam titulos de fornecedores DIFERENTES. O numero da
remessa nao esta no relatorio de contas-a-pagar do Omie -> subset-sum cego e intratavel
(116/128 com >30 titulos/dia) E inseguro (subconjuntos ambiguos). Decisao de owner:

  A) coluna opcional `Lote`/`Remessa` no modelo -> o motor agrupa por (data, lote),
     multi-contraparte permitido porque a CHAVE explicita e o que garante o par.
  B) debito de lote nao-casado -> categoria de pendencia LOTE_SISPAG (honesto, nao casa).

Rodar:  python tests/test_lote_multicontraparte.py
"""
import os
import sys
from datetime import date
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
SCRIPTS = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts")
sys.path.insert(0, ENGINE)
sys.path.insert(0, SCRIPTS)

from reconcile import match_banco, classifica_pendencia      # noqa: E402
import conciliar                                             # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _raz(d, v, cnpj=None, nome="", lote=None):
    return {"data": d, "valor": Decimal(v), "doc": None, "identificador": None,
            "contraparte": nome, "cpf_cnpj": cnpj, "descricao": nome, "lote": lote}


def _ext(d, v, desc=""):
    return {"data": d, "valor": Decimal(v), "doc": None, "descricao": desc,
            "contraparte": desc, "cpf_cnpj": None, "identificador": None}


D = date(2026, 3, 16)


@caso("lote multi-contraparte casa pela chave de remessa (mesma Lote, contrapartes diferentes)")
def _():
    ext = [_ext(D, "-100.00", "SISPAG FORNECEDORES")]
    raz = [_raz(D, "-60.00", "11111111000111", "FORN A", lote="SISPAG-555"),
           _raz(D, "-40.00", "22222222000122", "FORN B", lote="SISPAG-555")]
    c = match_banco(ext, raz)
    st = [l.status for l in c.lancamentos if l.lado == "EXTRATO"]
    assert st == ["CONCILIADO_LOTE"], st
    assert c.contagem.get("PENDENTE_RAZAO", 0) == 0, c.contagem


@caso("remessa inteira (>2, multi-contraparte) soma o debito = CONCILIADO_LOTE")
def _():
    ext = [_ext(D, "-150.00", "SISPAG FORNECEDORES PIX")]
    raz = [_raz(D, "-60.00", "11111111000111", "A", lote="R9"),
           _raz(D, "-40.00", "22222222000122", "B", lote="R9"),
           _raz(D, "-50.00", "33333333000133", "C", lote="R9")]
    c = match_banco(ext, raz)
    lote = [l for l in c.lancamentos if l.status == "CONCILIADO_LOTE"]
    assert len(lote) == 1, [l.status for l in c.lancamentos if l.lado == "EXTRATO"]
    assert sorted(lote[0].componentes) == [0, 1, 2], lote[0].componentes


@caso("remessas DIFERENTES nao se misturam (chave de lote isola)")
def _():
    ext = [_ext(D, "-100.00", "SISPAG")]
    raz = [_raz(D, "-60.00", "11111111000111", "A", lote="R1"),
           _raz(D, "-40.00", "22222222000122", "B", lote="R2")]
    c = match_banco(ext, raz)
    assert c.contagem.get("CONCILIADO_LOTE", 0) == 0, c.contagem
    assert c.contagem.get("PENDENTE_EXTRATO", 0) == 1, c.contagem


@caso("coluna Remessa/Lote e detectada e canonizada no razao")
def _():
    linhas = [{"Data": "16/03/2026", "Valor": "-100,00", "Remessa": "SISPAG-555", "Contraparte": "X"}]
    cols = conciliar._detecta_colunas(list(linhas[0].keys()), {})
    regs, erros = conciliar._razao_canonico(linhas, cols)
    assert not erros, erros
    assert regs[0]["lote"] == "SISPAG-555", regs[0]


@caso("razao sem coluna Lote continua funcionando (lote = None)")
def _():
    linhas = [{"Data": "16/03/2026", "Valor": "-100,00", "Contraparte": "X"}]
    cols = conciliar._detecta_colunas(list(linhas[0].keys()), {})
    regs, erros = conciliar._razao_canonico(linhas, cols)
    assert not erros, erros
    assert regs[0]["lote"] is None, regs[0]


@caso("debito SISPAG nao-casado e classificado como LOTE_SISPAG (honesto, nao casa)")
def _():
    ext = [_ext(D, "-5000.00", "SISPAG FORNECEDORES")]
    c = match_banco(ext, [])
    l = [x for x in c.lancamentos if x.lado == "EXTRATO"][0]
    assert l.status == "PENDENTE_EXTRATO", l.status
    assert l.categoria == "LOTE_SISPAG", l.categoria


@caso("classifica_pendencia rotula marcadores de lote como LOTE_SISPAG")
def _():
    assert classifica_pendencia("EXTRATO", Decimal("-5000"), "SISPAG FORNECEDORES PIX") == "LOTE_SISPAG"
    assert classifica_pendencia("EXTRATO", Decimal("-100"), "PAG FORNECEDORES") == "LOTE_SISPAG"
    # nao confundir uma saida comum com lote
    assert classifica_pendencia("EXTRATO", Decimal("-100"), "COMPRA MERCADO") == "A_LANCAR"


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
    print(f"==> LOTE MULTI-CONTRAPARTE OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
