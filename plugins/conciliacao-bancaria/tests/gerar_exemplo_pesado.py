# -*- coding: utf-8 -*-
"""Gera um mes PESADO e SINTETICO (zero dado real) p/ stress-test da conciliadora.

Monta uma pasta-mae com 1 subpasta por conta (banco), cada uma com:
  - extrato em formato variado (OFX / CSV / XLSX), p/ exercitar o dispatcher;
  - razao.csv no modelo, com a maioria casando e casos-limite injetados de proposito.

Casos-limite cobertos (p/ validar o motor em escala):
  - lote SISPAG N:1 (1 debito do banco = soma de varios titulos da razao, via coluna Lote);
  - pendencias no extrato (tarifa/IOF/rendimento) e no razao (cheque/deposito em transito);
  - conciliado-com-diferenca (centavos dentro da tolerancia);
  - credito sem razao (orientacao contas-a-receber);
  - banco que exporta saldo zerado (Bradesco/Santander) — so afeta amarracao (pasta nao amarra).

Deterministico (sem random): tudo derivado do indice. Reproduzivel.

Uso:  python tests/gerar_exemplo_pesado.py [pasta_destino] [txns_por_conta]
       (default: _exemplo-pesado/  e  120 txns/conta  ->  ~900 lancamentos)
"""
import os
import sys
from datetime import date, timedelta

# (nome, bankid, formato_extrato, saldo_zerado?)
BANCOS = [
    ("Itau", "0341", "ofx", False),
    ("Bradesco", "0237", "csv", True),
    ("Santander", "0033", "ofx", True),
    ("BancoDoBrasil", "0001", "xlsx", False),
    ("Caixa", "0104", "csv", False),
    ("Exemplo", "0422", "ofx", False),
    ("Inter", "0077", "xlsx", False),
    ("Nubank", "0260", "ofx", False),
]
BASE = date(2026, 5, 1)
HDR = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _cnpj(i):
    n = f"{(i * 37 + 11) % 100000000:08d}"
    return f"12.{n[0:3]}.{n[3:6]}/0001-{n[6:8]}"


def gera_conta(idx, banco, txns):
    """Devolve (linhas_extrato, linhas_razao) como listas de dicts canonicos do gerador.
    Cada item: dict(data=date, valor=Decimal-like str '-1234.56'(extrato) / '-1234,56'(razao BR),
    memo/contraparte, doc, lote)."""
    ext = []   # (dtposted 'YYYYMMDD', trnamt '-1234.56', memo)
    raz = []   # (data 'DD/MM/YYYY', valor '-1234,56', contraparte, cnpj, hist, lote, doc)
    saldo = 0.0

    for i in range(txns):
        d = BASE + timedelta(days=(i % 28))
        dt = d.strftime("%Y%m%d")
        dbr = d.strftime("%d/%m/%Y")
        seq = idx * 1000 + i
        # alterna entrada/saida; valores deterministicos
        saida = (i % 3) != 0
        base_val = round(50 + (seq * 7.13) % 4800, 2)
        val = -base_val if saida else base_val
        contra = ("FORNEC" if saida else "CLIENTE") + f" {idx:02d}{i:03d}"
        doc = f"D{seq:06d}"

        caso = i % 20
        if caso == 3:
            # pendente no extrato: tarifa (so no banco)
            ext.append((dt, f"{-9.90:.2f}", "TARIFA PACOTE SERVICOS"))
            continue
        if caso == 7:
            # pendente no extrato: rendimento (credito so no banco)
            ext.append((dt, f"{12.34:.2f}", "RENDIMENTO APLIC AUTOMATICA"))
            continue
        if caso == 11:
            # pendente no razao: cheque em transito (so na razao)
            raz.append((dbr, f"-{base_val:.2f}".replace(".", ","), contra, _cnpj(seq), "CHEQUE EMITIDO", "", doc))
            continue
        if caso == 15:
            # conciliado com diferenca de centavos (extrato 0,03 a mais)
            ext.append((dt, f"{val - 0.03:.2f}" if val < 0 else f"{val + 0.03:.2f}", contra))
            raz.append((dbr, f"{val:.2f}".replace(".", ","), contra, _cnpj(seq), "PGTO", "", doc))
            continue
        if caso == 18 and not saida:
            # credito sem razao -> orientacao contas-a-receber
            ext.append((dt, f"{base_val:.2f}", "PIX RECEBIDO " + contra))
            continue
        # caso normal: casa 1:1
        ext.append((dt, f"{val:.2f}", contra))
        raz.append((dbr, f"{val:.2f}".replace(".", ","), contra, _cnpj(seq), "PGTO", "", doc))

    # injeta 1 LOTE SISPAG: 1 debito grande no banco = soma de 4 titulos de fornecedores
    # diferentes, ligados pela coluna Lote (remessa). So no Itau (idx 0) p/ exercitar o caminho.
    if idx == 0:
        lote_id = "SISPAG-90001"
        titulos = [1500.00, 823.70, 3200.00, 463.10]
        total = round(sum(titulos), 2)
        dl = (BASE + timedelta(days=5)).strftime("%Y%m%d")
        dlbr = (BASE + timedelta(days=5)).strftime("%d/%m/%Y")
        ext.append((dl, f"{-total:.2f}", "SISPAG PAGTO FORNECEDORES LOTE"))
        for k, t in enumerate(titulos):
            raz.append((dlbr, f"-{t:.2f}".replace(".", ","), f"FORNEC LOTE {k+1}", _cnpj(9000 + k), "PGTO LOTE", lote_id, f"L{k}"))

    return ext, raz


# ---------------- writers de formato ----------------
def escreve_ofx(path, bankid, acct, ext):
    corpo = "\n".join(
        f"<STMTTRN><DTPOSTED>{dt}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
        for i, (dt, v, m) in enumerate(ext, 1))
    saldo = sum(float(v) for _, v, _ in ext)
    txt = ("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
           f"<BANKACCTFROM><BANKID>{bankid}<ACCTID>{acct}<ACCTTYPE>CHECKING</BANKACCTFROM>"
           f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
           f"<LEDGERBAL><BALAMT>{saldo:.2f}<DTASOF>20260531</LEDGERBAL></STMTRS></STMTTRNRS>"
           "</BANKMSGSRSV1></OFX>\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)


def escreve_csv_extrato(path, ext):
    # extrato em CSV com Data;Historico;Valor (sinal) — exercita o dispatcher tabular
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("Data;Historico;Valor\n")
        for dt, v, m in ext:
            d = f"{dt[6:8]}/{dt[4:6]}/{dt[0:4]}"
            f.write(f"{d};{m};{v.replace('.', ',')}\n")


def escreve_xlsx_extrato(path, ext):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Data", "Historico", "Valor"])
    for dt, v, m in ext:
        d = f"{dt[6:8]}/{dt[4:6]}/{dt[0:4]}"
        ws.append([d, m, float(v)])
    wb.save(path)


def escreve_razao(path, raz):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(HDR + "\n")
        for (data, valor, contra, cnpj, hist, lote, doc) in raz:
            f.write(f"{data};{valor};{doc};;{contra};{cnpj};{hist};{lote}\n")


def main():
    destino = sys.argv[1] if len(sys.argv) > 1 else "_exemplo-pesado"
    txns = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    os.makedirs(destino, exist_ok=True)
    tot_ext = tot_raz = 0
    for idx, (banco, bankid, fmt, _zero) in enumerate(BANCOS):
        sub = os.path.join(destino, banco)
        os.makedirs(sub, exist_ok=True)
        ext, raz = gera_conta(idx, banco, txns)
        acct = f"{10000 + idx}"
        if fmt == "ofx":
            escreve_ofx(os.path.join(sub, "extrato.ofx"), bankid, acct, ext)
        elif fmt == "csv":
            escreve_csv_extrato(os.path.join(sub, "extrato.csv"), ext)
        elif fmt == "xlsx":
            escreve_xlsx_extrato(os.path.join(sub, "extrato.xlsx"), ext)
        escreve_razao(os.path.join(sub, "razao.csv"), raz)
        tot_ext += len(ext); tot_raz += len(raz)
        print(f"  {banco:<14} fmt={fmt:<4} extrato={len(ext):>4}  razao={len(raz):>4}")
    print(f"\nOK exemplo pesado em '{destino}': {len(BANCOS)} contas, "
          f"{tot_ext} linhas de extrato, {tot_raz} linhas de razao.")
    print(f"Rode:  python scripts/conciliar.py pasta --pasta {destino} --out _resultado-pesado")


if __name__ == "__main__":
    main()
