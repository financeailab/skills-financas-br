# -*- coding: utf-8 -*-
"""Adaptador opt-in: empurra o resumo AGREGADO da posicao p/ uma Google Sheet.

ISOLAMENTO (de proposito): o nucleo (posicao.py + o CSV local) NAO importa este
modulo. Ele so e chamado pelo CLI quando o usuario passa --sheet. Assim o contrato
de "roda local, sem rede" do produto vale por padrao; a Sheet e uma escolha explicita.

O QUE SOBE: so saldos por conta + total + status (o agregado). NUNCA a linha de
extrato. `montar_linhas_agregadas` e PURA e testavel; `push_para_sheet` faz rede e
falha com mensagem clara se a lib/credencial nao estiver configurada.
"""
from __future__ import annotations

from posicao import Consolidado, status_texto, _mascara_conta, banco_saida, tipo_saida


def montar_linhas_agregadas(cons: Consolidado) -> list:
    """Monta as linhas (list[list[str]]) que vao p/ a Sheet. Funcao PURA, sem rede.
    Cabecalho + 1 linha por conta (saldo) + linha de TOTAL + linha de STATUS.
    A Sheet e egress de rede (Google): o numero de conta vai MASCARADO e o nome de arquivo
    nao sobe (SPEC-06 #4/B1 — o fosso vale tambem aqui; o numero cheio fica so no posicao.csv LOCAL)."""
    linhas = [["arquivo", "banco", "conta", "tipo", "saldo_final", "data_saldo",
               "entra_no_caixa"]]
    for c in cons.contas:
        linhas.append([
            "", banco_saida(c.banco), _mascara_conta(c.conta),
            "cartao" if c.eh_cartao else tipo_saida(c.tipo_conta),
            (str(c.saldo_final) if c.saldo_final is not None else ""),
            (str(c.data_saldo) if c.data_saldo else ""),
            "sim" if c.entra_no_caixa else f"nao ({c.motivo_fora})",
        ])
    linhas.append([])
    linhas.append(["TOTAL EM CAIXA", "", "", "", str(cons.total_caixa), "", ""])
    if cons.saldo_minimo is not None:
        linhas.append(["SALDO MINIMO", "", "", "", str(cons.saldo_minimo), "", ""])
        linhas.append(["STATUS", "", "", "", status_texto(cons),
                       (str(cons.deficit) if cons.abaixo else ""), ""])
    return linhas


def push_para_sheet(linhas: list, documento_id: str, aba: str = "Posicao Consolidada",
                    escritor=None) -> str:
    """Escreve `linhas` na Sheet. `escritor` permite injetar um fake nos testes
    (qualquer callable (linhas, documento_id, aba) -> str). Sem `escritor`, tenta o
    caminho real via gspread e falha com mensagem clara se a lib/credencial faltar.
    """
    if escritor is not None:
        return escritor(linhas, documento_id, aba)

    try:
        import gspread  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "push p/ Google Sheet exige a lib 'gspread' (pip install gspread) + uma conta "
            "de servico Google configurada. O CSV local ja foi gerado; rode sem --sheet "
            "para ficar 100% offline."
        ) from e

    gc = gspread.service_account()                 # GOOGLE_APPLICATION_CREDENTIALS
    sh = gc.open_by_key(documento_id)
    try:
        ws = sh.worksheet(aba)
    except Exception:                              # noqa: BLE001 — aba nao existe -> cria
        ws = sh.add_worksheet(title=aba, rows=str(len(linhas) + 5), cols="8")
    ws.clear()
    ws.update("A1", linhas)
    return f"{aba} ({len(linhas)} linhas)"
