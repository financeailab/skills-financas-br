# -*- coding: utf-8 -*-
"""OCR LOCAL (SPEC-02) — imagem/PDF escaneado -> texto -> conciliacao. 100% local
(Tesseract), OPT-IN e SKIP-SAFE: sem o binario, imagem/escaneado seguem PRECISA_OCR.

Rodar:  python tests/test_ocr.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "skills", "conciliacao-bancaria", "scripts", "engine")
sys.path.insert(0, ENGINE)

from ingest_extrato import ingest_extrato, ocr_disponivel   # noqa: E402

casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn)); return fn
    return deco


def _img_com_texto(txt):
    """Gera um PNG branco com `txt` em preto (p/ o Tesseract ler)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (900, 90), "white")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 34)
        except Exception:
            font = ImageFont.load_default()
    d.text((12, 25), txt, fill="black", font=font)
    p = os.path.join(tempfile.mkdtemp(prefix="ocr_"), "extrato.png")
    im.save(p)
    return p


@caso("OPT-IN: imagem com ocr=False -> PRECISA_OCR (fosso intacto, default)")
def _():
    # dummy .png (nao abre o arquivo no caminho ocr=False) -> sem dependencia de PIL (CI stdlib-pura)
    p = os.path.join(tempfile.mkdtemp(prefix="ocr_optin_"), "x.png")
    open(p, "wb").write(b"\x89PNG\r\n")
    r = ingest_extrato(p)          # default ocr=False
    assert r.status == "PRECISA_OCR" and r.fonte == "imagem", (r.status, r.fonte)


@caso("ocr_disponivel() devolve bool sem quebrar")
def _():
    assert isinstance(ocr_disponivel(), bool)


@caso("OCR REAL: imagem com data+valor -> extrai transacao (skip se sem Tesseract)")
def _():
    if not ocr_disponivel():       # checa ANTES de tocar PIL -> CI sem Tesseract pula limpo
        print("       [SKIP] Tesseract nao instalado"); return
    p = _img_com_texto("02/01/2026 PAGTO FORNEC -100,00")
    r = ingest_extrato(p, ocr=True)
    assert r.status == "ATENCAO", r.status
    assert len(r.transacoes) >= 1, r.transacoes
    # o valor -100,00 deve aparecer entre os extraidos
    from decimal import Decimal
    vals = [t["valor"] for t in r.transacoes]
    assert Decimal("-100.00") in vals, vals


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
    print(f"==> OCR OK: {len(casos)} casos travados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
