# -*- coding: utf-8 -*-
"""Regressao de seguranca do leitor (PRD-SAN-07: S-01 XXE, S-02 zip-bomb, S-06 arquivo gigante).

Gate de produto: o pacote so e "pronto p/ vender" com esta suite verde.
"""
from __future__ import annotations

import io
import os
import time
import xml.etree.ElementTree as ET
import zipfile

import pytest

import ler_notas
from engine.batch import processar_zip
from engine.dispatch import parsear, processar
from engine.parsers._safe_xml import parse as parse_xml_seguro
from engine.parsers.xml_abrasf import parse_nfse_abrasf
from engine.parsers.xml_nacional import parse_nfse_nacional
from engine.parsers.xml_nfe import parse_nfe
from engine.parsers.xml_sp import parse_nfse_sp
from engine.router import Familia, classificar

from tests.layout import EXEMPLO  # noqa: E402

# ---------------------------------------------------------------- S-01: XXE

XXE = (
    '<?xml version="1.0"?>\n'
    '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
    '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
    '<infNFe Id="NFe1"><emit><xNome>&xxe;</xNome></emit></infNFe></NFe>'
)

BILLION_LAUGHS = (
    '<?xml version="1.0"?>\n'
    "<!DOCTYPE lolz [\n"
    '<!ENTITY lol "lol">\n'
    '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
    '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'
    '<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">\n'
    '<!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">\n'
    '<!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">\n'
    '<!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">\n'
    '<!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">\n'
    '<!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">\n'
    "]>\n"
    "<lolz>&lol9;</lolz>"
)

PARSERS = [parse_nfse_nacional, parse_nfse_abrasf, parse_nfse_sp, parse_nfe]


@pytest.mark.parametrize("parser", PARSERS, ids=lambda p: p.__name__)
def test_xxe_entidade_externa_rejeitada_nos_4_parsers(parser):
    with pytest.raises(ET.ParseError) as exc:
        parser(XXE)
    # rejeicao tratada, com mensagem clara — e SEM conteudo de arquivo local vazado
    assert "seguranca" in str(exc.value)
    assert "root:" not in str(exc.value)


def test_xxe_no_router_vira_desconhecido():
    assert classificar(XXE) == Familia.DESCONHECIDO


def test_xxe_no_processar_vira_rejeicao_tratada():
    rel = processar(XXE)  # nao levanta: vira rejeicao no relatorio
    assert rel["erro"] == "familia nao reconhecida"
    assert rel["familia"] == Familia.DESCONHECIDO.value


def test_billion_laughs_rejeitado_rapido():
    t0 = time.monotonic()
    with pytest.raises(ET.ParseError):
        parse_xml_seguro(BILLION_LAUGHS)
    assert time.monotonic() - t0 < 2.0, "rejeicao deve ser imediata (sem expandir entidades)"


@pytest.mark.parametrize("nome", [
    "nfse-nacional.xml", "nfse-abrasf.xml", "nfse-sp.xml", "nfe-produto.xml",
])
def test_regressao_xml_legitimo_continua_parseando(nome):
    with open(os.path.join(EXEMPLO, nome), "rb") as f:
        xml = f.read().decode("utf-8")
    fam, modelo = parsear(xml)
    assert fam != Familia.DESCONHECIDO
    assert modelo is not None


# ---------------------------------------------------------- S-02: zip-bomb

def _zip_com(entradas: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for nome, dados in entradas:
            z.writestr(nome, dados)
    return buf.getvalue()


def test_zip_entrada_acima_de_50mb_recusada_antes_do_read(monkeypatch):
    zb = _zip_com([("bomba.xml", b"0" * (51 * 1024 * 1024))])  # 51 MB declarados (reais)

    def nao_le(self, *a, **k):
        raise AssertionError("z.read foi chamado para entrada que devia ser recusada antes")
    monkeypatch.setattr(zipfile.ZipFile, "read", nao_le)

    res = processar_zip(zb)
    assert res["resumo"]["falhou"] == 1
    assert any("excede o limite" in e["motivo"] for e in res["excecoes"])


def test_zip_taxa_de_compressao_suspeita_recusada(monkeypatch):
    zb = _zip_com([("suspeito.xml", b"<x/>")])
    real_getinfo = zipfile.ZipFile.getinfo

    def fudge(self, nome):
        info = real_getinfo(self, nome)
        info.file_size = 10 * 1024 * 1024  # 10 MB declarados...
        info.compress_size = 1024          # ...em 1 KB comprimido => razao 10240 > 1000
        return info
    monkeypatch.setattr(zipfile.ZipFile, "getinfo", fudge)
    monkeypatch.setattr(zipfile.ZipFile, "read",
                        lambda *a, **k: pytest.fail("entrada suspeita nao deveria ser lida"))

    res = processar_zip(zb)
    assert any("zip-bomb" in e["motivo"] for e in res["excecoes"])


def test_zip_total_acima_de_500mb_aborta_o_lote(monkeypatch):
    zb = _zip_com([(f"n{i:02d}.xml", b"<x/>") for i in range(12)])
    real_getinfo = zipfile.ZipFile.getinfo

    def fudge(self, nome):
        info = real_getinfo(self, nome)
        info.file_size = 46 * 1024 * 1024      # cada um abaixo do cap de 50 MB...
        info.compress_size = 40 * 1024 * 1024  # ...com razao de compressao normal
        return info
    monkeypatch.setattr(zipfile.ZipFile, "getinfo", fudge)
    monkeypatch.setattr(zipfile.ZipFile, "read", lambda self, nome, *a, **k: b"<x/>")

    with pytest.raises(ValueError) as exc:   # 46 MB x 11 = 506 MB > 500 MB
        processar_zip(zb)
    assert "500" in str(exc.value)


def test_regressao_zip_normal_processa():
    nomes = ["nfse-nacional.xml", "nfe-produto.xml"]
    entradas = []
    for n in nomes:
        with open(os.path.join(EXEMPLO, n), "rb") as f:
            entradas.append((n, f.read()))
    res = processar_zip(_zip_com(entradas))
    assert res["resumo"]["total"] == 2
    assert res["resumo"]["falhou"] == 0
    assert res["resumo"]["recebidas"] == 2 and res["resumo"]["fora_do_limite"] == 0


# --------------------------------------------- S-06: arquivo gigante (100 MB)

def test_arquivo_acima_de_100mb_recusado_sem_ler(monkeypatch, tmp_path):
    arq = tmp_path / "grande.xml"
    arq.write_text("<x/>", encoding="utf-8")
    monkeypatch.setattr(ler_notas.os.path, "getsize", lambda p: 101 * 1024 * 1024)
    with pytest.raises(ValueError) as exc:
        ler_notas._coletar(str(arq))
    assert "100 MB" in str(exc.value)


def test_cli_erro_claro_sem_stack_em_arquivo_gigante(monkeypatch, tmp_path, capsys):
    arq = tmp_path / "grande.xml"
    arq.write_text("<x/>", encoding="utf-8")
    monkeypatch.setattr(ler_notas.os.path, "getsize", lambda p: 101 * 1024 * 1024)
    rc = ler_notas.main(["validar", "--entrada", str(arq)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "[erro]" in err and "100 MB" in err
    assert "Traceback" not in err


def test_regressao_arquivo_normal_continua_aceito(tmp_path):
    arq = tmp_path / "mini.xml"
    with open(os.path.join(EXEMPLO, "nfse-nacional.xml"), "rb") as f:
        arq.write_bytes(f.read())
    tipo, dados = ler_notas._coletar(str(arq))
    assert tipo == "xmls" and len(dados) == 1
