# -*- coding: utf-8 -*-
"""Conciliacao Bancaria — orquestrador local (3 fases).

  Fase 1  validar    -> arquivos comparaveis? (parse, colunas, periodo) -> reprova -> PARA
  Fase 2  cruzar     -> casa lancamentos (match_banco), classifica 100%
  Fase 3  relatorio  -> Excel analitico (LOCAL) + resumo.json (o unico que sobe p/ a IA)

CONTRATO DE PRIVACIDADE (o fosso, PRD-F2-01 §5.7):
  Tudo aqui roda na maquina da analista. Nenhuma chamada de rede. O dado bruto
  (extrato/razao) NUNCA sai: o Excel fica no disco local; para a IA (Claude) so
  vai o resumo.json — contagens, totais e amarracao. Linha de extrato, jamais.

Uso:
  python conciliar.py validar   --extrato extrato.ofx --razao razao.csv
  python conciliar.py conciliar --extrato extrato.ofx --razao razao.csv \
                                --saldo-razao 12450.50 --out resultado
Determinismo: roda limpo numa pasta nova; nao se reescreve (teste de aceitacao §5.8).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))

from ingest_tabular import read_tabular       # noqa: E402
from normalize import parse_valor, parse_data, norm_doc, norm_cpf_cnpj, extrai_cpf_cnpj  # noqa: E402
from reconcile import match_banco, resumo_privado, ACAO_PENDENCIA  # noqa: E402
from posicao import varrer_pasta, consolidar_extratos, status_texto, resumo_agregado, _mascara_conta, banco_saida, tipo_saida, moeda_saida  # noqa: E402
from ingest_extrato import ingest_extrato, _STATUS_RANK, _FORMATO_RANK  # noqa: E402 (SPEC-01/04)

# CONTRATO DO RAZAO (decisao de owner 2026-06-02): formato ESPERADO unico, ver
# modelo-razao.csv. Nao tentamos suportar a variabilidade infinita de ERP — a pessoa
# arruma o razao no modelo (mapeamento unico dela). Aliases minimos so cobrem variacao
# de caixa/acento do cabecalho canonico; o resto usa --col-* como escape.
COLUNAS_MODELO = ("Data", "Valor", "Documento", "Identificador", "Contraparte", "CNPJ_CPF", "Historico", "Lote")
_ALIASES = {
    "data": ("data",),
    "valor": ("valor",),
    "doc": ("documento", "doc"),
    "ident": ("identificador", "e2e", "endtoend", "nsu", "nossonumero", "nosso numero"),
    "contraparte": ("contraparte", "fornecedor", "cliente", "favorecido", "beneficiario", "pagador"),
    "cpfcnpj": ("cnpj_cpf", "cpf_cnpj", "cnpj", "cpf", "cnpjcpf", "documento fiscal"),
    "desc": ("historico", "descricao"),
    # lote/remessa: liga titulos de fornecedores DIFERENTES pagos numa remessa unica
    # (Itau SISPAG e equivalentes) -> conciliacao N:1 multi-contraparte sem subset-sum.
    "lote": ("lote", "remessa", "sispag", "numero remessa", "nº remessa", "no remessa", "id lote"),
}


# marca `conferir` (D9/D10c): motivo FIXO -> texto fixo, sem dado do arquivo; o par conta como conciliado
_CONFERIR_ACAO = {"cpf_cnpj": "conferir: CPF/CNPJ do banco diferente do razao",
                  "lote_valores_iguais": "conferir: lote com titulos de mesmo valor (confira quais)"}


def _rotulo_conferir(l):
    """(categoria, acao_sugerida) da linha p/ o Excel: pendencia, ou conciliada que o operador deve conferir
    (ambigua do SPEC-07 #4 e/ou marca `conferir`)."""
    acoes = (["conferir: mesmo valor/data sem documento ou identificador"] if l.ambiguo else []) + [
        _CONFERIR_ACAO[m] for m in l.conferir]
    cat = l.categoria or ("AMBÍGUO" if l.ambiguo else "CONFERIR" if l.conferir else "")
    return cat, (ACAO_PENDENCIA.get(l.categoria, "") or "; ".join(acoes))


def _detecta_colunas(headers: list[str], overrides: dict) -> dict:
    achadas = {}
    low = {h.lower().strip(): h for h in headers}
    for chave, aliases in _ALIASES.items():
        if overrides.get(chave):
            achadas[chave] = overrides[chave]
            continue
        for a in aliases:
            if a in low:
                achadas[chave] = low[a]
                break
    return achadas


def _razao_canonico(linhas: list[dict], cols: dict) -> tuple[list[dict], list[str]]:
    """Converte a razao linha-a-linha. Linha ruim (data/valor invalido — ex.: subtotal
    de ERP) NAO derruba o run: vira erro contabilizado. Retorna (registros, erros).
    Erro = "linha N, coluna <data|valor>: <codigo>"; so numero de linha e codigo, nunca a celula
    (o stdout e o canal que a IA le). Codigos: data_vazia|data_invalida|valor_vazio|valor_invalido|coluna_ausente."""
    def val(r, chave):
        c = cols.get(chave)
        return r.get(c) if c else None

    def campo(r, chave, vazio, invalido, conv):
        """-> (valor, codigo|None). KeyError = coluna_ausente; vazio apos strip = *_vazia; excecao do parser = *_invalida."""
        try:
            raw = r[cols[chave]]
        except KeyError:
            return None, "coluna_ausente"
        if not str(raw if raw is not None else "").strip():
            return None, vazio
        try:
            return conv(raw), None
        except (ValueError, ArithmeticError):      # ArithmeticError: >28 digitos (quantize)
            return None, invalido

    def txt(r, chave):
        """Celula opcional como texto: xlsx entrega int/float/datetime, nao so str."""
        v = val(r, chave)
        return "" if v is None else str(v).strip()

    out, erros = [], []
    for i, r in enumerate(linhas, start=2):  # linha 2 = 1a de dados (linha 1 = header)
        data, e_data = campo(r, "data", "data_vazia", "data_invalida", parse_data)
        valor, e_valor = campo(r, "valor", "valor_vazio", "valor_invalido", lambda x: parse_valor(x, origem="br"))  # razao BR: ponto pode ser milhar
        if e_data or e_valor:
            erros.append(f"linha {i}, " + "; ".join(f"coluna {n}: {cod}" for n, cod in (("data", e_data), ("valor", e_valor)) if cod))
            continue
        contraparte = txt(r, "contraparte")
        out.append({
            "data": data,
            "valor": valor,
            "doc": norm_doc(val(r, "doc")),
            "identificador": txt(r, "ident") or None,
            "contraparte": contraparte,
            # CNPJ/CPF: coluna propria, com fallback de extrair da contraparte
            "cpf_cnpj": norm_cpf_cnpj(val(r, "cpfcnpj")) or extrai_cpf_cnpj(contraparte),
            "descricao": txt(r, "desc"),
            "lote": txt(r, "lote") or None,  # remessa p/ lote N:1 multi-contraparte
        })
    return out, erros


def _linhas_invalidas(erros: list[str]) -> list[int]:
    """Numeros de linha dos erros de _razao_canonico (prefixo 'linha N')."""
    return [int(re.match(r"linha (\d+)", e).group(1)) for e in erros]


def _saldo_extrato_efetivo(ext_saldo, override):
    """Decide o saldo do extrato p/ a amarracao. Alguns bancos (Bradesco/Santander/BB)
    exportam LEDGERBAL=0 -> tratamos 0/ausente como 'nao informado' e pedimos o saldo
    manual. Retorna (saldo|None, aviso|None)."""
    if override is not None:
        return override, None
    if ext_saldo is None or ext_saldo == Decimal("0.00"):
        return None, ("saldo final do extrato ausente ou zerado no OFX (alguns bancos como "
                      "Bradesco/Santander/BB nao preenchem o LEDGERBAL). Informe "
                      "--saldo-extrato VALOR para validar a amarracao.")
    return ext_saldo, None


def _msg_sem_transacoes(ext) -> str:
    """Mensagem clara do PORQUE o extrato nao rendeu transacoes, pelo status do ingest multiformato
    (SPEC-06 #1/A2: nada de 'OFX invalido' num CSV/XLSX valido)."""
    return {
        "PRECISA_OCR": "extrato em imagem/PDF escaneado: use a jornada `pasta` com --ocr (Tesseract local).",
        "MAPEAR_COLUNAS": ("layout do extrato nao reconhecido (nao achei colunas de data/valor). "
                           "Exporte em OFX (preferencia) ou CSV/XLSX no padrao do banco."),
        "CORROMPIDO": f"arquivo de extrato ilegivel/corrompido ({ext.aviso or 'sem detalhe'}).",
    }.get(ext.status, "extrato sem transacoes legiveis (confira o arquivo; OFX e o formato mais seguro).")


def fase1_validar(extrato_path: str, razao_path: str, overrides: dict) -> tuple[bool, dict]:
    """Retorna (aprovado, metadados). Metadados sao agregados (seguros p/ a IA)."""
    diag = {"reprovas": [], "avisos": []}

    if not os.path.exists(extrato_path):
        return False, {"erro": f"extrato nao encontrado: {extrato_path}"}
    if not os.path.exists(razao_path):
        return False, {"erro": f"razao nao encontrada: {razao_path}"}

    ext = ingest_extrato(extrato_path)   # multiformato OFX/CSV/XLSX/XLS/PDF (SPEC-06 #1/A2; nunca lanca)
    if ext.n_contas > 1:
        diag["reprovas"].append(
            f"o extrato tem {ext.n_contas} contas (conta corrente + cartao/poupanca?). "
            f"Exporte e concilie UMA conta por vez — misturar contas falsearia a amarracao.")
    if not ext.transacoes:
        diag["reprovas"].append(_msg_sem_transacoes(ext))
    if ext.txns_corrompidas:
        diag["avisos"].append(f"{ext.txns_corrompidas} transacao(oes) do extrato ignorada(s) por data/valor invalido")

    try:
        linhas = read_tabular(razao_path)
    except Exception as e:                                  # noqa: BLE001 — razao ilegivel degrada com msg (SPEC-06 #3)
        diag["reprovas"].append(
            f"nao consegui ler a razao ({type(e).__name__}): corrompida, aberta no Excel, ou formato "
            f"invalido. Salve a razao como CSV no modelo (modelo-razao.csv).")
        return False, diag
    if not linhas:
        diag["reprovas"].append("razao vazia ou ilegivel")
        return False, diag
    cols = _detecta_colunas(list(linhas[0].keys()), overrides)
    for obrig in ("data", "valor"):
        if obrig not in cols:
            diag["reprovas"].append(
                f"coluna obrigatoria nao detectada na razao: '{obrig}'. "
                f"Razao esperado no formato do modelo {list(COLUNAS_MODELO)} "
                f"(ver modelo-razao.csv; ';' como separador, valor com sinal +entrada/-saida). "
                f"Recebi {len(linhas[0])} coluna(s) no arquivo. "
                f"Reformate no modelo ou use --col-{obrig}.")
    if "doc" not in cols:
        diag["avisos"].append("sem coluna de documento na razao: matching cai p/ valor+data")

    metad = {"colunas_detectadas": cols}
    if ext.transacoes:
        datas_e = [t["data"] for t in ext.transacoes]
        metad["extrato"] = {
            "banco": banco_saida(ext.banco), "conta": _mascara_conta(ext.conta),   # tag do arquivo: so o validado sai
            "tipo": tipo_saida(ext.tipo_conta), "moeda": moeda_saida(ext.moeda),
            "transacoes": len(ext.transacoes),
            "creditos": sum(1 for t in ext.transacoes if t["valor"] > 0),
            "debitos": sum(1 for t in ext.transacoes if t["valor"] < 0),
            "periodo": [str(min(datas_e)), str(max(datas_e))],
            "tem_saldo_final": ext.saldo_final is not None,
        }
    if "data" in cols and "valor" in cols and not diag["reprovas"]:
        razao, erros = _razao_canonico(linhas, cols)
        if erros:
            amostra = "; ".join(erros[:5]) + (f" (+{len(erros) - 5})" if len(erros) > 5 else "")
            diag["reprovas"].append(
                f"{len(erros)} linha(s) da razao nao parseavel(is) (ex.: subtotal/rodape, "
                f"valor vazio, data invalida): {amostra}. Remova-as ou corrija no modelo.")
        elif razao:
            datas_r = [r["data"] for r in razao]
            metad["razao"] = {"linhas": len(razao), "periodo": [str(min(datas_r)), str(max(datas_r))]}
            if ext.transacoes:
                e0, e1 = min(datas_e), max(datas_e)
                r0, r1 = min(datas_r), max(datas_r)
                if e1 < r0 or r1 < e0:
                    diag["avisos"].append("periodos de extrato e razao nao se sobrepoem — confira os arquivos")
        else:
            diag["reprovas"].append("razao sem linhas validas apos a normalizacao")

    metad.update(diag)
    aprovado = not diag["reprovas"]
    return aprovado, metad


def conciliar(extrato_path, razao_path, saldo_razao, out_dir, overrides, janela, tolerancia,
              saldo_extrato_override=None):
    aprovado, metad = fase1_validar(extrato_path, razao_path, overrides)
    print("== FASE 1 — VALIDACAO ==")
    print(json.dumps(metad, ensure_ascii=False, indent=2, default=str))
    if not aprovado:
        print("\n[REPROVADO] corrija os itens acima antes de cruzar. Nada foi conciliado.")
        return 2

    ext = ingest_extrato(extrato_path)   # multiformato (SPEC-06 #1/A2); Fase 1 ja garantiu transacoes legiveis
    cols = metad["colunas_detectadas"]
    razao, _erros = _razao_canonico(read_tabular(razao_path), cols)  # Fase 1 ja garantiu sem erros

    saldo_ext, aviso_saldo = _saldo_extrato_efetivo(ext.saldo_final, saldo_extrato_override)

    print("\n== FASE 2 — CRUZAMENTO ==")
    c = match_banco(
        ext.transacoes, razao,
        tolerancia=tolerancia, janela_dias=janela,
        saldo_extrato_final=saldo_ext,
        saldo_razao_final=saldo_razao,
    )
    for status, qtd in sorted(c.contagem.items()):
        print(f"  {status:<28} {qtd}")

    # a "cauda" que nao fecha, explicada por categoria + acao
    resumo_tmp = resumo_privado(c)
    if resumo_tmp.get("conciliados_ambiguos"):           # SPEC-07 #4
        print(f"\n  [!] {resumo_tmp['conciliados_ambiguos']} conciliacao(oes) AMBIGUA(s): mesmo valor/data sem "
              f"documento ou identificador p/ desempatar -> casei o par mais provavel, mas CONFIRA no Excel "
              f"(pode ter trocado lancamentos de mesmo valor).")
    if resumo_tmp.get("conferir_cpf_cnpj"):               # D9
        print(f"\n  [!] {resumo_tmp['conferir_cpf_cnpj']} conciliacao(oes) com CPF/CNPJ do banco diferente do razao "
              f"(confira no Excel)")
    if resumo_tmp.get("conferir_lote_valores_iguais"):    # D10c
        print(f"\n  [!] {resumo_tmp['conferir_lote_valores_iguais']} lote(s) com titulos de mesmo valor "
              f"(confira quais titulos no Excel)")
    pend_cat = resumo_tmp.get("pendencias_por_categoria") or {}
    if pend_cat:
        print("\n  pendencias por categoria (a cauda):")
        for cat, info in pend_cat.items():
            print(f"    {cat:<24} {info['qtd']:>3}  -> {info['acao']}")

    # controle agregado do lote (SISPAG sem nº de remessa): bate no agregado?
    cl = resumo_tmp.get("controle_lote")
    if cl:
        print("\n  controle de lote (SISPAG — sem nº de remessa no razao p/ parear):")
        print(f"    debitos de lote no banco : {cl['qtd_debitos_lote']:>4}  total {cl['total_debitos_lote']}")
        print(f"    titulos de saida pendentes: {cl['qtd_titulos_pendentes']:>4}  total {cl['total_titulos_pendentes']}")
        print(f"    diferenca (banco - razao) : {cl['diferenca']}  (≈0 = lotes batem no agregado; confira a remessa p/ o detalhe)")

    print("\n== FASE 3 — RELATORIO ==")
    os.makedirs(out_dir, exist_ok=True)
    resumo = resumo_privado(c)
    resumo_path = os.path.join(out_dir, "resumo.json")
    with open(resumo_path, "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    try:
        rel_path = _escreve_relatorio(c, out_dir)
    except Exception as e:                               # noqa: BLE001 - so o tipo sobe: a mensagem pode trazer a descricao
        rel_path = f"relatorio nao gravado ({type(e).__name__})"

    if c.amarracao:
        estado = "FECHA (integridade OK)" if c.integridade_ok else f"NAO FECHA (residuo {c.amarracao['residuo']})"
        print(f"  amarracao: {estado}")
    elif aviso_saldo:
        print(f"  amarracao: nao calculada ({aviso_saldo})")
    print(f"  resumo (p/ IA): {resumo_path}")
    print(f"  relatorio (LOCAL, dado bruto): {rel_path}")
    if not c.integridade_ok:
        diag = (c.amarracao or {}).get("diagnostico") or {}
        print(f"\n[ATENCAO] a amarracao nao fechou (residuo {c.amarracao['residuo']}).")
        if diag:
            print(f"  causa provavel: {diag.get('causa_provavel')}")
            print(f"  {diag.get('acao')}")
        else:
            print("  investigar antes de confiar no relatorio.")
        return 3
    return 0


# Paleta on-brand do relatorio (Finance AI Lab, light-first esmeralda) — ARGB p/ openpyxl.
_COR = {
    "emerald": "FF047857", "emerald2": "FF10B981", "teal": "FF0E7490",
    "wash": "FFE7F6EF", "ink": "FF1A1A18", "mut": "FF6B6A64", "line": "FFE6E4DD",
    "amber": "FFB45309", "amberbg": "FFFEF6E7", "gray": "FF6B7280", "zebra": "FFF7F6F2",
    "white": "FFFFFFFF", "canvas": "FFFAF9F6",
}
_STATUS_COR = {
    "CONCILIADO": "FF047857", "CONCILIADO_COM_DIFERENCA": "FF10B981", "CONCILIADO_LOTE": "FF0E7490",
    "PENDENTE_EXTRATO": "FFB45309", "PENDENTE_RAZAO": "FF6B7280",
}
# rotulo amigavel por status (cabecalho das abas / capa)
_STATUS_ROTULO = {
    "CONCILIADO": "Conciliado", "CONCILIADO_COM_DIFERENCA": "Conciliado (diferenca de centavos)",
    "CONCILIADO_LOTE": "Conciliado em lote (N:1)", "PENDENTE_EXTRATO": "Pendente no extrato (lancar no razao)",
    "PENDENTE_RAZAO": "Pendente no razao (aguardando banco)",
}
_BRL_FMT = 'R$ #,##0.00;[Red]-R$ #,##0.00'


def _txt_csv(v):
    """D17: texto do arquivo que o Excel leria como formula ganha o apostrofo (CSV). So campos de texto."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _escreve_relatorio(c, out_dir):
    """Relatorio analitico LOCAL: Excel branded (se openpyxl) ou CSV (fallback).
    O Excel tem uma CAPA visual (KPIs + amarracao + status + pendencias) e uma aba por
    status com header esmeralda, valores em BRL, zebra e painel congelado. Fica na maquina."""
    grupos: dict = {}
    for l in c.lancamentos:
        grupos.setdefault(l.status, []).append(l)

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        import csv
        path = os.path.join(out_dir, "conciliacao_por_status.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["status", "lado", "data", "valor", "doc", "descricao",
                        "categoria", "acao_sugerida", "diferenca", "lag_dias"])
            for l in c.lancamentos:
                r = l.registro
                # SPEC-07 #4: o marcador de ambiguidade tambem no CSV-fallback (ambiente sem openpyxl)
                cat_txt, acao_txt = _rotulo_conferir(l)
                w.writerow([l.status, l.lado, r.get("data"), r.get("valor"),
                            _txt_csv(r.get("doc")), _txt_csv(r.get("descricao")),
                            cat_txt, acao_txt, l.diferenca, l.lag_dias])
        return path

    def _fill(hexv):
        return PatternFill("solid", fgColor=hexv)
    thin = Side(style="thin", color=_COR["line"])
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    res = resumo_privado(c)
    F = lambda **k: Font(name="Calibri", **k)

    wb = openpyxl.Workbook()
    cap = wb.active
    cap.title = "Resumo"
    cap.sheet_view.showGridLines = False
    cap.sheet_properties.tabColor = _COR["emerald"][2:]
    for col, wid in (("A", 2.5), ("B", 30), ("C", 24), ("D", 52)):
        cap.column_dimensions[col].width = wid

    # --- cabecalho ---
    cap["B2"] = "Conciliação Bancária"
    cap["B2"].font = F(bold=True, size=20, color=_COR["ink"])
    cap["C3"] = "Relatório gerado localmente · Finance AI Lab"
    cap.merge_cells("B3:D3")
    cap["B3"] = "Relatório gerado localmente · Finance AI Lab"
    cap["B3"].font = F(size=10, italic=True, color=_COR["mut"])
    # regua esmeralda
    for col in ("B", "C", "D"):
        cap[f"{col}4"].fill = _fill(_COR["emerald"])
    cap.row_dimensions[4].height = 4

    ln = 6

    def _kicker(texto):
        nonlocal ln
        cap.cell(ln, 2, texto).font = F(bold=True, size=9, color=_COR["emerald"])
        ln += 1

    def _kv(rotulo, valor, destaque=False, cor=None):
        nonlocal ln
        a = cap.cell(ln, 2, rotulo); a.font = F(size=10, color=_COR["mut"])
        b = cap.cell(ln, 3, valor)
        b.font = F(bold=destaque, size=13 if destaque else 10, color=cor or _COR["ink"])
        ln += 1

    # --- KPIs ---
    _kicker("VISÃO GERAL")
    _kv("Taxa de conciliação", f'{res["taxa_conciliacao_pct"]}%', destaque=True, cor=_COR["emerald"])
    _kv("Registros analisados", res["registros"])
    _kv("Total do extrato", _brl(c.total_esquerdo))
    _kv("Total do razão", _brl(c.total_direito))
    _kv("Diferença global", _brl(c.diferenca_global))
    ln += 1

    # --- amarracao (banner) ---
    if c.amarracao:
        fecha = c.integridade_ok
        cor = _COR["emerald"] if fecha else _COR["amber"]
        bg = _COR["wash"] if fecha else _COR["amberbg"]
        txt = "AMARRAÇÃO FECHA — integridade OK" if fecha else f'AMARRAÇÃO NÃO FECHA — resíduo {c.amarracao["residuo"]}'
        cap.merge_cells(f"B{ln}:D{ln}")
        cell = cap.cell(ln, 2, txt)
        cell.font = F(bold=True, size=11, color=cor)
        cell.fill = _fill(bg)
        cell.alignment = Alignment(vertical="center", indent=1)
        cap.row_dimensions[ln].height = 22
        ln += 1
        diag = c.amarracao.get("diagnostico")
        if diag and not fecha:
            cap.merge_cells(f"B{ln}:D{ln}")
            d = cap.cell(ln, 2, f'Causa provável: {diag.get("causa_provavel")} — {diag.get("acao","")}')
            d.font = F(size=9, italic=True, color=_COR["ink"]); d.alignment = Alignment(wrap_text=True, vertical="top")
            cap.row_dimensions[ln].height = 30
            ln += 1
        ln += 1

    # --- contagem por status ---
    _kicker("CONTAGEM POR STATUS")
    for st in sorted(c.contagem.keys()):
        qtd = c.contagem[st]
        chip = cap.cell(ln, 2, _STATUS_ROTULO.get(st, st))
        chip.font = F(bold=True, size=10, color=_COR["white"])
        chip.fill = _fill(_STATUS_COR.get(st, _COR["gray"]))
        chip.alignment = Alignment(indent=1, vertical="center")
        q = cap.cell(ln, 3, qtd); q.font = F(bold=True, size=11, color=_COR["ink"])
        cap.row_dimensions[ln].height = 18
        ln += 1
    ln += 1

    # --- pendencias por categoria (com acao) ---
    pend = res.get("pendencias_por_categoria") or {}
    if pend:
        _kicker("PENDÊNCIAS POR CATEGORIA — O QUE FAZER")
        h = ["Categoria", "Qtd", "Ação sugerida"]
        for j, t in enumerate(h):
            cc = cap.cell(ln, 2 + j, t)
            cc.font = F(bold=True, size=9, color=_COR["white"]); cc.fill = _fill(_COR["ink"])
            cc.alignment = Alignment(indent=1)
        ln += 1
        for cat, info in pend.items():
            cap.cell(ln, 2, cat).font = F(size=10, color=_COR["ink"])
            cap.cell(ln, 3, info.get("qtd")).font = F(size=10)
            ac = cap.cell(ln, 4, info.get("acao", "")); ac.font = F(size=10, color=_COR["mut"])
            ac.alignment = Alignment(wrap_text=True, vertical="top")
            if (ln % 2) == 0:
                for col in (2, 3, 4):
                    cap.cell(ln, col).fill = _fill(_COR["zebra"])
            ln += 1
        ln += 1

    # --- controle de lote (se houver) ---
    cl = res.get("controle_lote")
    if cl:
        _kicker("CONTROLE DE LOTE (SISPAG) — agregado")
        _kv("Débitos de lote (banco)", f'{cl["qtd_debitos_lote"]} · {_brl(Decimal(cl["total_debitos_lote"]))}')
        _kv("Títulos pendentes (razão)", f'{cl["qtd_titulos_pendentes"]} · {_brl(Decimal(cl["total_titulos_pendentes"]))}')
        _kv("Diferença (≈0 = bate)", _brl(Decimal(cl["diferenca"])))
        ln += 1

    # --- rodape (fosso) ---
    cap.merge_cells(f"B{ln}:D{ln}")
    foot = cap.cell(ln, 2, "Detalhe linha a linha nas abas por status. Tudo gerado na sua máquina — nenhum dado subiu para a internet.")
    foot.font = F(size=8, italic=True, color=_COR["mut"]); foot.alignment = Alignment(wrap_text=True)
    cap.row_dimensions[ln].height = 24

    # --- abas por status ---
    COLS = [("Lado", 10), ("Data", 13), ("Valor", 15), ("Documento", 16),
            ("Descrição", 40), ("Categoria", 22), ("Ação sugerida", 34),
            ("Diferença", 13), ("Lag (dias)", 11)]
    ordem = [s for s in _STATUS_ROTULO if s in grupos] + [s for s in grupos if s not in _STATUS_ROTULO]
    for status in ordem:
        items = grupos[status]
        ws = wb.create_sheet(status[:31])
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = _STATUS_COR.get(status, _COR["gray"])[2:]
        # titulo + header
        ws.merge_cells("A1:I1")
        t = ws.cell(1, 1, f'{_STATUS_ROTULO.get(status, status)}  ·  {len(items)} lançamento(s)')
        t.font = F(bold=True, size=12, color=_COR["white"]); t.fill = _fill(_STATUS_COR.get(status, _COR["gray"]))
        t.alignment = Alignment(indent=1, vertical="center"); ws.row_dimensions[1].height = 22
        for j, (nome, wid) in enumerate(COLS, start=1):
            cc = ws.cell(2, j, nome)
            cc.font = F(bold=True, size=10, color=_COR["white"]); cc.fill = _fill(_COR["emerald"])
            cc.alignment = Alignment(indent=1); cc.border = box
            ws.column_dimensions[get_column_letter(j)].width = wid
        for i, l in enumerate(items):
            r = l.registro
            row = 3 + i
            # SPEC-07 #4: marca a linha conciliada AMBIGUA (mesmo valor sem identificador) p/ o operador conferir
            cat_txt, acao_txt = _rotulo_conferir(l)
            vals = [l.lado, str(r.get("data") or ""), float(r.get("valor") or 0),
                    r.get("doc") or "", r.get("descricao") or "", cat_txt,
                    acao_txt, float(l.diferenca or 0), l.lag_dias or 0]
            for j, v in enumerate(vals, start=1):
                cc = ws.cell(row, j, v)
                if isinstance(v, str):
                    cc.data_type = "s"      # D17: texto do arquivo nunca vira formula
                cc.font = F(size=10, color=_COR["ink"]); cc.border = box
                if j in (3, 8):  # valor, diferenca
                    cc.number_format = _BRL_FMT; cc.alignment = Alignment(horizontal="right")
                elif j == 9:
                    cc.alignment = Alignment(horizontal="center")
                else:
                    cc.alignment = Alignment(indent=1, wrap_text=(j == 5))
            if (i % 2) == 1:
                for j in range(1, 10):
                    ws.cell(row, j).fill = _fill(_COR["zebra"])
        ws.freeze_panes = "A3"

    path = os.path.join(out_dir, "conciliacao.xlsx")
    wb.save(path)
    return path


def _brl(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cmd_posicao(pasta, saldo_minimo, out_dir, forcar_conta, sheet_id, aba):
    """Modo posicao: varre a pasta de OFX, consolida o caixa, devolve o status.
    CSV local + resumo.json agregado (sempre); push p/ Sheet so com --sheet (opt-in)."""
    if not os.path.isdir(pasta):
        print(f"pasta nao encontrada: {pasta}")
        return 2

    parsed = varrer_pasta(pasta)
    if not parsed:
        print(f"nenhum arquivo .ofx em {pasta}")
        return 2

    cons = consolidar_extratos(parsed, saldo_minimo=saldo_minimo, forcar_conta=forcar_conta)

    print("== POSICAO DE CAIXA CONSOLIDADA ==")
    # nome de arquivo NAO vai ao stdout (canal da IA): banco + conta mascarada; o nome fica no posicao.csv local
    print(f"{'banco':<8}{'conta':<10}{'tipo':<9}{'saldo':>16}{'caixa?':>8}")
    print("-" * 51)
    for c in cons.contas:
        tipo = "cartao" if c.eh_cartao else tipo_saida(c.tipo_conta)
        marca = "sim" if c.entra_no_caixa else f"nao"
        print(f"{banco_saida(c.banco):<8}{_mascara_conta(c.conta):<10}{tipo:<9}{_brl(c.saldo_final):>16}{marca:>8}")
    print("-" * 51)
    print(f"contas no caixa: {cons.n_caixa} | cartoes (fora): {cons.n_cartoes} | "
          f"sem saldo: {cons.n_sem_saldo} | multi-conta: {cons.n_multi_conta} | erros: {len(cons.erros)}")
    print(f"TOTAL EM CAIXA: {_brl(cons.total_caixa)}")
    if saldo_minimo is not None:
        st = status_texto(cons)
        extra = f" (deficit {_brl(cons.deficit)})" if cons.abaixo else ""
        print(f"SALDO MINIMO:   {_brl(saldo_minimo)}")
        print(f"STATUS: {st}{extra}")
    if cons.n_cartoes:
        cart = ", ".join(f"{banco_saida(c.banco)} {_mascara_conta(c.conta)}"
                         for c in cons.contas if c.eh_cartao and not c.entra_no_caixa)
        print(f"\n[i] Cartoes fora do caixa (envelope de cartao): {cart}")
        print("    Se algum for conta (ex.: NuConta), inclua com --forcar-conta nome.ofx;"
              " o nome do arquivo esta no posicao.csv local")
    if cons.n_outra_moeda:
        moedas = ", ".join(sorted({moeda_saida(c.moeda) for c in cons.contas if c.motivo_fora == "moeda"}))
        print(f"[i] {cons.n_outra_moeda} conta(s) em outra moeda fora do caixa: {moedas}")
    if cons.n_repetidas_conflito:
        print(f"[!] {cons.n_repetidas_conflito} conta(s) repetida(s) com saldos diferentes")
        print("    A mesma conta veio em mais de um arquivo com saldos diferentes na data mais recente;"
              " nenhuma entrou no caixa. Deixe so a exportacao certa na pasta.")
    if cons.n_multi_conta:
        print(f"[!] {cons.n_multi_conta} arquivo(s) com mais de uma conta fora do caixa: exporte uma conta por arquivo")
    if cons.erros:
        print(f"[!] {len(cons.erros)} arquivo(s) ilegiveis (ignorados)")

    # --- saidas LOCAIS (sempre) ---
    os.makedirs(out_dir, exist_ok=True)
    resumo = resumo_agregado(cons)
    resumo_path = os.path.join(out_dir, "resumo.json")
    with open(resumo_path, "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)

    import csv
    csv_path = os.path.join(out_dir, "posicao.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["arquivo", "banco", "conta", "tipo", "saldo_final", "data_saldo",
                    "n_transacoes", "entra_no_caixa", "motivo_fora"])
        for c in cons.contas:
            w.writerow([_txt_csv(c.arquivo), _txt_csv(c.banco), _txt_csv(c.conta),
                        _txt_csv("cartao" if c.eh_cartao else (c.tipo_conta or "conta")),
                        c.saldo_final, c.data_saldo, c.n_transacoes,
                        "sim" if c.entra_no_caixa else "nao", c.motivo_fora])
        w.writerow([])
        w.writerow(["TOTAL EM CAIXA", "", "", "", cons.total_caixa, "", "", "", ""])
        if saldo_minimo is not None:
            w.writerow(["SALDO MINIMO", "", "", "", saldo_minimo, "", "", "", ""])
            w.writerow(["STATUS", "", "", "", status_texto(cons),
                        cons.deficit if cons.abaixo else "", "", "", ""])

    print(f"\n  resumo (p/ IA, agregado): {resumo_path}")
    print(f"  posicao (LOCAL): {csv_path}")

    # --- push p/ Google Sheet (opt-in; so o agregado sobe) ---
    if sheet_id:
        from sheets_push import montar_linhas_agregadas, push_para_sheet
        linhas = montar_linhas_agregadas(cons)
        try:
            destino = push_para_sheet(linhas, sheet_id, aba)
            print(f"  Google Sheet atualizada: {destino}")
        except Exception as e:                      # noqa: BLE001 - gspread/APIError pode ecoar o que foi enviado: so o tipo
            print(f"\n[!] Push p/ Sheet nao concluido ({type(e).__name__})")
            print("    Confira se o gspread esta instalado e a credencial do Google configurada (ver o README).")
            return 4
    return 0


def _eh_arquivo_razao(nome):
    """O razao da conta e o arquivo cujo nome contem 'razao'/'razão' (convencao do produto:
    1 pasta por conta, com o extrato + um razao.csv no modelo). 1 lancamento por linha."""
    n = nome.lower()
    return "razao" in n or "razão" in n


def _le_saldo(pasta_conta, arquivo):
    """SPEC-07 #3: le um saldo (do razao OU do extrato) de um arquivo opt-in na pasta da conta,
    p/ fechar a amarracao na jornada `pasta`. `saldo-razao.txt` = saldo contabil; `saldo-extrato.txt`
    = saldo do banco p/ quando o OFX vem com LEDGERBAL zerado/ausente (quirk Bradesco/Santander/BB) ou
    a conta fecha legitimamente em 0,00. Skip-safe: ausente/ilegivel -> None (so reporta taxa, sem amarracao)."""
    p = os.path.join(pasta_conta, arquivo)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as f:
            txt = f.read().strip()
        return parse_valor(txt, origem="br") if txt else None
    except (OSError, ValueError, ArithmeticError):
        return None


def _melhor_extrato(paths, ocr):
    """Ingere cada extrato candidato e devolve o melhor (preferencia de formato/status)."""
    res = [(p, ingest_extrato(p, ocr=ocr)) for p in paths]
    res.sort(key=lambda pr: (_STATUS_RANK.get(pr[1].status, 9),
                             _FORMATO_RANK.get(pr[1].fonte, 9), -len(pr[1].transacoes)))
    return res[0]


def cmd_pasta(pasta, out_dir, ocr=False):
    """JORNADA DO ANALISTA (SPEC-04): varre a pasta (1 subpasta por conta: extrato em
    qualquer formato + um `razao.csv` no modelo), escolhe o melhor extrato de cada conta e,
    se houver razao na pasta, CONCILIA (taxa, pendencias, lote). Foco = contas a PAGAR:
    credito do banco pendente -> orienta 'lance um contas-a-receber' (SPEC-03). So agregados
    sobem p/ a IA (resumo.json); o Excel/detalhe fica local. ocr=True liga o OCR local."""
    if not os.path.isdir(pasta):
        print(f"pasta nao encontrada: {pasta}")
        return 2

    # agrupa por SUBPASTA (convencao: 1 subpasta por conta). Robustez contra uso indevido (SPEC-05):
    #   R1: arquivo solto na RAIZ da pasta-mae nao e conta (nada de conta fantasma ".");
    #   R2: pula diretorios de ruido (ocultos, _*, __pycache__, resultado*) e a propria pasta de saida.
    pasta_abs = os.path.abspath(pasta)
    out_abs = os.path.abspath(out_dir)

    def _dir_ruido(nome):
        return (nome.startswith(".") or nome.startswith("_")
                or nome == "__pycache__" or nome.lower().startswith("resultado"))

    grupos = {}
    soltos_raiz = 0  # arquivos parecidos com extrato/razao soltos na raiz -> aviso (R3)
    for root, dirs, files in os.walk(pasta):
        dirs[:] = [d for d in dirs
                   if not _dir_ruido(d) and os.path.abspath(os.path.join(root, d)) != out_abs]
        na_raiz = os.path.abspath(root) == pasta_abs
        for f in sorted(files):
            if f.startswith("._"):
                continue
            if f.lower() in ("conciliacao.xlsx", "conciliacao_por_status.csv"):   # relatorio gerado por esta skill, nao extrato (SPEC-06 #1; nome exato p/ nao descartar um "conciliacao_*.csv" do ERP)
                continue
            if f.lower() in ("saldo-razao.txt", "saldo-extrato.txt"):   # SPEC-07 #3: config de amarracao da conta, nao extrato/razao (lido direto da pasta da conta)
                continue
            ext = os.path.splitext(f)[1].lower().lstrip(".")
            if na_raiz:
                if ext in ("ofx", "csv", "xlsx", "xls", "pdf"):
                    soltos_raiz += 1
                continue
            p = os.path.join(root, f)
            g = grupos.setdefault(root, {"razao": None, "extratos": []})
            if _eh_arquivo_razao(f) and ext in ("csv", "xlsx", "xls"):
                g["razao"] = p
            elif ext in ("ofx", "csv", "xlsx", "xls", "pdf", "txt", "jpg", "jpeg", "png"):
                g["extratos"].append(p)

    reprovadas = []   # (conta, n, lista de linhas) do razao com linha invalida
    contas, glob = [], {"contas": 0, "conciliadas": 0, "ingeridas": 0, "precisa_acao": 0, "ar_cred": 0}
    for d, g in sorted(grupos.items()):
        if not g["extratos"]:
            continue
        ep, ext = _melhor_extrato(g["extratos"], ocr)
        conta = {"conta": os.path.relpath(d, pasta) or os.path.basename(d),  # rotulo do cliente (B1: mantem); filename NAO sobe (#4)
                 "fonte": ext.fonte, "status_extrato": ext.status, "n_txns": len(ext.transacoes),
                 "tem_razao": bool(g["razao"]), "precisa_acao": not ext.transacoes}
        glob["contas"] += 1
        if not ext.transacoes:
            glob["precisa_acao"] += 1
        elif ext.n_contas > 1:                           # mesma regra do `validar`: misturar contas falsearia o cruzamento e o saldo
            conta.update({"tem_razao": False, "precisa_acao": True, "multiconta": ext.n_contas})
            glob["ingeridas"] += 1
            glob["precisa_acao"] += 1
        elif g["razao"]:
            try:
                linhas = read_tabular(g["razao"])
            except Exception as e:                       # noqa: BLE001 — razao ilegivel nao derruba a pasta (SPEC-06 #3)
                conta["tem_razao"] = False
                conta["aviso"] = f"razao ilegivel ({type(e).__name__}); conta so ingerida (salve a razao como CSV)"
                glob["ingeridas"] += 1
                contas.append(conta)
                continue
            cols = _detecta_colunas(list(linhas[0].keys()), {}) if linhas else {}
            razao, erros_raz = _razao_canonico(linhas, cols) if linhas else ([], [])
            if erros_raz:                                # linha invalida: conta nao concilia (so numero de linha, nunca a celula)
                nums = _linhas_invalidas(erros_raz)
                lista = ", ".join(map(str, nums[:5])) + (f" (+{len(nums) - 5})" if len(nums) > 5 else "")
                conta["tem_razao"] = False
                conta["razao_reprovada"] = True
                conta["aviso"] = f"razao reprovada: {len(nums)} linha(s) invalida(s): linhas {lista}; conta so ingerida"
                reprovadas.append((conta["conta"], len(nums), lista))
                glob["ingeridas"] += 1
                contas.append(conta)
                continue
            # SPEC-07 #3: fecha a amarracao da conta (checksum) quando ha saldo do razao (opt-in
            # `saldo-razao.txt` na pasta da conta) E saldo do extrato (LEDGERBAL do OFX). Senao, so taxa/pendencias.
            saldo_raz = _le_saldo(d, "saldo-razao.txt")
            # escape hatch: saldo-extrato.txt cobre LEDGERBAL zerado/ausente (quirk Bradesco/Santander/BB)
            # ou conta que fecha legitimamente em 0,00 (achado /codex:review SPEC-07)
            saldo_ext, _av = _saldo_extrato_efetivo(ext.saldo_final, _le_saldo(d, "saldo-extrato.txt"))
            if saldo_raz is not None and saldo_ext is not None:
                c = match_banco(ext.transacoes, razao, saldo_extrato_final=saldo_ext, saldo_razao_final=saldo_raz)
            else:
                c = match_banco(ext.transacoes, razao)
            rp = resumo_privado(c)
            conc = sum(1 for l in c.lancamentos if l.lado == "EXTRATO" and l.status.startswith("CONCILIADO"))
            pend_ext = sum(1 for l in c.lancamentos if l.status == "PENDENTE_EXTRATO")
            ar_cred = sum(1 for l in c.lancamentos
                          if l.status == "PENDENTE_EXTRATO" and l.registro["valor"] > 0)  # credito sem AR
            conta.update({"n_razao": len(razao), "taxa_pct": rp["taxa_conciliacao_pct"],
                          "conciliados": conc, "pendente_extrato": pend_ext,
                          "pendente_razao": c.contagem.get("PENDENTE_RAZAO", 0),
                          "credito_sem_ar": ar_cred, "controle_lote": rp.get("controle_lote"),
                          "ambiguos": rp.get("conciliados_ambiguos", 0),       # SPEC-07 #4
                          "conferir_cpf_cnpj": rp.get("conferir_cpf_cnpj", 0),  # D9
                          "conferir_lote_valores_iguais": rp.get("conferir_lote_valores_iguais", 0),  # D10c
                          "amarracao": c.amarracao,                            # SPEC-07 #3 (None se sem saldo)
                          "integridade_ok": (c.integridade_ok if c.amarracao else None)})
            try:
                _escreve_relatorio(c, d)                 # relatorio branded LOCAL por conta, todo formato (SPEC-06 #1)
            except Exception as e:                       # noqa: BLE001 — relatorio e best-effort, nao derruba o run
                conta["aviso_relatorio"] = f"relatorio nao gravado ({type(e).__name__})"
            glob["conciliadas"] += 1
            glob["ar_cred"] += ar_cred
        else:
            glob["ingeridas"] += 1
        contas.append(conta)

    print("== CONCILIACAO DA PASTA (por conta — 1 razao por conta) ==")
    print(f"  contas: {glob['contas']} | conciliadas: {glob['conciliadas']} | "
          f"so ingeridas (sem razao): {glob['ingeridas']} | extrato p/ acao: {glob['precisa_acao']}")
    print(f"\n  {'conta':<34}{'fonte':<6}{'txns':>5}{'raz':>5}{'taxa':>6}{'pEXT':>6}{'pRAZ':>6}{'AR?':>5}")
    print("  " + "-" * 74)
    for c in contas:
        if c.get("tem_razao") and not c["precisa_acao"]:
            print(f"  {c['conta'][:32]:<34}{c['fonte']:<6}{c['n_txns']:>5}{c['n_razao']:>5}"
                  f"{c['taxa_pct']:>5.0f}%{c['pendente_extrato']:>6}{c['pendente_razao']:>6}{c['credito_sem_ar']:>5}")
        else:
            nota = ("multiconta" if c.get("multiconta") else c["status_extrato"] if c["precisa_acao"]
                    else "razao reprovada" if c.get("razao_reprovada") else "sem razao")
            print(f"  {c['conta'][:32]:<34}{c['fonte']:<6}{c['n_txns']:>5}{'':>5}{'':>6}{'':>6}{'':>6}  {nota}")

    if glob["ar_cred"]:
        print(f"\n  [i] {glob['ar_cred']} credito(s) do banco sem correspondente no razao — o foco do produto"
              f" e CONTAS A PAGAR; para esses, LANCE um CONTAS A RECEBER no razao da conta.")
    multi = [c["conta"] for c in contas if c.get("multiconta")]
    pa = glob["precisa_acao"] - len(multi)                 # multiconta tem a linha propria logo abaixo
    if pa:
        print(f"  [!] {pa} conta(s) com extrato que precisa de acao (OCR/--ocr; layout nao reconhecido"
              f" -> exporte OFX/CSV; corrompido).")
    if multi:
        print(f"  [!] extrato com mais de uma conta em: {', '.join(multi)}")
        print("      Exporte e concilie UMA conta por vez; essas contas foram so ingeridas, nada foi conciliado.")
    amb = sum(c.get("ambiguos", 0) for c in contas)       # SPEC-07 #4
    if amb:
        print(f"  [!] {amb} conciliacao(oes) AMBIGUA(s) (mesmo valor sem documento/identificador p/ desempatar)"
              f" — casei o par provavel, mas CONFIRA no Excel da(s) conta(s).")
    conf = sum(c.get("conferir_cpf_cnpj", 0) for c in contas)                    # D9
    if conf:
        print(f"  [!] {conf} conciliacao(oes) com CPF/CNPJ do banco diferente do razao (confira no Excel)")
    conf = sum(c.get("conferir_lote_valores_iguais", 0) for c in contas)         # D10c
    if conf:
        print(f"  [!] {conf} lote(s) com titulos de mesmo valor (confira quais titulos no Excel)")
    fecha = [c["conta"] for c in contas if c.get("integridade_ok") is True]        # SPEC-07 #3
    naofecha = [c["conta"] for c in contas if c.get("integridade_ok") is False]
    if fecha:
        print(f"  [i] amarracao FECHOU em: {', '.join(fecha)}.")
    if naofecha:
        print(f"  [!] amarracao NAO fechou em: {', '.join(naofecha)} — confira o saldo-razao.txt e as pendencias.")
    for nome, n, lista in reprovadas:
        print(f"  [!] razão reprovada em: {nome} ({n} linha(s) inválida(s): linhas {lista})")
    if soltos_raiz:
        print(f"  [i] Ignorei {soltos_raiz} arquivo(s) solto(s) na raiz da pasta — nao sao contas"
              f" (organize 1 subpasta por conta: extrato + razao.csv).")
    if glob["contas"] == 0:
        print("\n  Nenhuma conta encontrada. Organize 1 SUBPASTA por conta (extrato + razao.csv) na pasta"
              " do mes, ou use o comando 'conciliar' para conciliar uma conta so.")

    os.makedirs(out_dir, exist_ok=True)
    resumo_path = os.path.join(out_dir, "resumo.json")
    with open(resumo_path, "w", encoding="utf-8") as f:
        json.dump({"resumo": glob, "contas": contas}, f, ensure_ascii=False, indent=2)  # agregado, sem linhas
    print(f"\n  resumo (p/ IA, agregado): {resumo_path}")
    return 0


def _build_parser():
    p = argparse.ArgumentParser(description="Conciliacao Bancaria local (3 fases).")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nome in ("validar", "conciliar"):
        sp = sub.add_parser(nome)
        sp.add_argument("--extrato", required=True, help="extrato bancario (OFX/CSV/XLSX/XLS/PDF; OFX de preferencia)")
        sp.add_argument("--razao", required=True, help="razao contabil .csv/.xlsx")
        sp.add_argument("--col-data"); sp.add_argument("--col-valor")
        sp.add_argument("--col-doc"); sp.add_argument("--col-desc")
        # mapeamento de colunas fora do padrao do modelo (SPEC-06 #5 — antes so data/valor/doc/desc existiam)
        sp.add_argument("--col-ident"); sp.add_argument("--col-contraparte")
        sp.add_argument("--col-cpfcnpj"); sp.add_argument("--col-lote")
        if nome == "conciliar":
            sp.add_argument("--saldo-razao", required=True, help="saldo final do razao (amarracao)")
            sp.add_argument("--out", default="resultado", help="pasta de saida (default: resultado/)")
            sp.add_argument("--janela", type=int, default=3, help="dias de defasagem D+n (default 3)")
            sp.add_argument("--tolerancia", default="0.10", help="tolerancia de centavos (default 0.10)")
            sp.add_argument("--saldo-extrato",
                            help="saldo final do extrato; use quando o OFX vem com saldo zerado "
                                 "(Bradesco/Santander/BB nao preenchem o LEDGERBAL)")

    # modo posicao: varre uma pasta de OFX, consolida o caixa, devolve o status
    spp = sub.add_parser("posicao", help="consolida a posicao de caixa de uma pasta de OFX")
    spp.add_argument("--pasta", required=True, help="pasta com os arquivos .ofx (export do internet banking)")
    spp.add_argument("--saldo-minimo", help="saldo minimo de caixa p/ o alerta (ex.: 50000)")
    spp.add_argument("--out", default="resultado-posicao", help="pasta de saida (default: resultado-posicao/)")
    spp.add_argument("--forcar-conta", default="",
                     help="arquivos (separados por virgula) a tratar como conta mesmo em envelope de cartao (ex.: nubank.ofx)")
    spp.add_argument("--sheet", help="(opt-in) ID da Google Sheet p/ empurrar o agregado; sem isso roda 100%% offline")
    spp.add_argument("--aba", default="Posicao Consolidada", help="aba da Sheet (default: Posicao Consolidada)")

    # modo pasta: varre uma pasta de extratos (qualquer formato) e diz o que conseguiu ler
    spx = sub.add_parser("pasta", help="ingere uma pasta de extratos (OFX/CSV/XLSX/XLS/PDF) com preferencia de formato")
    spx.add_argument("--pasta", required=True, help="pasta com os extratos do periodo (qualquer formato)")
    spx.add_argument("--out", default="resultado-pasta", help="pasta de saida (default: resultado-pasta/)")
    spx.add_argument("--ocr", action="store_true", help="liga OCR local (Tesseract) p/ imagem/PDF escaneado")
    return p


def main(argv=None):
    import logging
    import warnings
    # console da analista pode ser cp1252/cp850 (Windows) -> blinda print de acento/setas
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    # warning/log de biblioteca (openpyxl, pdfminer) vai ao stderr sem passar pelo handler e pode trazer texto do arquivo
    warnings.showwarning = lambda message, category, *a, **k: print(
        f"[aviso] uma biblioteca emitiu {category.__name__}; detalhe omitido (pode trazer texto do arquivo)", file=sys.stderr)
    logging.getLogger().addHandler(logging.NullHandler())
    args = _build_parser().parse_args(argv)

    if args.cmd == "posicao":
        saldo_min = None
        if args.saldo_minimo:
            try:
                saldo_min = parse_valor(args.saldo_minimo, origem="br")
            except ValueError:
                print(f"--saldo-minimo invalido: {args.saldo_minimo!r}")
                return 2
        forcar = [s.strip() for s in args.forcar_conta.split(",") if s.strip()]
        return cmd_posicao(args.pasta, saldo_min, args.out, forcar, args.sheet, args.aba)

    if args.cmd == "pasta":
        return cmd_pasta(args.pasta, args.out, args.ocr)

    overrides = {"data": args.col_data, "valor": args.col_valor, "doc": args.col_doc, "desc": args.col_desc,
                 "ident": args.col_ident, "contraparte": args.col_contraparte,
                 "cpfcnpj": args.col_cpfcnpj, "lote": args.col_lote}

    if args.cmd == "validar":
        aprovado, metad = fase1_validar(args.extrato, args.razao, overrides)
        print(json.dumps(metad, ensure_ascii=False, indent=2, default=str))
        print("\n[OK] arquivos comparaveis." if aprovado else "\n[REPROVADO] ver 'reprovas'.")
        return 0 if aprovado else 2

    try:
        saldo = parse_valor(args.saldo_razao, origem="br")
    except ValueError:
        print(f"--saldo-razao invalido: {args.saldo_razao!r}")
        return 2
    try:
        tol = parse_valor(args.tolerancia, origem="br")
    except ValueError:
        print(f"--tolerancia invalida: {args.tolerancia!r}")
        return 2
    saldo_ext_override = None
    if args.saldo_extrato:
        try:
            saldo_ext_override = parse_valor(args.saldo_extrato, origem="br")
        except ValueError:
            print(f"--saldo-extrato invalido: {args.saldo_extrato!r}")
            return 2
    return conciliar(args.extrato, args.razao, saldo, args.out, overrides, args.janela, tol,
                     saldo_extrato_override=saldo_ext_override)


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
