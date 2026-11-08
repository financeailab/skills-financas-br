# Conciliação Bancária

Concilia o **extrato do banco contra o razão do ERP**, com o motor rodando na sua máquina (no terminal ou no Claude Code em sessão local). Você
entrega o extrato (OFX, CSV, XLSX, XLS ou PDF) e o razão no formato do `modelo-razao.csv`; o
motor Python cruza os dois, classifica cada lançamento (conciliado, com diferença, em lote,
pendente de cada lado), explica a cauda que não fecha e confere a **amarração de saldo**. É
para quem fecha o mês na tesouraria e hoje faz isso no Excel, linha por linha.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `conciliacao-bancaria`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install conciliacao-bancaria@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `conciliacao-bancaria.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. **Aqui o arquivo anexado e os scripts rodam na nuvem da Anthropic**, não no seu computador. |
| **Terminal** | `python scripts/conciliar.py pasta --pasta PASTA_DO_MES --out resultado-pasta` (de dentro de `skills/conciliacao-bancaria/`). |

## Requisitos

- **Python 3.10 ou mais**.
- **Dependências opcionais**, instaladas uma vez com `pip install -r requirements.txt` (dentro
  de `skills/conciliacao-bancaria/`). Sem elas o motor roda no que conseguir e **degrada com
  mensagem clara, sem quebrar**:

  | Dependência | Para quê | Sem ela |
  |---|---|---|
  | `openpyxl` | extrato e razão em `.xlsx`; relatório `conciliacao.xlsx` | o relatório sai em CSV; `.xlsx` não é lido |
  | `xlrd` | `.xls` antigo (por exemplo, o da Caixa) | `.xls` não é lido |
  | `pdfplumber` e `pypdf` | extrato em PDF com texto (o `pypdf` é o plano B de extração) | PDF não é lido |
  | `pytesseract` e `pypdfium2`, mais o **Tesseract** instalado à parte | OCR de imagem e de PDF escaneado, só com `--ocr` | o arquivo vira status `PRECISA_OCR` |

  O Tesseract não vem do `pip`: no Windows, `winget install UB-Mannheim.TesseractOCR`; no
  macOS, `brew install tesseract`; no Linux, `apt install tesseract-ocr`. OFX e CSV não
  precisam de nenhuma dependência além do Python.

Para testar sem dado seu, use os arquivos fictícios em
[`skills/conciliacao-bancaria/exemplo/`](skills/conciliacao-bancaria/exemplo/) (extrato OFX,
razão e o resultado esperado).

## Como usar

O razão entra no formato fixo do [`modelo-razao.csv`](skills/conciliacao-bancaria/modelo-razao.csv)
(`;` como separador, valor com sinal, `+` entrada e `-` saída). Só `Data` e `Valor` são
obrigatórias; `Documento`, `Identificador`, `Contraparte`, `CNPJ_CPF`, `Historico` e `Lote`
afinam o cruzamento.

```
# a pasta do mês: uma subpasta por conta, com o extrato e um razao.csv
python scripts/conciliar.py pasta --pasta PASTA_DO_MES --out resultado-pasta [--ocr]

# uma conta, com a amarração de saldo
python scripts/conciliar.py validar   --extrato EXTRATO.ofx --razao RAZAO.csv
python scripts/conciliar.py conciliar --extrato EXTRATO.ofx --razao RAZAO.csv \
       --saldo-razao 12345,67 --out resultado
```

O Claude lê só o `resumo.json` agregado; o detalhe linha a linha fica no `conciliacao.xlsx`
(ou `.csv`) local, para você abrir no Excel.

## Privacidade

- **Terminal**: o motor lê o extrato e o razão no seu computador e nada sai dele.
- **Claude Code, em sessão local**: o motor também lê o extrato e o razão no disco e o Claude lê
  só o resumo agregado que ele imprime (contagens, totais, saldos, amarração); o seu pedido, esse
  resumo e qualquer arquivo que você mandar o Claude abrir vão para a Anthropic.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra) e **claude.ai** (web ou app): o trabalho
  roda na nuvem da Anthropic e o arquivo sobe para lá. Nesse caso, anonimize o arquivo ou rode no
  terminal ou no Claude Code em sessão local.

### A única saída de rede: `posicao --sheet`

O motor não faz chamada de rede, com uma exceção: o modo `posicao` (consolida o saldo das
contas de uma pasta de OFX) com a opção `--sheet`. É **opt-in**, nunca o caminho padrão, e
envia para uma **planilha Google da sua própria conta** só os **saldos agregados**: por conta,
o banco, o tipo, o saldo final, a data do saldo e se a conta entra no caixa, mais o total em
caixa (e o saldo mínimo e o status, se você informar). O número da conta vai **mascarado**
(só os dois últimos dígitos) e o nome do arquivo não sobe. Nenhuma linha de extrato vai. Exige
a biblioteca `gspread` (`pip install gspread`, que não está no `requirements.txt`) e uma conta
de serviço Google que você configura. Sem `--sheet`, o `posicao` roda sem rede.

```
python scripts/conciliar.py posicao --pasta PASTA_DE_OFX --sheet ID_DA_PLANILHA
```

## Limites

- Concilia **extrato baixado** (conciliação bancária). **CNAB** (remessa e retorno) fica fora
  de propósito: o ERP já concilia esse fluxo.
- O razão precisa estar no formato fixo do `modelo-razao.csv`, com valor **assinado** (`+`
  entrada, `-` saída). Convenção de débito e crédito em colunas separadas ainda não é
  suportada. O motor não adivinha o layout de cada ERP: você arruma o razão uma vez no modelo.
- **PDF de extrato é frágil.** Prefira OFX. Imagem e PDF escaneado só com OCR, que é opt-in e
  exige o Tesseract instalado à parte; sem ele o arquivo vira `PRECISA_OCR` em vez de quebrar.
- **Pagamento em lote** (por exemplo, remessa SISPAG do Itaú): quando o banco lança um débito
  que é a soma de títulos de fornecedores diferentes, o motor só fecha o par se a coluna `Lote`
  do razão trouxer o número da remessa. Sem ele, o débito fica pendente como `LOTE_SISPAG`, com
  um total de controle agregado, e **não** é pareado linha a linha. O número da remessa costuma
  estar no relatório de pagamentos do ERP, não no de contas a pagar.
- **A classificação das pendências é heurística** (palavras-chave e sinal): trate como
  sugestão, não como certeza. Se a amarração de saldo não fechar, o relatório avisa que há
  erro de integridade a investigar; não confie nos números antes disso.
- **Crédito do banco sem correspondente no razão** fica pendente: a ferramenta cobre contas a
  pagar, e o lado de recebíveis é responsabilidade de quem opera.
- Alguns bancos (por exemplo Bradesco, Santander e Banco do Brasil) exportam o OFX com saldo
  zerado; nesse caso informe o saldo do extrato com `--saldo-extrato`, senão a amarração
  avisa que o saldo não foi informado.
- Cada ERP e cada banco exporta de um jeito: valide o resultado antes de apoiar o fechamento
  nele.

## Testes

Os testes são scripts, não pytest. Da raiz do repositório:

```
cd plugins/conciliacao-bancaria
for t in tests/test_*.py; do python "$t" || exit 1; done
```

## Licença

[Apache-2.0](../../LICENSE).
