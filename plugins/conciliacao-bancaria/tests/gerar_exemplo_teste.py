# -*- coding: utf-8 -*-
"""Gera um KIT DE TESTE curado (dados ficticios realistas BR) p/ o operador testar a
skill no Claude Cowork. Diferente do `gerar_exemplo_pesado.py` (stress em volume), aqui
os dados sao POUCOS e LEGIVEIS, cada conta exercita casos claros, p/ a pessoa VER o
produto funcionando: match 1:1, tarifa/IOF, rendimento, Pix sem razao (contas-a-receber),
cheque em transito, conciliado-com-diferenca e lote SISPAG (N:1). Tres formatos: OFX/CSV/XLSX.

Uso:  python tests/gerar_exemplo_teste.py [pasta_destino]
       (default: ~/Downloads/Conciliadora-Exemplo-Teste)
"""
import os
import sys

HDR = "Data;Valor;Documento;Identificador;Contraparte;CNPJ_CPF;Historico;Lote"


def _cnpj(seed):
    n = f"{(seed * 137 + 7) % 100000000:08d}"
    return f"{n[0:2]}.{n[2:5]}.{n[5:8]}/0001-{(seed*7)%90+10}"


def _dt(ddmm):  # "04/05" -> "20260504"
    d, m = ddmm.split("/")
    return f"2026{m}{d}"


# ---------------- dados curados por conta ----------------
# ext: (data ddmm, valor com ponto e sinal, memo) | raz: (data, valor com virgula e sinal, contraparte, hist, lote)
CONTAS = {
    # Itau (OFX): 4 matches + lote SISPAG (3 titulos = 1 debito) + tarifa + rendimento + Pix(AR)
    "Itau": {
        "fmt": "ofx", "bankid": "0341", "acct": "12345-6",
        "ext": [
            ("04/05", "-1500.00", "PAGTO FORNEC PAPELARIA ALFA"),
            ("06/05", "-3200.00", "PAGTO TRANSPORTADORA BETA"),
            ("09/05", "-875.40", "PAGTO MANUTENCAO GAMA"),
            ("12/05", "8500.00", "RECEBIMENTO CLIENTE DELTA"),
            ("15/05", "-29.90", "TARIFA PACOTE SERVICOS"),          # pendente extrato (tarifa)
            ("20/05", "127.35", "RENDIMENTO APLIC AUTOMATICA"),     # pendente extrato (rendimento)
            ("22/05", "2300.00", "PIX RECEBIDO REF NF 4471"),       # credito sem razao -> contas-a-receber
            ("25/05", "-5300.00", "SISPAG PAGTO FORNECEDORES"),     # lote N:1 = 2000+1800+1500
        ],
        "raz": [
            ("04/05", "-1500,00", "PAPELARIA ALFA", "Compra material", ""),
            ("06/05", "-3200,00", "TRANSPORTADORA BETA", "Frete", ""),
            ("09/05", "-875,40", "MANUTENCAO GAMA", "Servico", ""),
            ("12/05", "8500,00", "CLIENTE DELTA", "Venda NF 312", ""),
            ("25/05", "-2000,00", "FORNEC EPSILON", "Lote pagto", "SISPAG-5521"),
            ("25/05", "-1800,00", "FORNEC ZETA", "Lote pagto", "SISPAG-5521"),
            ("25/05", "-1500,00", "FORNEC ETA", "Lote pagto", "SISPAG-5521"),
        ],
    },
    # Bradesco (CSV): 3 matches + IOF (pendente extrato) + conciliado-com-diferenca + cheque (pendente razao)
    "Bradesco": {
        "fmt": "csv", "bankid": "0237", "acct": "67890-1",
        "ext": [
            ("05/05", "-640.00", "ALUGUEL IMOVEL"),
            ("11/05", "-1250.00", "PAGTO FORNEC THETA"),
            ("14/05", "3100.00", "RECEBIMENTO CLIENTE IOTA"),
            ("18/05", "-89.90", "IOF OPERACAO CREDITO"),            # pendente extrato (IOF)
            ("21/05", "-450.04", "PAGTO FORNEC KAPPA"),             # conciliado-com-diferenca (razao -450,00)
        ],
        "raz": [
            ("05/05", "-640,00", "ALUGUEL IMOVEL", "Aluguel maio", ""),
            ("11/05", "-1250,00", "FORNEC THETA", "Insumos", ""),
            ("14/05", "3100,00", "CLIENTE IOTA", "Venda NF 318", ""),
            ("21/05", "-450,00", "FORNEC KAPPA", "Servico", ""),
            ("28/05", "-2200,00", "FORNEC LAMBDA", "Cheque 000123 em transito", ""),  # pendente razao (nao caiu no banco)
        ],
    },
    # Santander (XLSX): 3 matches + tarifa (pendente extrato) + Pix(AR)
    "Santander": {
        "fmt": "xlsx", "bankid": "0033", "acct": "55555-0",
        "ext": [
            ("07/05", "-980.00", "PAGTO FORNEC MU"),
            ("13/05", "-1500.00", "PAGTO FORNEC NU"),
            ("19/05", "5600.00", "RECEBIMENTO CLIENTE XI"),
            ("23/05", "-45.00", "TARIFA TED"),                      # pendente extrato (tarifa)
            ("27/05", "1750.00", "PIX RECEBIDO"),                   # credito sem razao -> contas-a-receber
        ],
        "raz": [
            ("07/05", "-980,00", "FORNEC MU", "Material", ""),
            ("13/05", "-1500,00", "FORNEC NU", "Servico", ""),
            ("19/05", "5600,00", "CLIENTE XI", "Venda NF 401", ""),
        ],
    },
}

LEIA_ME = """KIT DE TESTE — Conciliacao Bancaria (Finance AI Lab)
=====================================================
Dados FICTICIOS (nenhuma informacao real). Use para testar a skill no Claude Cowork.

COMO TESTAR (jornada principal "pasta do mes"):
  1. No Cowork, crie um projeto: Projetos > Novo projeto > Usar uma pasta existente
     e aponte para ESTA pasta (Conciliadora-Exemplo-Teste).
  2. Peca ao Claude:  "Concilia a pasta do mes."
  3. Veja o resultado por conta (taxa, pendencias com acao) + o relatorio conciliacao.xlsx
     que a skill grava em cada subpasta. Nenhum dado sai da sua maquina.

O QUE CADA CONTA EXERCITA (de proposito):
  Itau (OFX)      : 4 lancamentos casam 1:1; 1 LOTE SISPAG (1 debito de R$ 5.300 = 3 titulos
                    de fornecedores diferentes ligados pela coluna Lote=SISPAG-5521);
                    1 tarifa e 1 rendimento que faltam no razao; 1 Pix recebido sem razao
                    (a skill orienta lancar um CONTAS A RECEBER).
  Bradesco (CSV)  : 3 casam; 1 IOF que falta no razao; 1 pagamento conciliado-COM-DIFERENCA
                    (3 centavos dentro da tolerancia); 1 cheque em transito que esta no razao
                    mas ainda nao caiu no banco (pendente no razao).
  Santander (XLSX): 3 casam; 1 tarifa que falta no razao; 1 Pix recebido sem razao (contas-a-receber).

TESTAR TAMBEM (opcional):
  - Amarracao de uma conta: peca "valida e concilia o extrato do Itau contra a razao,
    com saldo do razao R$ <valor>" (a skill fecha a amarracao de saldo).
  - Posicao de caixa: peca "me da a posicao de caixa dessa pasta" (soma os saldos dos OFX).

Cada subpasta tem: o extrato (OFX/CSV/XLSX) + um razao.csv no modelo (1 lancamento por linha,
valor com sinal: + entrada / - saida).
"""


def escreve_ofx(path, bankid, acct, ext):
    corpo = "\n".join(
        f"<STMTTRN><DTPOSTED>{_dt(d)}<TRNAMT>{v}<FITID>F{i}<MEMO>{m}</STMTTRN>"
        for i, (d, v, m) in enumerate(ext, 1))
    saldo = sum(float(v) for _, v, _ in ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write("OFXHEADER:100\nDATA:OFXSGML\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL"
                f"<BANKACCTFROM><BANKID>{bankid}<ACCTID>{acct}<ACCTTYPE>CHECKING</BANKACCTFROM>"
                f"<BANKTRANLIST>\n{corpo}\n</BANKTRANLIST>"
                f"<LEDGERBAL><BALAMT>{saldo:.2f}<DTASOF>20260531</LEDGERBAL></STMTRS></STMTTRNRS>"
                "</BANKMSGSRSV1></OFX>\n")


def escreve_csv_extrato(path, ext):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("Data;Historico;Valor\n")
        for d, v, m in ext:
            dd, mm = d.split("/")
            f.write(f"{dd}/{mm}/2026;{m};{v.replace('.', ',')}\n")


def escreve_xlsx_extrato(path, ext):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Data", "Historico", "Valor"])
    for d, v, m in ext:
        dd, mm = d.split("/")
        ws.append([f"{dd}/{mm}/2026", m, float(v)])
    wb.save(path)


def escreve_razao(path, raz):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(HDR + "\n")
        for k, (data, valor, contra, hist, lote) in enumerate(raz):
            dd, mm = data.split("/")
            f.write(f"{dd}/{mm}/2026;{valor};DOC{k+1:03d};;{contra};{_cnpj(k+1)};{hist};{lote}\n")


def main():
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.expanduser("~"), "Downloads", "Conciliadora-Exemplo-Teste")
    os.makedirs(destino, exist_ok=True)
    # LEIA-ME fica FORA da pasta (irmao), senao o 'pasta' trata o arquivo solto da raiz
    # como uma "conta" fantasma. A pasta do kit contem so as subpastas de conta.
    leia_path = os.path.join(os.path.dirname(os.path.abspath(destino)),
                             os.path.basename(destino.rstrip("/\\")) + " - LEIA-ME.txt")
    with open(leia_path, "w", encoding="utf-8") as f:
        f.write(LEIA_ME)
    for conta, cfg in CONTAS.items():
        sub = os.path.join(destino, conta)
        os.makedirs(sub, exist_ok=True)
        if cfg["fmt"] == "ofx":
            escreve_ofx(os.path.join(sub, "extrato.ofx"), cfg["bankid"], cfg["acct"], cfg["ext"])
        elif cfg["fmt"] == "csv":
            escreve_csv_extrato(os.path.join(sub, "extrato.csv"), cfg["ext"])
        elif cfg["fmt"] == "xlsx":
            escreve_xlsx_extrato(os.path.join(sub, "extrato.xlsx"), cfg["ext"])
        escreve_razao(os.path.join(sub, "razao.csv"), cfg["raz"])
        print(f"  {conta:<11} {cfg['fmt']:<4} extrato={len(cfg['ext'])}  razao={len(cfg['raz'])}")
    print(f"\nOK kit de teste em: {destino}")
    print("Aponte um projeto Cowork para essa pasta e peca: \"Concilia a pasta do mes.\"")


if __name__ == "__main__":
    main()
