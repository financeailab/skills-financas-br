from __future__ import annotations

from engine.model import NFSeServico

_CRITICOS = ("valor_servicos", "iss_valor", "valor_liquido", "emitente_cnpj")


def _val(campo):
    return campo.valor if (campo is not None and campo.valor is not None) else None


def cruzar_nfse(nf_xml: NFSeServico, nf_pdf: NFSeServico) -> dict:
    """Cruza campos críticos de uma NFS-e lida por XML e por PDF; divergência = sinalização."""
    divergencias = []
    for campo in _CRITICOS:
        a = _val(getattr(nf_xml, campo))
        b = _val(getattr(nf_pdf, campo))
        if a is not None and b is not None and a != b:
            divergencias.append({"campo": campo, "xml": str(a), "pdf": str(b)})
    return {
        "ok": not divergencias,
        "divergencias": divergencias,
        "motivos": [f"XML e PDF divergem em {d['campo']}: {d['xml']} vs {d['pdf']}" for d in divergencias],
    }
