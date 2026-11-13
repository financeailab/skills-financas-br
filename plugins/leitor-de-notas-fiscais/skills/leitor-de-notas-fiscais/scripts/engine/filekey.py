from __future__ import annotations

import re
import unicodedata


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\s+", "-", s.strip())
    return re.sub(r"[^A-Za-z0-9_-]", "", s)


def _so_digitos(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def file_key(
    chave_acesso: str | None,
    modelo: str,
    *,
    uf: str | None = None,
    municipio_ibge: str | None = None,
    cnpj_prestador: str | None = None,
    numero: str | None = None,
    aaaamm: str | None = None,
    serie: str | None = None,
) -> str:
    """Chave deterministica: chave de acesso (50/44) como primaria; senao fallback composto."""
    if chave_acesso:
        digs = _so_digitos(chave_acesso)
        if len(digs) in (44, 50):
            return digs
    prefixo = {"NFSe": "NFSE", "NFe": "NFE"}.get(modelo, _slug(modelo).upper() or "DOC")
    partes = [
        prefixo,
        _slug(uf or ""),
        _so_digitos(municipio_ibge or ""),
        _so_digitos(cnpj_prestador or ""),
        _slug(numero or ""),
        _so_digitos(aaaamm or ""),
    ]
    if serie:  # 7a parte so quando existe: sem serie o formato segue o de sempre
        partes.append(_slug(serie).replace("_", "-"))  # "_" separa as partes
    return "_".join(partes)
