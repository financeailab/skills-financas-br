---
name: leitor-de-fatura-de-cartao
description: >-
  Lê o PDF da fatura de cartão corporativo e devolve os lançamentos individuais
  estruturados (data, estabelecimento, valor, parcela, portador, moeda) em CSV e XLSX,
  com prova de completude: a soma dos lançamentos mais os encargos tem que fechar com o
  total impresso, senão o motor avisa em vez de fingir que leu tudo. Use quando a pessoa
  precisar explodir a fatura do cartão corporativo em lançamentos por portador, para
  prestação de contas ou fechamento.
---

# Leitor de Fatura de Cartão, Finance AI Lab

Você (Claude) **orquestra**; o **motor Python** em `scripts/` lê o PDF, extrai os lançamentos e faz a prova de
completude, sempre do mesmo jeito para a mesma entrada.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Contrato de privacidade, por plataforma

O que vale depende de onde a conversa roda. Diga isso à pessoa, sem prometer o que a plataforma não entrega.

- **No terminal ou no Claude Code em sessão local:** o motor lê o PDF no disco. Peça o caminho da fatura ou da
  pasta; não peça para ela colar ou anexar a fatura e não abra o PDF. Você lê só o que o motor imprime: emissor
  reconhecido, vencimento, quantos portadores, lançamentos e encargos, o total calculado, o total impresso e o
  veredicto; no lote, as contagens por veredicto e o nome de cada arquivo que não fechou. O pedido dela, esse
  resumo e qualquer arquivo que você abrir vão para a Anthropic.
- **Os arquivos de saída** (o CSV e o XLSX) trazem portador, estabelecimento, valor e parcela de cada
  lançamento. Você não os abre. Para ver lançamento a lançamento, oriente a pessoa a abrir o XLSX. Se ela pedir
  que você confira, lembre que o que você abrir vai para a Anthropic e deixe a decisão com ela.
- **No Cowork ou numa conversa comum do Claude (web ou app):** o arquivo está na nuvem da Anthropic. Avise a
  pessoa antes de ela anexar, em vez de dizer que nada sobe, e sugira o terminal ou o Claude Code em sessão local.
- Se o motor não consegue ler a fatura, a saída é um veredicto (`LAYOUT DESCONHECIDO`, `BAIXA CONFIANCA` ou erro
  de leitura) com um aviso sem o conteúdo do PDF. A resposta é a conferência humana, nunca você abrir o PDF por
  fora do motor nem pedir print da fatura.

## Pré-requisitos

- Python 3.12 ou mais novo (`python --version`).
- As bibliotecas do motor: `python -m pip install -r requirements.txt` (`pdfplumber`, que lê o PDF, e
  `openpyxl`, que gera o XLSX). O resto é biblioteca-padrão do Python, e o motor não faz chamada de rede.

## Primeiro uso: rode o exemplo

O `exemplo/` traz 3 faturas fictícias, uma de cada veredicto:

```
python scripts/ler_fatura.py exemplo/fatura-01-itau-ok.pdf --saida saida-01
python scripts/ler_fatura.py exemplo/fatura-02-bradesco-total-nao-fecha.pdf --saida saida-02
python scripts/ler_fatura.py exemplo/fatura-03-generico-baixa-confianca.pdf --saida saida-03
```

Compare com `exemplo/RESULTADO-esperado.md`: **1 OK, 1 TOTAL NAO FECHA, 1 BAIXA CONFIANCA**. Se bater, está tudo
certo na máquina.

## Fluxo com a fatura real

Uma fatura:

```
python scripts/ler_fatura.py <fatura.pdf> [--saida <base>] [--formato csv|xlsx|todos] [--emissor auto|itau|bradesco|generico]
```

Lote (até 12 faturas de uma pasta, por exemplo vários portadores ou vários meses):

```
python scripts/ler_fatura.py --lote <pasta> --csv <saida.csv> [--xlsx <saida.xlsx>]
```

O lote consolida num CSV e num XLSX únicos, com o veredicto de cada fatura em cada linha, e lista no terminal as
faturas que não saíram `OK`. A mesma fatura duas vezes na pasta (mesmo conteúdo) entra uma vez só.

- `--formato`: `csv`, `xlsx` ou `todos` (padrão). O XLSX é o de conferência; o CSV é a carga crua, para
  planilha ou ERP.
- `--emissor`: força o leitor (`itau`, `bradesco` ou `generico`) no lugar da detecção automática; use só se o
  `auto` errar.
- Texto que começa com `=`, `+`, `-` ou `@` sai com um apóstrofo, para o Excel não executar como fórmula.

## Veredictos (o motor nunca finge que leu tudo)

`OK` (a soma fecha com o total impresso) · `TOTAL NAO FECHA` (a soma dos lançamentos mais os encargos não bate
com o total impresso: algo se perdeu na extração) · `LAYOUT DESCONHECIDO` (nenhuma linha reconhecível) ·
`BAIXA CONFIANCA` (o leitor genérico achou lançamentos, mas sem total impresso para provar a completude, ou alguma
linha que começa com data, no formato DD/MM/AAAA seguido de espaço, não foi lida: o aviso diz quantas, e a fatura não sai `OK` nem com a soma fechando). Cada um tem um
código de saída próprio (0, 2, 3 e 4; erro de leitura é 1).

## Como narrar a saída

Em português, direto, usando só o resumo que o terminal imprime: emissor, vencimento, quantos portadores,
lançamentos e encargos, total calculado contra total impresso e o veredicto. Se o veredicto não for `OK`, diga o
motivo (o aviso vem no resumo) e oriente a pessoa a abrir o XLSX na máquina dela para conferir lançamento a
lançamento.

## Limites

- **Sem OCR nesta versão.** Só PDF nativo, com texto extraível. Fatura escaneada ou foto fica de fora.
- **Sem fatura real ainda.** Os dois leitores (`itau` e `bradesco`) reconhecem um estilo estrutural (texto
  corrido com vários portadores, ou tabela por coluna), calibrado contra faturas sintéticas, não o layout de um
  banco real. A sua fatura pode cair no leitor genérico.
- **Layout fora dos dois estilos cai no leitor genérico, de melhor esforço.** Ele lê só data, estabelecimento e
  valor; nunca inventa portador, parcela, moeda nem total impresso. Por isso o genérico nunca sai `OK`: o teto é
  `BAIXA CONFIANCA`.
- **Não categoriza.** O CSV e o XLSX são o insumo cru; centro de custo e natureza ficam para depois.
- **Não concilia com o extrato bancário.** Para isso, a ferramenta é a Conciliação Bancária, do mesmo
  repositório.
- **Não é política de despesa.** É extração: quem aprova o gasto do portador é a pessoa, não o motor.
