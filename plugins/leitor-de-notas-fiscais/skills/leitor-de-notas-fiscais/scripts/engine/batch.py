from __future__ import annotations

import io
import zipfile

from engine.avaliacao import avaliar_nfe, avaliar_nfse
from engine.dispatch import marcar_limites_do_xml, parsear
from engine.export.csv_generico import exportar_excecoes
from engine.export.linha import montar_linha
from engine.export.perfis import exportar_perfil
from engine.extracao import montar_nfe_de_extracao, montar_nfse_de_extracao
from engine.router import Familia

class Recusa(ValueError):
    """Recusa do proprio motor: texto fixo, so com numeros e limites (nunca texto do arquivo)."""


CAP_LOTE = 50  # §10-A: cap único por lote, configurável

# Anti zip-bomb (PRD-SAN-07 S-02): limites inspecionados no file_size DECLARADO
# (z.getinfo), ANTES de descomprimir qualquer byte.
MAX_UNCOMPRESSED_PER_FILE = 50 * 1024 * 1024   # 50 MB por arquivo
MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024     # 500 MB no acumulado do lote
RAZAO_COMPRESSAO_SUSPEITA = 1000               # file_size/compress_size > 1000 = bomb provável


MOTIVO_FORA_DO_LIMITE = f"acima do limite de {CAP_LOTE} por lote; rode de novo com o resto"
MOTIVO_REPETIDA = "nota repetida no lote (mesma chave): so a primeira vai para a carga"


def _repetida(linha: dict, vistas: set[str]) -> bool:
    """True na 2a ocorrencia da mesma nota: chave de acesso (44/50 digitos) ou chave de reserva com CNPJ e numero.
    A reserva sem CNPJ ou sem numero sai igual para notas diferentes, entao nao conta; com eles, vale dentro da
    mesma familia (a mesma nota nao sai em dois padroes municipais)."""
    chave = str(linha.get("chave_arquivo") or "")
    partes = chave.split("_")
    if chave.isdigit() and len(chave) in (44, 50):
        ident = chave
    elif len(partes) in (6, 7) and partes[3] and partes[4]:  # 7 = com serie
        ident = f"{linha.get('familia') or linha.get('tipo_documento')}|{chave}"
    else:
        return False
    if ident in vistas:
        return True
    vistas.add(ident)
    return False


def _linhas_fora_do_limite(nomes: list[str]) -> list[dict]:
    return [{"arquivo_origem": n, "motivo": MOTIVO_FORA_DO_LIMITE} for n in nomes]


def processar_lote(arquivos: list[tuple[str, bytes | str | Recusa | None]], perfil: str = "generico", tomador_ref=None) -> dict:
    """arquivos = list[(nome, conteudo XML)]. Retorna csv + resumo + excecoes + linhas.

    `conteudo` None = item que o chamador nao abriu por estar alem do corte (vira "fora do limite");
    `Recusa` = arquivo recusado na leitura (vira exceção e o lote segue).
    Alem de CAP_LOTE itens processaveis, o excedente tambem vira "fora do limite" (nunca é mudo).
    `tomador_ref` (opcional, uma vez por lote) e repassado a avaliacao no ramo NFS-e.
    """
    linhas: list[dict] = []
    excecoes: list[dict] = []
    fora: list[str] = []
    resumo = {"total": 0, "auto_aprovadas": 0, "conferir": 0, "falhou": 0,
              "recebidas": len(arquivos), "fora_do_limite": 0, "repetidas": 0, "por_familia": {}}

    lidos = 0
    vistas: set[str] = set()
    for nome, conteudo in arquivos:
        if conteudo is None or lidos >= CAP_LOTE:
            fora.append(nome)
            continue
        lidos += 1
        try:
            if isinstance(conteudo, Recusa):
                raise conteudo
            xml = conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo
            fam, modelo = parsear(xml)
            if modelo is None:
                excecoes.append({"arquivo_origem": nome, "motivo": "família não reconhecida"})
                resumo["falhou"] += 1
                continue
            if fam == Familia.NFE:
                rel = avaliar_nfe(modelo)
            else:
                rel = avaliar_nfse(modelo, tomador_ref=tomador_ref,
                                   aliquota_opcional=fam == Familia.NFSE_NACIONAL)
            rel["familia"] = fam.value
            marcar_limites_do_xml(fam, xml, rel)
            linha = montar_linha(modelo, rel, nome)
            if _repetida(linha, vistas):  # a mesma nota de novo: o ERP lancaria duas vezes
                excecoes.append({"arquivo_origem": nome, "chave_arquivo": linha.get("chave_arquivo"), "motivo": MOTIVO_REPETIDA})
                resumo["repetidas"] += 1
                continue
            linhas.append(linha)
            resumo["total"] += 1
            resumo["por_familia"][fam.value] = resumo["por_familia"].get(fam.value, 0) + 1
            if linha["status"] == "auto-aprovada":
                resumo["auto_aprovadas"] += 1
            else:
                resumo["conferir"] += 1
        except Exception as e:  # degradação graciosa: nota ruim vira exceção, não derruba o lote
            excecoes.append({"arquivo_origem": nome, "motivo": f"erro ao processar: {e}"})  # saida-ok: vai so para o excecoes.csv local; a SKILL veta o agente de abrir o CSV
            resumo["falhou"] += 1

    resumo["fora_do_limite"] = len(fora)
    excecoes.extend(_linhas_fora_do_limite(fora))
    excecoes.extend(exportar_excecoes(linhas))
    return {
        "csv": exportar_perfil(linhas, perfil),
        "resumo": resumo,
        "excecoes": excecoes,
        "linhas": linhas,
    }


def processar_zip(zip_bytes: bytes, perfil: str = "generico", tomador_ref=None) -> dict:
    """Descompacta o ZIP e processa os arquivos .xml. (PDF no lote = orquestrado pela skill.)

    Anti zip-bomb (PRD-SAN-07 S-02): cap de 50 arquivos e limites de tamanho são
    aplicados sobre o tamanho descomprimido DECLARADO, antes de qualquer `z.read`.
    Entrada acima do limite/suspeita vira exceção no relatório (não derruba o lote);
    estourar o TOTAL do lote aborta com `ValueError` de mensagem clara.
    """
    excecoes_zip: list[dict] = []
    arquivos: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        nomes = sorted(n for n in z.namelist() if n.lower().endswith(".xml"))  # como a pasta: o corte de 50 nao depende da ordem do ZIP
        total_declarado = 0
        for nome in nomes[:CAP_LOTE]:  # cap do lote ANTES de ler qualquer conteúdo
            info = z.getinfo(nome)
            if info.file_size > MAX_UNCOMPRESSED_PER_FILE:
                excecoes_zip.append({"arquivo_origem": nome, "motivo": (
                    f"recusado: tamanho descomprimido declarado "
                    f"({info.file_size // (1024 * 1024)} MB) excede o limite de "
                    f"{MAX_UNCOMPRESSED_PER_FILE // (1024 * 1024)} MB por arquivo")})
                continue
            if info.file_size / max(info.compress_size, 1) > RAZAO_COMPRESSAO_SUSPEITA:
                excecoes_zip.append({"arquivo_origem": nome, "motivo": (
                    "recusado: taxa de compressão suspeita (possível zip-bomb)")})
                continue
            total_declarado += info.file_size
            if total_declarado > MAX_TOTAL_UNCOMPRESSED:
                raise Recusa(
                    f"lote recusado: total descomprimido do ZIP excede "
                    f"{MAX_TOTAL_UNCOMPRESSED // (1024 * 1024)} MB (possível zip-bomb); "
                    "divida o lote em ZIPs menores")
            arquivos.append((nome, z.read(nome)))
    arquivos += [(n, None) for n in nomes[CAP_LOTE:]]  # alem do corte: sem abrir, viram "fora do limite"
    res = processar_lote(arquivos, perfil, tomador_ref=tomador_ref)
    if excecoes_zip:
        res["excecoes"] = excecoes_zip + res["excecoes"]
        res["resumo"]["falhou"] += len(excecoes_zip)
    res["resumo"]["recebidas"] = len(nomes)
    return res


def _modelo_e_avaliacao(ex: dict, tomador_ref):
    """Roteia 1 dict de extracao (do Claude) -> (modelo, relatorio). Levanta em entrada invalida."""
    classe = ex.get("classe")
    campos = ex.get("campos", {})
    if classe == "nfse":
        # `simples_nacional` e `cancelada` sao metas no topo da extracao (irmao de `campos`,
        # como o prompt emite): repassa ao builder, que separa do _campos e converte p/ bool.
        nfse_in = dict(campos)
        for _meta in ("simples_nacional", "cancelada"):
            if _meta in ex:
                nfse_in[_meta] = ex[_meta]
        modelo = montar_nfse_de_extracao(nfse_in)
        rel = avaliar_nfse(modelo, tomador_ref=tomador_ref)
        rel["tipo_documento"] = "nfse"
        return modelo, rel
    if classe == "nfe":
        nfe_in = dict(campos)
        if "cancelada" in ex:  # `cancelada` (carimbo) vale p/ NF-e tambem
            nfe_in["cancelada"] = ex["cancelada"]
        modelo = montar_nfe_de_extracao(nfe_in)
        rel = avaliar_nfe(modelo)
        rel["tipo_documento"] = "nfe"
        return modelo, rel
    raise ValueError("documento nao e nota fiscal NFS-e/NF-e (fora do escopo do leitor)")


def processar_extracoes(extracoes: list[tuple[str, dict]], perfil: str = "generico", tomador_ref=None) -> dict:
    """Lote do caminho PDF: cada (nome, dict de extracao do Claude) -> linha de carga.
    Mesma estrutura de retorno de processar_lote."""
    linhas: list[dict] = []
    excecoes: list[dict] = []
    resumo = {"total": 0, "auto_aprovadas": 0, "conferir": 0, "falhou": 0,
              "recebidas": len(extracoes), "fora_do_limite": len(extracoes[CAP_LOTE:]), "repetidas": 0, "por_tipo": {}}
    vistas: set[str] = set()
    for nome, ex in extracoes[:CAP_LOTE]:
        try:
            modelo, rel = _modelo_e_avaliacao(ex, tomador_ref)
            linha = montar_linha(modelo, rel, nome)
            if _repetida(linha, vistas):
                excecoes.append({"arquivo_origem": nome, "chave_arquivo": linha.get("chave_arquivo"), "motivo": MOTIVO_REPETIDA})
                resumo["repetidas"] += 1
                continue
            linhas.append(linha)
            resumo["total"] += 1
            t = linha.get("tipo_documento") or "desconhecido"
            resumo["por_tipo"][t] = resumo["por_tipo"].get(t, 0) + 1
            resumo["auto_aprovadas" if linha["status"] == "auto-aprovada" else "conferir"] += 1
        except Exception as e:  # degradacao graciosa
            excecoes.append({"arquivo_origem": nome, "motivo": f"erro ao processar: {e}"})  # saida-ok: vai so para o excecoes.csv local; a SKILL veta o agente de abrir o CSV
            resumo["falhou"] += 1
    excecoes.extend(_linhas_fora_do_limite([n for n, _ in extracoes[CAP_LOTE:]]))
    excecoes.extend(exportar_excecoes(linhas))
    return {"csv": exportar_perfil(linhas, perfil), "resumo": resumo,
            "excecoes": excecoes, "linhas": linhas}
