---
name: conciliacao-bancaria
description: >-
  Concilia o extrato bancário (OFX, CSV, XLSX, XLS ou PDF) contra o razão contábil ou do
  ERP, classifica cada lançamento, lista as pendências de trânsito e fecha a amarração de
  saldo. Rodando no terminal ou no Claude Code em sessão local, o motor Python
  processa o extrato localmente. No Claude Code em sessão local, a skill foi feita para o
  Claude ler só o resumo agregado (contagens, totais, saldos), não a linha de transação.
  Use quando a pessoa quiser conciliar banco x razão no Brasil.
---

# Conciliação Bancária, Finance AI Lab

Ferramenta de tesouraria: concilia o **extrato bancário x razão contábil** de forma
**determinística**. Você (Claude) **orquestra**; o **motor Python** faz o cruzamento e o
cálculo. Você lê apenas o `resumo.json`, nunca o dado bruto.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Contrato de privacidade, por plataforma

O que vale depende de onde a conversa roda. Diga isso à pessoa, sem prometer o que a
plataforma não entrega.

- **No terminal ou no Claude Code em sessão local:** o motor lê o extrato e o razão no disco
  e você lê só o resumo agregado; não abra o arquivo bruto. O motor processa tudo
  localmente e grava o relatório no disco dela. Para você só sobe o `resumo.json`
  **agregado** (contagens, totais, **saldos**, amarração), **nenhuma linha de transação**.
  **Nunca** abra nem leia o `.ofx`, o `.csv` do razão ou o `conciliacao.xlsx`. Se a pessoa
  pedir uma análise linha a linha, oriente-a a abrir o Excel local. O pedido dela, esse
  resumo e qualquer arquivo que você abrir vão para a Anthropic.
- **No Cowork ou numa conversa comum do Claude (web ou app):** o arquivo está na nuvem da
  Anthropic: avise a pessoa antes de ela anexar ou de abrir a tarefa, em vez de dizer que
  nada sobe, e sugira o terminal, o Claude Code em sessão local ou anonimizar o arquivo.

### A única saída de rede do motor: `posicao --sheet`

O motor não faz nenhuma chamada de rede, com **uma** exceção: o modo `posicao` com a opção
`--sheet`. É **opt-in** (só roda se a pessoa passar `--sheet`, nunca é o caminho padrão) e
envia para uma **planilha Google da própria pessoa** apenas **saldos agregados**: por conta,
banco, tipo, saldo final, data do saldo e se a conta entra no caixa, mais o total em caixa
(e o saldo mínimo e o status, se informados). O número da conta vai **mascarado** (só os
dois últimos dígitos) e o nome do arquivo não sobe. Nenhuma linha de extrato vai. Exige a
biblioteca `gspread` e uma conta de serviço Google configurada pela pessoa. Sem `--sheet`,
o `posicao` roda 100% offline. Não sugira `--sheet` por conta própria: explique o que ele
envia e deixe a pessoa decidir.

## Pré-requisitos

- **Python 3.10 ou mais**, no computador da pessoa, com acesso a Bash/Python (Claude Code
  em sessão local ou terminal).
- **Instalar as dependências uma vez** (no terminal da pessoa, a partir desta pasta):
  ```
  pip install -r requirements.txt
  ```
  Isso habilita ler **todos os formatos** de extrato (CSV, XLSX, XLS, PDF). Precisa de
  internet **só na instalação**; depois roda **offline** (fora o `--sheet`, acima). Se
  pular, o motor ainda roda no que conseguir e **degrada com mensagem clara** (nunca
  quebra).
- **OCR (opcional):** para extrato em **imagem ou PDF escaneado**, instale o **Tesseract**
  (Windows: `winget install UB-Mannheim.TesseractOCR`; macOS: `brew install tesseract`;
  Linux: `apt install tesseract-ocr`) e rode com `--ocr`. Sem ele, esses arquivos viram
  `PRECISA_OCR`.
- Os arquivos do período: **extrato** (qualquer formato; OFX de preferência) + **razão** no
  modelo.

## Entradas

**Lado banco: qualquer formato.** O ideal continua sendo **OFX** (aberto, exato). Mas a
skill **engole o que o time mandar**: OFX, CSV, XLSX, XLS (inclusive HTML disfarçado de
`.xls`), e **PDF com texto**, tudo lido pelo motor (`ingest_extrato`). PDF escaneado e
imagem (foto/print) passam pelo OCR local, que é opt-in (`--ocr`) e exige o Tesseract; sem
isso viram status `PRECISA_OCR` (oriente a exportar OFX/CSV). **Ordem de preferência** quando a mesma conta
vem em vários formatos: OFX > CSV/XLSX > PDF-texto. **Você pode entregar uma PASTA inteira**
de extratos do mês (veja o comando `pasta` no Fluxo).

**Lado contábil: razão no formato fixo (contrato).** Não tentamos adivinhar
o layout de cada ERP (cada um exporta de um jeito, fonte de erro). A pessoa arruma
o razão **uma vez** no modelo **`modelo-razao.csv`**:

| Coluna | Obrig.? | Conteúdo | Regra |
|---|---|---|---|
| `Data` | ✅ | data do lançamento | `DD/MM/AAAA` |
| `Valor` | ✅ | valor **com sinal** | `+entrada / −saída`; vírgula decimal (`1.500,00` / `-850,00`) |
| `Documento` | recomendado | nº do lançamento/cheque/doc | chave forte quando alinha com o banco |
| `Identificador` | opcional | **E2E do PIX / NSU / Nosso Número** | chave forte quando o ERP guarda |
| `Contraparte` | opcional | nome do fornecedor/cliente | **desempata** mesmo-valor por nome |
| `CNPJ_CPF` | opcional | CNPJ/CPF da contraparte | **desempata/confirma** (o banco traz no PIX) |
| `Historico` | opcional | descrição | livre |
| `Lote` | opcional | nº da **remessa de pagamento** (SISPAG/lote) | liga títulos de fornecedores **diferentes** pagos numa remessa única → concilia o débito em lote (N:1) |

Separador `;`, UTF-8. **Só `Data` e `Valor` são obrigatórias**; os identificadores
são opcionais, mas quanto mais a pessoa incluir, melhor o matching desambigua casos de
**mesmo valor no mesmo dia**.

> **Pagamentos em lote (Itaú SISPAG e equivalentes):** quando o banco lança **um débito
> = soma de vários títulos** (de contrapartes diferentes), o motor só fecha o par se a
> coluna `Lote` trouxer o **nº da remessa** igual em cada título do lote. Sem isso, o débito
> fica pendente e é rotulado `LOTE_SISPAG` ("confira contra a remessa"). Títulos da **mesma
> contraparte** no mesmo dia já agrupam sem `Lote`. O nº da remessa costuma estar no relatório
> de **pagamentos/remessas** do ERP (não no de contas-a-pagar). Se o ERP exporta com outros nomes de coluna, oriente a
reordenar/renomear para o modelo (a maioria dos ERPs deixa escolher colunas no export)
ou, pontualmente, passe `--col-data/--col-valor/--col-doc/--col-contraparte` etc.
**Não invente um parser por ERP.** O contrato é o modelo.

> **Como o matching usa isso:** `Valor`+`Data` (com janela D+n) **criam** o par; quando
> há vários candidatos de mesmo valor, o desempate segue a ordem `Documento` →
> `Identificador` → `CNPJ_CPF` → overlap de nome da `Contraparte`. O banco normalmente
> traz a contraparte no histórico, e o PIX traz CNPJ/CPF, e o motor extrai isso do extrato
> automaticamente. Identificadores **afinam a precisão**; nunca substituem valor+data.

A pessoa também informa o **saldo final do razão** (saldo contábil da conta no
fim do período): é o que fecha a amarração.

## Fluxo

Trabalhe a partir da pasta onde estão os arquivos. Os scripts estão em `scripts/`.

### Fase 0: Conciliar a pasta do mês (a jornada principal)
```
python scripts/conciliar.py pasta --pasta PASTA_DO_MES --out resultado-pasta [--ocr]
```
Estrutura: **1 subpasta por conta**, cada uma com o **extrato** (qualquer formato: OFX/CSV/
XLSX/XLS/PDF; OFX de preferência) **+ um `razao.csv`** no modelo (1 lançamento por linha).
A skill, **por conta**: escolhe o melhor extrato (não conta a mesma conta 2x), e **se houver
`razao.csv` na pasta, concilia** (taxa, pendências, lote); senão, só reporta o que leu.
- **Nomeie a subpasta por um apelido da conta** (ex.: `itau-principal`), **sem número de conta**: o nome da
  subpasta aparece no `resumo.json` e na saída que você lê.
- `--ocr` liga o OCR local (Tesseract) p/ extrato em imagem/PDF escaneado (opt-in).
- **Crédito do banco sem correspondente no razão** → a skill orienta **lançar um contas-a-receber**
  (a ferramenta cobre **contas a pagar**; o lado de recebíveis é responsabilidade de quem opera).
- Estados que **precisam de ação**: `PRECISA_OCR` (rode com `--ocr`), `MAPEAR_COLUNAS` (layout não
  reconhecido → exporte OFX/CSV), `CORROMPIDO`, `TIMEOUT` (PDF gigante → divida o período).
- Só o agregado (`resumo.json`) sobe para você, **nenhuma linha de transação**.

Para a amarração de saldo de uma conta específica, use a `conciliar` (abaixo) com `--saldo-razao`.

### Fase 1: Validar (sempre primeiro)
```
python scripts/conciliar.py validar --extrato EXTRATO.ofx --razao RAZAO.csv
```
Mostra metadados agregados (banco/conta, nº de transações, período, colunas
detectadas da razão). **Se reprovar** (coluna obrigatória ausente, arquivo
ilegível, períodos que não se sobrepõem), **pare** e ajude a corrigir, não
cruze nada. Se a razão usar nomes de coluna fora do padrão, passe
`--col-data`, `--col-valor`, `--col-doc`, `--col-desc`.

### Fase 2 + 3: Conciliar e relatar
```
python scripts/conciliar.py conciliar --extrato EXTRATO.ofx --razao RAZAO.csv \
       --saldo-razao 12345,67 --out resultado
```
Gera em `resultado/`:
- `resumo.json`: **o único arquivo que você lê.**
- `conciliacao.xlsx` (ou `.csv`): relatório analítico **local**, para a pessoa.

Opções: `--janela N` (dias de liquidação D+n aceitos como conciliado, padrão 3);
`--tolerancia 0,10` (diferença de centavos vira "conciliado com diferença").

### Modo posição de caixa (opcional, só OFX)
```
python scripts/conciliar.py posicao --pasta PASTA_DE_OFX [--saldo-minimo 50000] [--out resultado-posicao]
```
Varre uma pasta de OFX, consolida o saldo das contas e devolve o total em caixa (e o status
contra o saldo mínimo, se informado). Grava `posicao.csv` (local, com o número da conta
cheio) e `resumo.json` (agregado, com a conta mascarada). A opção `--sheet` é a única saída
de rede do motor e está descrita no contrato de privacidade acima.

## Como ler o `resumo.json` e responder

Classes de status:
- **CONCILIADO**: bateu (doc+valor+data, ou valor+data, ou dentro da janela D+n).
- **CONCILIADO_COM_DIFERENCA**: valor dentro da tolerância (centavos a investigar).
- **CONCILIADO_LOTE**: um débito/crédito do banco = **soma de vários títulos** do mesmo
  dia (N:1), agrupados pela **mesma remessa** (`Lote`) ou **mesma contraparte**. Os
  títulos que o compõem aparecem em `componentes`.
- **PENDENTE_EXTRATO**: está no banco, falta no razão (tarifa, IOF, juros, débito
  automático → **a lançar no razão**).
- **PENDENTE_RAZAO**: está no razão, ainda não no banco (cheque emitido não
  compensado, depósito em trânsito → **aguardando o banco**).

**`pendencias_por_categoria`**: a "cauda" que não fecha, já **classificada** com a
ação sugerida. Use isto para explicar cada pendência (é o que a analista quer):

| Categoria | O que é | Ação |
|---|---|---|
| `TARIFA_IOF` | tarifa, IOF, juros, cesta (só no extrato) | lançar no razão (despesa) |
| `RENDIMENTO` | rendimento/aplicação (só no extrato) | lançar no razão (receita) |
| `PIX_ORFAO` | Pix recebido sem identificação | conferir e identificar o pagador |
| `LIQUIDO_ADQUIRENTE` | crédito de cartão líquido de taxa | conciliar pelo líquido + linha de taxa |
| `LOTE_SISPAG` | débito de **remessa de pagamento** (SISPAG / pag. fornecedores) | conferir contra a remessa; informe a coluna `Lote` no razão p/ conciliar |
| `A_LANCAR` | outros lançamentos do extrato | lançar no razão |
| `CHEQUE_NAO_COMPENSADO` | cheque emitido, ainda não no banco | aguardar compensação |
| `DEPOSITO_TRANSITO` | depósito/TED no razão, não no banco | aguardar crédito |
| `EM_TRANSITO` | outros do razão aguardando o banco | aguardar / conferir |

> A classificação é heurística (palavras-chave + sinal). Trate como **sugestão**:
> diga "provavelmente tarifa", não afirme como certeza. Líquido de adquirente é
> oportunista (depende de a descrição citar a adquirente).

**`controle_lote`** (só aparece quando há débito de lote/SISPAG pendente): figura de
**controle agregado** da cauda de lote que não pôde ser pareada por falta do nº da remessa
no razão: `total_debitos_lote` (banco) × `total_titulos_pendentes` (saídas do razão) +
`diferenca`. **Não é conciliação linha-a-linha**: é o "bate no agregado?". Se `diferenca`
≈ 0, os lotes fecham no total (o detalhe está na remessa); se for grande, há títulos de
outro período/conta ou falta a remessa. Diga à pessoa o total e a diferença, e oriente a
exportar o relatório de **remessas/pagamentos** (com o nº SISPAG) p/ a coluna `Lote` parear de fato.

A **amarração** é o checksum: `saldo_razão + pendências_extrato − pendências_razão
+ diferenças = saldo_extrato`. Se `integridade_ok` for `false` (resíduo ≠ 0),
**avise que o relatório não fecha** e que há erro de integridade a investigar antes
de confiar nos números, e não maquie.

Responda em PT-BR, direto: taxa de conciliação, o que ficou pendente de cada lado
(e a ação típica), e se a amarração fechou. Aponte o Excel local para o detalhe.

## Limites honestos (dizer, não esconder)

- Conciliação **bancária** (extrato baixado). **CNAB** (remessa/retorno) fica fora:
  já é auto-conciliado pelo ERP, e não é onde a dor está.
- A razão precisa de valor **com sinal** na convenção +entrada/−saída. Outras
  convenções (débito/crédito em colunas separadas) ainda não são suportadas.
- PDF de extrato é frágil. Prefira OFX.
