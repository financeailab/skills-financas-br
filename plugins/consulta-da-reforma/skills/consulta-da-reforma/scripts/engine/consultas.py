# -*- coding: utf-8 -*-
"""Consultas fixas as tabelas oficiais. So leitura: nenhuma conta de imposto (base, valor, reducao aplicada).

Cada consulta reproduz como a API Java oficial LE a tabela (calculadora-rtc-regime-regular e
calculadora-rtc-simples-nacional, MIT); o arquivo de origem esta no comentario. Vigencia igual a da API:
`data BETWEEN inicio AND COALESCE(fim, data)`, com datas AAAA-MM-DD (comparacao de texto segura, spike secao 3).
"""
from __future__ import annotations

import sqlite3

from base import LinhaAmbigua

GRUPOS = {"cbs-ibs": 2, "is": 1}  # TBTO_ID: 1 = IS, 2 = CBS (o grupo CBS/IBS da API)
LIMITE_BUSCA = 20
NIVEIS_NCM = (2, 4, 6, 7, 8)  # DadosAbertosService.consultarNcm: capitulo, posicao, subposicao, item, subitem
NIVEIS_NBS = (5, 6, 7, 8, 9)  # DadosAbertosService.consultarNbs


def _vig(prefixo: str) -> str:
    return f"? BETWEEN {prefixo}_INICIO_VIGENCIA AND COALESCE({prefixo}_FIM_VIGENCIA, ?)"


def _uma(linhas: list):
    if len(linhas) > 1:
        raise LinhaAmbigua()  # a API espera no maximo uma linha (spike: 14 codigos em 2 grupos)
    return linhas[0] if linhas else None


def classificacao(con: sqlite3.Connection, codigo: str, data: str, grupo: str = "cbs-ibs"):
    """ClassificacaoTributariaRepository.buscarClassificacaoTributaria: por grupo de tributo, vigencia nas 4 tabelas."""
    linhas = con.execute(f"""
        SELECT ct.CLTR_ID, ct.CLTR_CD, ct.CLTR_DESCRICAO, st.SITR_CD, st.SITR_DESCRICAO,
               ct.CLTR_INICIO_VIGENCIA, ct.CLTR_FIM_VIGENCIA
        FROM CLASSIFICACAO_TRIBUTARIA ct
        JOIN SITUACAO_TRIBUTARIA st ON ct.CLTR_SITR_ID = st.SITR_ID
        JOIN TRIBUTO_SITUACAO_TRIBUTARIA tst ON tst.TRST_SITR_ID = st.SITR_ID
        JOIN TRIBUTO tb ON tst.TRST_TBTO_ID = tb.TBTO_ID
        WHERE ct.CLTR_CD = ? AND tb.TBTO_ID = ?
          AND {_vig('ct.CLTR')} AND {_vig('st.SITR')} AND {_vig('tst.TRST')} AND {_vig('tb.TBTO')}""",
        (codigo, GRUPOS[grupo], data, data, data, data, data, data, data, data)).fetchall()
    linha = _uma(linhas)
    if linha is None:
        return None
    cltr_id = linha[0]
    # PercentualReducaoRepository.buscar, um por tributo
    reducoes = con.execute(f"""
        SELECT t.TBTO_SIGLA, p.PERE_VALOR FROM PERCENTUAL_REDUCAO p JOIN TRIBUTO t ON t.TBTO_ID = p.PERE_TBTO_ID
        WHERE p.PERE_CLTR_ID = ? AND {_vig('p.PERE')} ORDER BY t.TBTO_ID""", (cltr_id, data, data)).fetchall()
    fundamentos = con.execute(f"""
        SELECT f.FDLG_TEXTO_CURTO, f.FDLG_REFERENCIA_NORMATIVA FROM FUNDAMENTACAO_CLASSIFICACAO x
        JOIN FUNDAMENTACAO_LEGAL f ON f.FDLG_ID = x.FDCL_FDLG_ID
        WHERE x.FDCL_CLTR_ID = ? AND {_vig('x.FDCL')} AND {_vig('f.FDLG')} ORDER BY f.FDLG_ID""",
        (cltr_id, data, data, data, data)).fetchall()
    return {"id": cltr_id, "codigo": linha[1], "descricao": linha[2], "cst": linha[3], "cst_descricao": linha[4],
            "inicio": linha[5], "fim": linha[6], "reducoes": reducoes, "fundamentos": fundamentos}


def referencia(con: sqlite3.Connection, data: str) -> list:
    """AliquotaReferenciaRepository.buscar, para os tributos com linha na data."""
    return con.execute(f"""
        SELECT t.TBTO_SIGLA, a.ALRE_VALOR FROM ALIQUOTA_REFERENCIA a JOIN TRIBUTO t ON t.TBTO_ID = a.ALRE_TBTO_ID
        WHERE {_vig('a.ALRE')} ORDER BY t.TBTO_ID""", (data, data)).fetchall()


def _niveis(con, tabela: str, col: str, codigo: str, niveis: tuple, data: str) -> list:
    out = []
    for n in niveis:
        if n > len(codigo):
            break
        r = con.execute(f"SELECT {col}_CD, {col}_DESCRICAO FROM {tabela} WHERE {col}_CD = ? AND {_vig(col)}",
                        (codigo[:n], data, data)).fetchone()
        if r:
            out.append(r)
    return out


def _is_produto(con, ncm: str, data: str, tab: str, ali: str, exc: str, p: str, a: str, e: str, val: str):
    """AliquotaAdValoremProdutoRepository / AliquotaAdRemProdutoRepository.buscar...: prefixo, excecoes, mais longo.
    Incidencia do IS = existe a linha (mesmo com valor nulo, "nao definida em lei"), DadosAbertosService.consultarNcm.
    `val` e a lista de colunas devolvidas (o ad rem leva tambem a unidade)."""
    return con.execute(f"""
        SELECT {val} FROM {tab} x JOIN {ali} a ON a.{a}_ID = x.{p}_{a}_ID
        WHERE EXISTS (SELECT 1 FROM NCM n WHERE n.NCM_CD = ?)
          AND x.{p}_NCM_CD = substr(?, 1, length(x.{p}_NCM_CD)) AND a.{a}_TBTO_ID = 1 AND {_vig('x.' + p)}
          AND NOT EXISTS (SELECT 1 FROM {exc} e WHERE e.{e}_{p}_ID = x.{p}_ID
                AND (e.{e}_NCM_CD = substr(?, 1, length(e.{e}_NCM_CD))
                     OR e.{e}_NCM_CD = substr(x.{p}_NCM_CD, 1, length(e.{e}_NCM_CD)))
                AND {_vig('e.' + e)})
        ORDER BY length(x.{p}_NCM_CD) DESC LIMIT 1""", (ncm, ncm, data, data, ncm, data, data)).fetchall()


def inicio_is(con: sqlite3.Connection) -> str | None:
    """Inicio de vigencia do tributo IS na base (TRIBUTO, TBTO_ID 1): antes dele, nenhuma NCM tem IS."""
    r = con.execute("SELECT TBTO_INICIO_VIGENCIA FROM TRIBUTO WHERE TBTO_ID = 1").fetchone()
    return r[0] if r else None


def _is_em_subitens(con, codigo: str, data: str) -> bool:
    """NCM com menos de 8 digitos: algum subitem tem linha de IS na data? A API so olha do codigo para cima (prefixo);
    para leigo, "sem incidencia" num capitulo cujos subitens tem IS seria resposta errada."""
    for tab, ali, p, a in (("ALIQUOTA_AD_VALOREM_PRODUTO", "ALIQUOTA_AD_VALOREM", "AAVP", "AADV"),
                           ("ALIQUOTA_AD_REM_PRODUTO", "ALIQUOTA_AD_REM", "AARP", "AARE")):
        if con.execute(f"""
                SELECT 1 FROM {tab} x JOIN {ali} a ON a.{a}_ID = x.{p}_{a}_ID
                WHERE substr(x.{p}_NCM_CD, 1, ?) = ? AND length(x.{p}_NCM_CD) > ? AND a.{a}_TBTO_ID = 1
                  AND {_vig('x.' + p)} LIMIT 1""", (len(codigo), codigo, len(codigo), data, data)).fetchone():
            return True
    return False


def _is_fim(con, codigo: str, data: str) -> str | None:
    """A NCM teve linha de IS (prefixo) e todas acabaram antes da data? Devolve o ultimo fim; senao None.
    Depois do fim das linhas, a base nao afirma "sem incidencia"."""
    fins = []
    for tab, ali, p, a in (("ALIQUOTA_AD_VALOREM_PRODUTO", "ALIQUOTA_AD_VALOREM", "AAVP", "AADV"),
                           ("ALIQUOTA_AD_REM_PRODUTO", "ALIQUOTA_AD_REM", "AARP", "AARE")):
        fins += [r[0] for r in con.execute(f"""
            SELECT x.{p}_FIM_VIGENCIA FROM {tab} x JOIN {ali} a ON a.{a}_ID = x.{p}_{a}_ID
            WHERE x.{p}_NCM_CD = substr(?, 1, length(x.{p}_NCM_CD)) AND a.{a}_TBTO_ID = 1""", (codigo,))]
    if not fins or None in fins or max(fins) >= data:
        return None
    return max(fins)


def ncm(con: sqlite3.Connection, codigo: str, data: str):
    """DadosAbertosService.consultarNcm: a NCM existe na data? descricao por nivel; IS ad valorem e ad rem."""
    if not con.execute(f"SELECT 1 FROM NCM WHERE NCM_CD = ? AND {_vig('NCM')}", (codigo, data, data)).fetchone():
        return None
    adv = _is_produto(con, codigo, data, "ALIQUOTA_AD_VALOREM_PRODUTO", "ALIQUOTA_AD_VALOREM",
                      "EXCECAO_AD_VALOREM_PRODUTO", "AAVP", "AADV", "EAVP", "a.AADV_VALOR")
    adr = _is_produto(con, codigo, data, "ALIQUOTA_AD_REM_PRODUTO", "ALIQUOTA_AD_REM",
                      "EXCECAO_AD_REM_PRODUTO", "AARP", "AARE", "EARP",
                      "a.AARE_VALOR, (SELECT u.UNMD_DESCRICAO FROM UNIDADE_MEDIDA u WHERE u.UNMD_ID = a.AARE_UNMD_ID)")
    subitens = not adv and not adr and len(codigo) < 8 and _is_em_subitens(con, codigo, data)
    return {"niveis": _niveis(con, "NCM", "NCM", codigo, NIVEIS_NCM, data),
            "is_ad_valorem": adv[0] if adv else None,  # linha (valor,) ou None
            "is_ad_rem": adr[0] if adr else None,  # linha (valor, unidade) ou None
            "is_subitens": subitens,
            "is_fim": None if adv or adr else _is_fim(con, codigo, data)}


def nbs(con: sqlite3.Connection, codigo: str, data: str):
    """DadosAbertosService.consultarNbs: NBS nao tem ad rem; IS ad valorem de servico (tabela hoje vazia)."""
    if not con.execute(f"SELECT 1 FROM NBS WHERE NBS_CD = ? AND {_vig('NBS')}", (codigo, data, data)).fetchone():
        return None
    adv = con.execute(f"""
        SELECT a.AADV_VALOR FROM ALIQUOTA_AD_VALOREM_SERVICO x JOIN ALIQUOTA_AD_VALOREM a ON a.AADV_ID = x.AAVS_AADV_ID
        WHERE x.AAVS_NBS_CD = substr(?, 1, length(x.AAVS_NBS_CD)) AND a.AADV_TBTO_ID = 1 AND {_vig('x.AAVS')}
          AND NOT EXISTS (SELECT 1 FROM EXCECAO_AD_VALOREM_SERVICO e WHERE e.EAVS_AAVS_ID = x.AAVS_ID
                AND e.EAVS_NBS_CD = substr(?, 1, length(e.EAVS_NBS_CD)) AND {_vig('e.EAVS')})
        ORDER BY length(x.AAVS_NBS_CD) DESC LIMIT 1""", (codigo, data, data, codigo, data, data)).fetchall()
    return {"niveis": _niveis(con, "NBS", "NBS", codigo, NIVEIS_NBS, data), "is_ad_valorem": adv[0] if adv else None}


SEM_LISTA, VINCULADA, NAO_VINCULADA, INCOMPLETO = "sem lista", "vinculada", "nao vinculada", "codigo incompleto"
CODIGO_INEXISTENTE = "codigo inexistente"


def vinculo(con: sqlite3.Connection, tipo: str, codigo: str, cclasstrib: str, data: str, grupo: str = "cbs-ibs"):
    """NcmAplicavelService.criticar / NbsAplicavelService.criticar: sem anexo vigente = sem lista;
    com anexo, codigo completo (NCM 8, NBS 9) e vinculada = A && (!E || S). Antes, o codigo tem de existir na
    data (NcmRepository.existeNcm / NbsRepository.existeNbs): codigo inexistente nunca vira resposta confiante."""
    c = classificacao(con, cclasstrib, data, grupo)
    if c is None:
        return None
    tab, exc, p, e, tam = (("NCM_APLICAVEL", "EXCECAO_NCM_APLICAVEL", "NCMA", "ENCM", 8) if tipo == "ncm"
                           else ("NBS_APLICAVEL", "EXCECAO_NBS_APLICAVEL", "NBSA", "ENBS", 9))
    cd = "NCM_CD" if tipo == "ncm" else "NBS_CD"
    um = lambda sql, *args: con.execute(sql, args).fetchone()[0]
    col = tipo.upper()
    if not um(f"SELECT EXISTS (SELECT 1 FROM {col} WHERE {col}_CD = ? AND {_vig(col)})", codigo, data, data):
        return CODIGO_INEXISTENTE
    tem = um(f"SELECT EXISTS (SELECT 1 FROM {tab} n WHERE n.{p}_CLTR_ID = ? AND {_vig('n.' + p)})", c["id"], data, data)
    if not tem:
        return SEM_LISTA
    if len(codigo) != tam:
        return INCOMPLETO
    cobre = f"n.{p}_{cd} = substr(?, 1, length(n.{p}_{cd}))"
    A = um(f"SELECT EXISTS (SELECT 1 FROM {tab} n WHERE {cobre} AND n.{p}_CLTR_ID = ? AND {_vig('n.' + p)})",
           codigo, c["id"], data, data)
    E = um(f"""SELECT EXISTS (SELECT 1 FROM {exc} e JOIN {tab} n ON n.{p}_ID = e.{e}_{p}_ID
               WHERE {cobre} AND e.{e}_{cd} = substr(?, 1, length(e.{e}_{cd})) AND n.{p}_CLTR_ID = ?
               AND {_vig('e.' + e)})""", codigo, codigo, c["id"], data, data)
    S = um(f"""SELECT EXISTS (SELECT 1 FROM {tab} n LEFT JOIN {exc} e ON e.{e}_{p}_ID = n.{p}_ID
               WHERE {cobre} AND n.{p}_CLTR_ID = ? AND {_vig('n.' + p)}
               AND (e.{e}_ID IS NULL OR NOT ({_vig('e.' + e)})))""", codigo, c["id"], data, data, data, data)
    return VINCULADA if A and (not E or S) else NAO_VINCULADA


def faixa(con: sqlite3.Connection, tabela: str, prefixo: str) -> tuple:
    """(menor inicio, maior fim ou None se algum nao tem fim) de vigencia da tabela: as mensagens de "sem linha"
    citam a base, nao um ano fixo que envelhece na proxima atualizacao."""
    ini, sem_fim, fim = con.execute(
        f"SELECT min({prefixo}_INICIO_VIGENCIA), sum({prefixo}_FIM_VIGENCIA IS NULL), max({prefixo}_FIM_VIGENCIA) "
        f"FROM {tabela}").fetchone()
    return ini, (None if sem_fim else fim)


def simples(con: sqlite3.Connection, data: str, codigo: str | None = None) -> list:
    """AtividadeSimplesRepository (repo calculadora-rtc-simples-nacional): atividades vigentes, pela ordem oficial."""
    filtro, args = ("AND ATSN_CATIVSN = ?", (data, data, codigo)) if codigo else ("", (data, data))
    return con.execute(f"""
        SELECT ATSN_CATIVSN, ATSN_DESCRICAO, ATSN_ANEXO_SEM_FATOR_R, ATSN_ANEXO_COM_FATOR_R, ATSN_ROTULO
        FROM ATIVIDADE_SIMPLES_NACIONAL WHERE {_vig('ATSN')} {filtro} ORDER BY ATSN_ORDEM""", args).fetchall()


def buscar(con: sqlite3.Connection, termo_normalizado: str, data: str, em: str = "cclasstrib") -> tuple[int, list]:
    """Codigos vigentes cuja descricao contem o termo (sem acento e sem caixa). Devolve (total, ate 20)."""
    if em == "cclasstrib":
        sql = f"""SELECT DISTINCT CLTR_CD, CLTR_DESCRICAO FROM CLASSIFICACAO_TRIBUTARIA
                  WHERE {_vig('CLTR')} AND instr(sem_acento(CLTR_DESCRICAO), ?) > 0 ORDER BY CLTR_CD"""
    else:
        col, tam = ("NCM", 8) if em == "ncm" else ("NBS", 9)  # so o codigo completo, como buscarTodosNcmsVigentes
        sql = f"""SELECT {col}_CD, {col}_DESCRICAO FROM {col} WHERE {_vig(col)} AND length({col}_CD) = {tam}
                  AND instr(sem_acento({col}_DESCRICAO), ?) > 0 ORDER BY {col}_CD"""
    linhas = con.execute(sql, (data, data, termo_normalizado)).fetchall()
    return len(linhas), linhas[:LIMITE_BUSCA]
