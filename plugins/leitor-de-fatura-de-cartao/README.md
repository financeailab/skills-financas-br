# Leitor de Fatura de Cartão

Lê o **PDF da fatura do cartão corporativo** e devolve cada lançamento (data, estabelecimento, valor, parcela,
portador e moeda) em **CSV e XLSX**, com uma **prova de completude**: a soma dos lançamentos mais os encargos tem
que fechar com o total impresso na fatura, senão o veredicto avisa em vez de fingir que leu tudo. É para quem
digita a fatura na planilha para fechar a prestação de contas por portador.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `leitor-de-fatura-de-cartao`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install leitor-de-fatura-de-cartao@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `leitor-de-fatura-de-cartao.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. **Aqui o arquivo anexado e os scripts rodam na nuvem da Anthropic**, não no seu computador. |
| **Terminal** | `python scripts/ler_fatura.py fatura.pdf` (de dentro de `skills/leitor-de-fatura-de-cartao/`). |

## Requisitos

- **Python 3.12 ou mais**.
- **Dependências**, instaladas uma vez com `pip install -r requirements.txt` (dentro de
  `skills/leitor-de-fatura-de-cartao/`): `pdfplumber`, que lê o PDF, e `openpyxl`, que gera a planilha. O resto é
  biblioteca-padrão do Python.
- A fatura em **PDF nativo**, com texto extraível (não escaneada).

Para testar sem dado seu, use as 3 faturas fictícias em
[`skills/leitor-de-fatura-de-cartao/exemplo/`](skills/leitor-de-fatura-de-cartao/exemplo/), uma de cada veredicto,
com o resultado esperado.

## Como usar

```
python scripts/ler_fatura.py fatura.pdf --saida resultado
python scripts/ler_fatura.py --lote PASTA_DAS_FATURAS --csv consolidado.csv --xlsx consolidado.xlsx
```

- `--formato csv|xlsx|todos` escolhe a saída (padrão: os dois).
- `--emissor itau|bradesco|generico` força o leitor no lugar da detecção automática.
- O lote lê até 12 PDFs de uma pasta e consolida num CSV e num XLSX únicos; a mesma fatura duas vezes entra uma
  vez só.

Sai no seu disco: o CSV e o XLSX com os lançamentos. Na tela sai só o resumo: emissor, vencimento, quantos
portadores, lançamentos e encargos, o total calculado, o total impresso e o veredicto (`OK`, `TOTAL NAO FECHA`,
`LAYOUT DESCONHECIDO` ou `BAIXA CONFIANCA`, cada um com o seu código de saída). No lote, a tela lista o nome de
cada arquivo que não saiu `OK`.

## Privacidade

- **Terminal**: o motor lê o PDF no seu computador e nada sai dele.
- **Claude Code, em sessão local**: o motor também lê o PDF no disco, e a skill foi feita para o Claude ler só o
  resumo que ele imprime, mas o seu pedido, esse resumo e qualquer arquivo que o Claude abrir vão para a
  Anthropic. A skill pede ao Claude que não abra a fatura nem os arquivos de saída, que trazem portador,
  estabelecimento e valor de cada lançamento.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra) e **claude.ai** (web ou app): o trabalho roda na nuvem
  da Anthropic e o PDF sobe para lá. Nesse caso, rode no terminal ou no Claude Code em sessão local.

O motor não faz chamada de rede.

## Limites

- **Sem OCR nesta versão**: só PDF nativo. Fatura escaneada ou foto fica de fora.
- **Sem fatura real ainda.** Os leitores `itau` e `bradesco` reconhecem um estilo estrutural, calibrado contra
  faturas sintéticas, não o layout de um banco real; a sua fatura pode cair no leitor genérico.
- **O leitor genérico** lê só data, estabelecimento e valor, nunca inventa portador, parcela ou total impresso, e
  nunca sai `OK`: o teto é `BAIXA CONFIANCA`.
- **Linha que começa com data (DD/MM/AAAA) seguida de espaço e que o motor não consegue ler não some calada**: o
  aviso diz quantas, e a fatura não sai `OK` nem com a soma fechando. Fica fora dessa conta a data colada no texto,
  sozinha na linha, seguida de pontuação, em outro formato ou no meio da linha.
- **Não categoriza, não concilia com o extrato e não aprova despesa.** Para conciliar, use a
  [Conciliação Bancária](../conciliacao-bancaria/README.md), deste mesmo repositório.
- Texto que começa com `=`, `+`, `-` ou `@` ganha um apóstrofo na frente, no CSV e na planilha, para o Excel não
  executar como fórmula.

## Testes

Da raiz do repositório:

```
cd plugins/leitor-de-fatura-de-cartao
python -m pip install -r skills/leitor-de-fatura-de-cartao/requirements.txt reportlab pytest
python -m pytest -q tests
```

Os testes geram os PDFs sintéticos na hora, com o `reportlab`.

## Licença

[Apache-2.0](../../LICENSE).
