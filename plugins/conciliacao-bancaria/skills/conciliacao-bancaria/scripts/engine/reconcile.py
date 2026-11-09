# -*- coding: utf-8 -*-
"""Core de conciliacao: motor deterministico.

match_banco: sem chave limpa. Cascata data+valor+documento + janela de
liquidacao + tolerancia, e a AMARRACAO de saldo (checksum da conciliacao
bancaria classica). Devolve um formato de resultado (Conciliacao).

Convencao de sinal (lado banco e lado razao): +entrada / -saida de caixa
(mesmo sinal do TRNAMT do OFX). A razao deve ser ingerida nessa convencao.

Determinismo: nenhuma aleatoriedade, nenhuma rede, nenhuma escrita fora do alvo.
A IA (Claude) le apenas o resumo agregado (resumo_privado), nunca os lancamentos.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations

from normalize import tokens_nome
from ingest_ofx import _E2E

ZERO = Decimal("0.00")
TOL_PADRAO = Decimal("0.10")        # diferenca de centavos -> "conciliado com diferenca"
JANELA_PADRAO = 3                    # dias de defasagem de liquidacao (D+n) ainda = conciliado


def divergente(ext: dict, r: dict) -> bool:
    """cpf_cnpj nos DOIS lados e diferente, salvo CNPJ de 14 digitos com a mesma raiz de 8 (matriz e filial)."""
    a, b = ext.get("cpf_cnpj"), r.get("cpf_cnpj")
    if not (a and b) or a == b:
        return False
    return not (len(a) == 14 and len(b) == 14 and a[:8] == b[:8])


def _e2e_diferem(a: str, b: str) -> bool:
    """Diferentes alem da caixa; ou so na caixa quando nenhum lado esta todo em maiusculas (o banco pode ter
    normalizado o MEMO, S5 da spec: a recusa perderia o par bom)."""
    return a.upper() != b.upper() or (a != b and a != a.upper() and b != b.upper())


def conflito_forte(ext: dict, r: dict, j: int, por_cnpj: dict) -> bool:
    """PROVA de par errado (D9): (i) `identificador` com formato de E2E nos dois lados e diferente; ou (ii) cpf_cnpj
    divergente E o cpf_cnpj do extrato e o de OUTRO titulo do razao (indice diferente de j, consumido ou nao).
    Divergencia sem prova nao recusa: o par casa e leva a marca `conferir`. O `doc` fica de fora (o numero do
    banco e o do ERP raramente sao o mesmo) e NSU/nosso numero do razao nao sao E2E."""
    ie, ir = ext.get("identificador"), r.get("identificador")
    if ie and ir and _e2e_diferem(ie, ir) and _E2E.fullmatch(ie) and _E2E.fullmatch(ir):
        return True
    return divergente(ext, r) and any(k != j for k in por_cnpj.get(ext["cpf_cnpj"], ()))


@dataclass
class Lancamento:
    lado: str                 # 'EXTRATO' | 'RAZAO'
    registro: dict            # registro canonico (data, valor, doc, descricao...)
    status: str
    par_idx: int | None = None
    diferenca: Decimal = ZERO
    lag_dias: int = 0
    categoria: str = ""       # sub-classificacao do operador p/ pendencias (ver classifica_pendencia)
    componentes: list = field(default_factory=list)  # indices da razao que somam um CONCILIADO_LOTE (N:1)
    conferir: tuple = ()      # D9/D10c: motivos FIXOS de conferencia ("cpf_cnpj", "lote_valores_iguais"); conciliado, mas o operador confere
    ambiguo: bool = False     # SPEC-07 #4: match exato com 2+ candidatos de mesmo valor e afinidade empatada
                              # (nenhum doc/ident/CNPJ/nome desempatou) -> par PROVAVEL, mas conferir


# ----------------------------------------------------------------------------
# Classificacao de pendencia nas categorias do operador (a "cauda" que nao fecha).
# Heuristica deterministica por lado + sinal + palavras-chave da descricao.
# Cada categoria sugere uma ACAO — e o que a analista quer ("explicar cada pendencia").
# ----------------------------------------------------------------------------
ACAO_PENDENCIA = {
    "TARIFA_IOF": "lançar no razão (despesa bancária)",
    "RENDIMENTO": "lançar no razão (receita financeira)",
    "PIX_ORFAO": "conferir — identificar o pagador",
    "LIQUIDO_ADQUIRENTE": "conciliar pelo líquido + linha de taxa",
    "LOTE_SISPAG": "lote de pagamento — conferir contra a remessa (informe a coluna Lote no razão p/ conciliar)",
    "A_LANCAR": "lançar no razão",
    "CHEQUE_NAO_COMPENSADO": "aguardar compensação no banco",
    "DEPOSITO_TRANSITO": "aguardar crédito no banco",
    "EM_TRANSITO": "aguardar / conferir",
}

# keywords ancoradas em termo bancario (evita falso-positivo tipo "TAXA CONDOMINIO"
# virar tarifa, ou "doc"/"ted" solto virar deposito — achado da revisao).
_KW = {
    "tarifa": ("tarifa", "tar ", "tar.", "iof", "cesta", "pacote de servico", "pacote servico",
               "manutencao de conta", "anuidade", "encargo", "ted tar", "tar ted",
               "debito automatico", "deb aut", "juros"),
    "rendimento": ("rendimento", "rend pago", "rend.", "aplic"),
    "adquirente": ("rede", "cielo", "getnet", "stone", "pagseguro", "mercado pago", "adquirente", "recebivel", "maquininha"),
    "pix": ("pix",),
    "cheque": ("cheque", "compensac"),
    "deposito": ("deposito", "dep.", "em transito", "transito"),
    # marcador de lote de pagamento (Itau SISPAG e equivalentes) — debito que soma
    # varios titulos de fornecedores; o detalhe do lote nao vem no extrato.
    "lote": ("sispag", "pag fornecedores", "pagamento fornecedores", "pagto fornecedores",
             "pag eletronico", "lote de pagamento", "pagamento em lote"),
}


def _norm_desc(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def classifica_pendencia(lado: str, valor: Decimal, descricao) -> str:
    """Rotula uma pendencia na categoria do operador. lado='EXTRATO' (so no banco,
    falta no razao) ou 'RAZAO' (so no razao, ainda nao no banco)."""
    d = _norm_desc(descricao)
    hit = lambda chave: any(k in d for k in _KW[chave])  # noqa: E731
    if lado == "EXTRATO":
        if valor < ZERO:  # saida no banco nao lancada
            if hit("lote"):
                return "LOTE_SISPAG"
            if hit("tarifa"):
                return "TARIFA_IOF"
            if hit("adquirente"):
                return "LIQUIDO_ADQUIRENTE"
            return "A_LANCAR"
        # entrada no banco nao lancada
        if hit("rendimento"):
            return "RENDIMENTO"
        if hit("adquirente"):
            return "LIQUIDO_ADQUIRENTE"
        if hit("pix"):
            return "PIX_ORFAO"
        return "A_LANCAR"
    # lado == RAZAO (no razao, falta no extrato)
    if valor < ZERO:
        if hit("cheque"):
            return "CHEQUE_NAO_COMPENSADO"
        return "EM_TRANSITO"
    if hit("deposito"):
        return "DEPOSITO_TRANSITO"
    return "EM_TRANSITO"


@dataclass
class Conciliacao:
    modo: str
    lancamentos: list = field(default_factory=list)
    contagem: dict = field(default_factory=dict)
    total_esquerdo: Decimal = ZERO
    total_direito: Decimal = ZERO
    diferenca_global: Decimal = ZERO
    rotulo_esquerdo: str = "ESQUERDO"
    rotulo_direito: str = "DIREITO"
    amarracao: dict | None = None
    integridade_ok: bool = True


# ----------------------------------------------------------------------------
# match_banco: cascata + amarracao de saldo.
# ----------------------------------------------------------------------------
def match_banco(extrato_tx: list[dict], razao: list[dict], *,
                tolerancia: Decimal = TOL_PADRAO, janela_dias: int = JANELA_PADRAO,
                saldo_extrato_final: Decimal | None = None,
                saldo_razao_final: Decimal | None = None) -> Conciliacao:
    consumido = [False] * len(razao)
    idx_valor: dict = defaultdict(list)
    por_cnpj: dict = defaultdict(list)          # cpf_cnpj -> indices do razao (prova de conflito, D9)
    for j, r in enumerate(razao):
        idx_valor[r["valor"]].append(j)
        if r.get("cpf_cnpj"):
            por_cnpj[r["cpf_cnpj"]].append(j)

    def afinidade(ext, r) -> tuple:
        """Quao fortemente este candidato (mesmo valor, dentro da janela) e o par certo.
        Maior = melhor. NAO cria match (o match e por valor+janela) — so DESEMPATA quando
        ha varios candidatos de mesmo valor. Ordem de forca: doc > identificador > CNPJ/CPF
        > overlap de nome da contraparte."""
        doc = 1 if ext.get("doc") and r.get("doc") and ext["doc"] == r["doc"] else 0
        ident = 1 if ext.get("identificador") and r.get("identificador") and ext["identificador"] == r["identificador"] else 0
        cnpj = 1 if ext.get("cpf_cnpj") and r.get("cpf_cnpj") and ext["cpf_cnpj"] == r["cpf_cnpj"] else 0
        nome = len(tokens_nome(ext.get("contraparte") or ext.get("descricao"))
                   & tokens_nome(r.get("contraparte") or r.get("descricao")))
        return (doc, ident, cnpj, nome)

    def melhor_exato(ext):
        cands = []
        for j in idx_valor.get(ext["valor"], ()):
            if consumido[j]:
                continue
            dd = abs((ext["data"] - razao[j]["data"]).days)
            if dd > janela_dias:
                continue
            if conflito_forte(ext, razao[j], j, por_cnpj):
                continue                              # D9: so a PROVA de par errado recusa
            # max por: afinidade, depois data mais proxima, depois razao mais antiga (FIFO)
            cands.append((afinidade(ext, razao[j]), -dd, -j, j))
        if not cands:
            return None, False
        cands.sort(reverse=True)
        # SPEC-07 #4: AMBIGUO quando 2+ candidatos empatam na afinidade MAXIMA -> o desempate
        # forte (doc/ident/CNPJ/nome) nao decidiu e a escolha caiu em data/FIFO (arbitraria p/ correcao).
        # O par mais provavel ainda concilia, mas o operador e avisado de ONDE conferir.
        top_afin = cands[0][0]
        ambiguo = sum(1 for c in cands if c[0] == top_afin) >= 2
        return cands[0][-1], ambiguo

    def melhor_tolerancia(ext):
        # Match por tolerancia (centavos) EXIGE afinidade > 0 (doc/identificador/CNPJ/nome).
        # Sem isso, dois lancamentos NAO relacionados de valor parecido cairiam como
        # "conciliado com diferenca" e esconderiam uma divergencia real (achado da revisao).
        # "Casar errado e pior que deixar pendente."
        cands = []
        for j, r in enumerate(razao):
            if consumido[j]:
                continue
            dd = abs((ext["data"] - r["data"]).days)
            if dd > janela_dias:
                continue
            vd = abs(ext["valor"] - r["valor"])
            if ZERO < vd <= tolerancia:
                if conflito_forte(ext, r, j, por_cnpj):
                    continue                          # D9
                afin = afinidade(ext, r)
                if afin == (0, 0, 0, 0):
                    continue                          # sem nenhum identificador batendo -> nao casa
                # max por: menor diferenca de valor, depois afinidade, depois data, FIFO
                cands.append((-vd, afin, -dd, -j, j))
        if not cands:
            return None
        cands.sort(reverse=True)
        return cands[0][-1]

    def chave_lote(r):
        """Chave de agrupamento do lote, da mais forte p/ a mais fraca:
        - `lote`/remessa EXPLICITA (ex.: nº SISPAG no razão): identifica a remessa
          inteira, **permite multi-contraparte** — a chave e a guarda anti falso-positivo.
        - CNPJ/CPF ou tokens do nome: lote conservador da MESMA contraparte (sem a remessa)."""
        if r.get("lote"):
            return ("lote", str(r["lote"]))
        if r.get("cpf_cnpj"):
            return ("cnpj", r["cpf_cnpj"])
        toks = tokens_nome(r.get("contraparte") or r.get("descricao"))
        return ("nome", frozenset(toks)) if toks else None

    def acha_lote(ext):
        """LOTE N:1: titulos NAO consumidos que compartilham uma chave (remessa explicita
        OU mesma contraparte), mesmo sinal, dentro da janela, somando o valor do debito.
        Remessa explicita casa a soma da remessa INTEIRA (qualquer tamanho); sem remessa,
        exige a mesma contraparte (CNPJ, ou nome com todos os tokens no extrato), nenhuma prova de par errado
        e UMA unica combinacao (ou so combinacoes de mesmos valores no mesmo grupo) que feche o valor.
        Deterministico. Devolve (combo, marcas `conferir`); combo None se nao achar ou se ambiguo."""
        alvo = ext["valor"]
        sinal_ext = alvo > ZERO
        toks_ext = tokens_nome(ext.get("contraparte") or ext.get("descricao"))
        grupos = defaultdict(list)
        for j, r in enumerate(razao):
            if consumido[j] or (r["valor"] > ZERO) != sinal_ext:
                continue
            if abs((ext["data"] - r["data"]).days) > janela_dias:
                continue
            k = chave_lote(r)
            if k is None:
                continue
            if k[0] != "lote" and conflito_forte(ext, r, j, por_cnpj):
                continue                              # D9/D10a: sem remessa explicita, titulo com prova de par errado nao entra
            grupos[k].append(j)
        def candidatas(idxs):
            """Combinacoes de um grupo: a remessa/grupo INTEIRO (qualquer tamanho) e depois os subconjuntos de
            2 a 8 titulos (so em grupo de ate 18; acima a forca bruta estoura -> conservador)."""
            yield tuple(idxs)
            if len(idxs) <= 18:
                for tam in range(2, min(8, len(idxs)) + 1):
                    if tam < len(idxs):               # tam == len(idxs) e o grupo inteiro, ja emitido
                        yield from combinations(idxs, tam)

        chaves = sorted(grupos, key=lambda x: (x[0], str(x[1])))
        # 1) remessa explicita (k[0]=="lote"): soma EXATA (tol=0) e a chave e a guarda; o 1o que fecha, como antes.
        for k in chaves:
            idxs = sorted(grupos[k])
            if k[0] != "lote" or len(idxs) < 2:
                continue
            for combo in candidatas(idxs):
                if sum((razao[j]["valor"] for j in combo), ZERO) == alvo:
                    return list(combo), ()
        # 2) sem remessa (CNPJ ou nome): enumera TODAS as combinacoes, de qualquer tamanho e grupo, ANTES de
        # consumir (D10c). Combinacoes do MESMO grupo com o MESMO multiconjunto de valores contam como uma: casa a
        # 1a da enumeracao e marca `lote_valores_iguais` (o dinheiro bate, so muda qual titulo leva). Valores
        # diferentes ou grupos diferentes = ambiguo = pendente ("casar errado e pior que deixar pendente").
        achadas, classes = [], set()
        for k in chaves:
            idxs = sorted(grupos[k])
            if k[0] == "lote" or len(idxs) < 2:
                continue
            if k[0] == "nome" and toks_ext and not k[1] <= toks_ext:
                continue                              # D10b: TODOS os tokens do nome do grupo no extrato (um em comum nao basta)
            for combo in candidatas(idxs):
                valores = tuple(sorted(razao[j]["valor"] for j in combo))
                if abs(sum(valores, ZERO) - alvo) <= tolerancia:
                    classes.add((k, valores))
                    if len(classes) > 1:
                        return None, ()
                    achadas.append(list(combo))
        if not achadas:
            return None, ()
        return achadas[0], (("lote_valores_iguais",) if len(achadas) > 1 else ())

    cont = Counter()
    lanc: list[Lancamento] = []
    pendentes_ext: list[Lancamento] = []
    for ext in extrato_tx:
        chosen, ambiguo = melhor_exato(ext)
        status = "CONCILIADO" if chosen is not None else None
        if chosen is None:
            chosen = melhor_tolerancia(ext)
            ambiguo = False                 # tolerancia ja exige afinidade>0 -> nao e escolha arbitraria
            if chosen is not None:
                status = "CONCILIADO_COM_DIFERENCA"

        if chosen is None:
            cont["PENDENTE_EXTRATO"] += 1
            cat = classifica_pendencia("EXTRATO", ext["valor"], ext.get("descricao"))
            l = Lancamento("EXTRATO", ext, "PENDENTE_EXTRATO", categoria=cat)
            lanc.append(l)
            pendentes_ext.append(l)
        else:
            consumido[chosen] = True
            r = razao[chosen]
            dif = (ext["valor"] - r["valor"]) if status == "CONCILIADO_COM_DIFERENCA" else ZERO
            lag = abs((ext["data"] - r["data"]).days)
            cont[status] += 1
            conferir = ("cpf_cnpj",) if divergente(ext, r) else ()      # D9: divergencia sem prova casa e marca
            lanc.append(Lancamento("EXTRATO", ext, status, par_idx=chosen, diferenca=dif, lag_dias=lag, ambiguo=ambiguo,
                                   conferir=conferir))

    # --- passe de LOTE (N:1): so depois do 1:1, sobre os debitos/creditos ainda pendentes ---
    for l in pendentes_ext:
        combo, marcas = acha_lote(l.registro)
        if not combo:
            continue
        for j in combo:
            consumido[j] = True
        l.status = "CONCILIADO_LOTE"
        l.componentes = combo
        l.par_idx = combo[0]
        l.diferenca = l.registro["valor"] - sum((razao[j]["valor"] for j in combo), ZERO)   # D8: centavos do lote entram na amarracao
        sem_prova = not razao[combo[0]].get("lote") and any(divergente(l.registro, razao[j]) for j in combo)
        l.conferir = (("cpf_cnpj",) if sem_prova else ()) + marcas    # D9 (divergencia sem prova) e D10c (mesmos valores)
        l.categoria = ""
        cont["PENDENTE_EXTRATO"] -= 1
        cont["CONCILIADO_LOTE"] += 1
    if cont.get("PENDENTE_EXTRATO") == 0:
        cont.pop("PENDENTE_EXTRATO", None)

    for j, r in enumerate(razao):
        if not consumido[j]:
            cont["PENDENTE_RAZAO"] += 1
            cat = classifica_pendencia("RAZAO", r["valor"], r.get("descricao"))
            lanc.append(Lancamento("RAZAO", r, "PENDENTE_RAZAO", categoria=cat))

    tot_ext = sum((t["valor"] for t in extrato_tx), ZERO)
    tot_raz = sum((r["valor"] for r in razao), ZERO)

    # --- AMARRACAO (checksum da conciliacao bancaria) ---
    # Partindo do saldo do razao, incorpora o que falta lancar e remove o que ainda
    # nao caiu no banco, mais o residuo dos pares conciliados-com-diferenca:
    #   saldo_razao_final
    #     + Σ(PENDENTE_EXTRATO)            # no banco, falta no razao (tarifa, IOF, juros)
    #     - Σ(PENDENTE_RAZAO)              # no razao, ainda nao no banco (cheque/deposito em transito)
    #     + Σ(diferenca dos conciliados)   # centavos que separam os pares com diferenca
    #   == saldo_extrato_final (LEDGERBAL)
    amarr = None
    integridade_ok = True
    if saldo_extrato_final is not None and saldo_razao_final is not None:
        soma_pend_ext = sum((l.registro["valor"] for l in lanc if l.status == "PENDENTE_EXTRATO"), ZERO)
        soma_pend_raz = sum((l.registro["valor"] for l in lanc if l.status == "PENDENTE_RAZAO"), ZERO)
        soma_dif = sum((l.diferenca for l in lanc if l.status in ("CONCILIADO_COM_DIFERENCA", "CONCILIADO_LOTE")), ZERO)
        esperado = saldo_razao_final + soma_pend_ext - soma_pend_raz + soma_dif
        residuo = (saldo_extrato_final - esperado).quantize(Decimal("0.01"))
        integridade_ok = residuo == ZERO
        amarr = {
            "saldo_extrato_final": str(saldo_extrato_final),
            "saldo_razao_final": str(saldo_razao_final),
            "ajuste_pendente_extrato": str(soma_pend_ext),
            "ajuste_pendente_razao": str(soma_pend_raz),
            "ajuste_diferenca_conciliados": str(soma_dif),
            "saldo_extrato_esperado": str(esperado),
            "residuo": str(residuo),
            "fecha": integridade_ok,
        }
        amarr["diagnostico"] = diagnostica_residuo(amarr, lanc)

    return Conciliacao(
        modo="banco", lancamentos=lanc, contagem=dict(cont),
        total_esquerdo=tot_ext, total_direito=tot_raz, diferenca_global=tot_ext - tot_raz,
        rotulo_esquerdo="EXTRATO", rotulo_direito="RAZAO",
        amarracao=amarr, integridade_ok=integridade_ok,
    )


# ----------------------------------------------------------------------------
# Resumo privado — o UNICO objeto que sobe para o Claude (sem dado bruto).
# ----------------------------------------------------------------------------
def resumo_privado(c: Conciliacao) -> dict:
    total = len(c.lancamentos)
    conc = (c.contagem.get("CONCILIADO", 0) + c.contagem.get("CONCILIADO_COM_DIFERENCA", 0)
            + c.contagem.get("CONCILIADO_LOTE", 0))
    # quebra das pendencias por categoria do operador (a "cauda") + acao sugerida
    cats = Counter(l.categoria for l in c.lancamentos if l.categoria)
    pend_cat = {k: {"qtd": v, "acao": ACAO_PENDENCIA.get(k, "")} for k, v in sorted(cats.items())}
    return {
        "modo": c.modo,
        "registros": total,
        "contagem_por_status": c.contagem,
        "pendencias_por_categoria": pend_cat,
        # SPEC-07 #4: conciliacoes onde 2+ lancamentos de mesmo valor disputaram sem identificador
        # que desempate -> par provavel, MAS o operador deve conferir (no Excel). 0 = nada ambiguo.
        "conciliados_ambiguos": sum(1 for l in c.lancamentos if l.ambiguo),
        # D9: conciliacoes em que o cpf_cnpj do banco difere do razao sem prova de par errado (confira no Excel)
        "conferir_cpf_cnpj": sum(1 for l in c.lancamentos if "cpf_cnpj" in l.conferir),
        # D10c: lotes sem remessa em que combinacoes de mesmos valores do mesmo grupo empataram (confira quais titulos)
        "conferir_lote_valores_iguais": sum(1 for l in c.lancamentos if "lote_valores_iguais" in l.conferir),
        "taxa_conciliacao_pct": round(100 * conc / total, 1) if total else 0.0,
        "total_" + c.rotulo_esquerdo.lower(): str(c.total_esquerdo),
        "total_" + c.rotulo_direito.lower(): str(c.total_direito),
        "diferenca_global": str(c.diferenca_global),
        "controle_lote": controle_lote(c),
        "amarracao": c.amarracao,
        "integridade_ok": c.integridade_ok,
    }


def controle_lote(c: Conciliacao) -> dict | None:
    """Figura de CONTROLE p/ a cauda de lote (SISPAG) que nao casa por falta da remessa
    no razao: agrega o total dos debitos de lote (banco) x total dos titulos de SAIDA
    pendentes (razao) + a diferenca. NAO pareia linha-a-linha (seria falso-positivo) —
    da o "bate no agregado?" e aponta a remessa p/ o detalhe. None se nao ha debito de lote.
    So somas/contagens -> seguro p/ a IA (contrato de privacidade)."""
    deb_lote = [l for l in c.lancamentos
                if l.lado == "EXTRATO" and l.status == "PENDENTE_EXTRATO" and l.categoria == "LOTE_SISPAG"]
    if not deb_lote:
        return None
    saidas_pend = [l for l in c.lancamentos
                   if l.lado == "RAZAO" and l.status == "PENDENTE_RAZAO" and l.registro["valor"] < ZERO]
    tot_b = sum((l.registro["valor"] for l in deb_lote), ZERO)
    tot_r = sum((l.registro["valor"] for l in saidas_pend), ZERO)
    return {
        "qtd_debitos_lote": len(deb_lote),
        "total_debitos_lote": str(tot_b),
        "qtd_titulos_pendentes": len(saidas_pend),
        "total_titulos_pendentes": str(tot_r),
        "diferenca": str(tot_b - tot_r),
    }


def diagnostica_residuo(amarr: dict | None, lancamentos: list[Lancamento]) -> dict | None:
    """Quando a amarracao NAO fecha, explica o residuo: causa provavel + acao.

    O checksum sozinho ("residuo X") deixa a analista sem saber o que investigar. Aqui o
    motor aponta a causa, usando SO numeros/categorias ja expostos no resumo (residuo, saldos,
    categorias) -> nao vaza nenhuma linha bruta. Duas causas cobrem o grosso:
      - SALDO do razao informado errado (a nº1): diz o saldo IMPLICITO pelos lancamentos
        (saldo_razao + residuo). Se os lancamentos estao certos, esse e o saldo correto.
      - Uma PENDENCIA isolada cujo valor explica o residuo: PENDENTE_RAZAO de valor == residuo
        (linha no razao sem contrapartida no banco) ou PENDENTE_EXTRATO de valor == -residuo
        (lancamento do banco ainda fora do razao). Aponta a(s) categoria(s) p/ conferir.
    Retorna None se a amarracao fecha ou nao foi calculada."""
    if not amarr or amarr.get("fecha"):
        return None
    residuo = Decimal(amarr["residuo"])
    if residuo == ZERO:
        return None
    saldo_razao = Decimal(amarr["saldo_razao_final"])
    explicam: list[str] = []
    for l in lancamentos:
        v = l.registro["valor"]
        if l.status == "PENDENTE_RAZAO" and v == residuo:
            explicam.append(l.categoria or "EM_TRANSITO")
        elif l.status == "PENDENTE_EXTRATO" and v == -residuo:
            explicam.append(l.categoria or "A_LANCAR")
    diag = {
        "residuo": str(residuo),
        "saldo_razao_informado": str(saldo_razao),
        "saldo_razao_implicito": str(saldo_razao + residuo),
    }
    if explicam:
        diag["causa_provavel"] = "pendencia"
        diag["pendencias_que_explicam"] = {
            "qtd": len(explicam),
            "categorias": dict(sorted(Counter(explicam).items())),
        }
        diag["acao"] = ("o residuo coincide com pendencia(s) de mesmo valor; confira se essa "
                        "linha esta digitada certo ou se pertence a este mes")
    else:
        diag["causa_provavel"] = "saldo"
        diag["acao"] = ("nenhuma pendencia isolada explica o residuo; o saldo do razao informado "
                        f"provavelmente esta errado (pelos lancamentos deveria ser {saldo_razao + residuo})")
    return diag
