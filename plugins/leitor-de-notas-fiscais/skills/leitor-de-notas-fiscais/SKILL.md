---
name: leitor-de-notas-fiscais
description: >-
  Lê notas fiscais recebidas de fornecedores (NFS-e de serviço e NF-e de produto, em XML, PDF
  ou foto), confere com regras fiscais determinísticas, dá uma confiança de 0 a 1 por nota e
  gera o arquivo de carga de contas a pagar (Omie, ContaAzul ou CSV genérico). Use quando a
  pessoa quiser transformar uma pilha de notas fiscais em carga de contas a pagar.
---

# Leitor de Notas Fiscais, Finance AI Lab

Você (Claude) **orquestra**; o **motor Python** em `scripts/` lê a nota, confere as regras fiscais,
calcula a confiança e monta a carga, sempre do mesmo jeito para a mesma entrada.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Contrato de privacidade, por plataforma

O que vale depende de onde a conversa roda e de qual caminho a nota segue. Diga isso à pessoa, sem prometer
o que a plataforma não entrega.

- **XML, no terminal ou no Claude Code em sessão local:** o motor lê o XML no disco. Peça o caminho da pasta,
  do ZIP ou do arquivo; não peça para ela colar ou anexar o conteúdo e não abra o XML. Você lê só o que o motor
  imprime: contagens por família e por status, sem nome de arquivo, fornecedor, CNPJ ou valor. O pedido dela,
  esse resumo e qualquer arquivo que você abrir vão para a Anthropic.
- **Os arquivos de saída** (`carga.csv`, `carga.xlsx`, `excecoes.csv`) trazem fornecedor, CNPJ, valores e o
  nome de cada arquivo. Você não os abre. Para ver nota a nota, oriente a pessoa a abrir a `carga.xlsx`. Se ela
  pedir que você confira, lembre que o que você abrir vai para a Anthropic e deixe a decisão com ela.
- **PDF ou foto:** aqui você lê o documento, e ele vai para a Anthropic em qualquer plataforma. Diga isso antes
  de ler e ofereça o XML da mesma nota, que é o caminho em que você não abre a nota.
- **No Cowork ou numa conversa comum do Claude (web ou app):** o arquivo está na nuvem da Anthropic. Avise a
  pessoa antes de ela anexar, em vez de dizer que nada sobe, e sugira o terminal ou o Claude Code em sessão local.

## Pré-requisitos

- Python 3.12 ou mais novo (`python --version`).
- Bibliotecas do motor: `python -m pip install -r requirements.txt` (pydantic, defusedxml e openpyxl). O
  `defusedxml` lê o XML de forma segura, contra nota maliciosa; o motor não roda sem ele. O `openpyxl` gera a
  planilha `carga.xlsx`, já formatada para conferência no Excel.
- As notas: **XML** (o melhor, vem no e-mail do fornecedor) e/ou **PDF ou foto**. Lote numa pasta ou num **ZIP**,
  até 50 notas por rodada. Acima disso, o motor lê as 50 primeiras em ordem alfabética, lista as outras no
  `excecoes.csv` como "acima do limite de 50 por lote" e avisa: rode de novo com o resto.

## Primeiro uso: rode o exemplo

O `exemplo/` traz notas fictícias, uma por família de XML, e uma extração de PDF já pronta. Rode os dois antes
do dado real:

```
# 1) XML (4 notas, uma por família)
python scripts/ler_notas.py processar --entrada exemplo --perfil generico --out resultado-exemplo

# 2) PDF ou foto já lido (NFS-e escaneada)
python scripts/ler_notas.py processar-pdf --extracoes exemplo/extracoes-exemplo.json --out resultado-pdf
```

Compare com `exemplo/RESULTADO-esperado.md`. O exemplo inclui também `nota-servico.pdf` e `nota-foto.png` (a
mesma nota fictícia como PDF e como foto de celular): se a pessoa quiser ver a leitura de PDF, você abre o
arquivo, lê seguindo `scripts/ler-nfse/extrair-pdf.md` e gera a carga.

## Setup, uma vez por lote: a empresa que recebe a nota

Pergunte: **"Qual o CNPJ e o município (código IBGE) da sua empresa?"** Isso liga o cruzamento de retenção
(a empresa precisa recolher o ISS?), o endereçamento (a nota é sua?) e o alerta de retenção não destacada
(LC 116). Passe por `--tomador-cnpj` e `--tomador-municipio`. Sem isso, a skill roda sem esses três sinais.
O CNPJ que ela digitar faz parte do pedido e vai para a Anthropic com ele.
Detalhe: `scripts/ler-nfse/setup-tomador.md`.

## Fluxo

### XML

```
python scripts/ler_notas.py validar   --entrada PASTA_OU_ARQUIVO        # quantas notas por família
python scripts/ler_notas.py processar --entrada PASTA|LOTE.zip|NOTA.xml \
       --perfil omie --tomador-cnpj 11222333000181 --tomador-municipio 3550308 --out resultado
```

Gera, no disco da pessoa, `resultado/carga.csv` (para o ERP), `resultado/carga.xlsx` (planilha de conferência),
`resultado/excecoes.csv` (o que pede atenção) e `resultado/resumo.json` (as contagens que você lê).

### PDF ou foto (você lê)

1. Avise que você vai abrir o documento e que ele vai para a Anthropic.
2. Para cada PDF ou foto, leia seguindo `scripts/ler-nfse/extrair-pdf.md` e produza o dicionário de extração,
   com a chave de acesso, o número e o CNPJ do prestador. O motor só reconhece a mesma nota lida duas vezes pela
   chave de acesso, ou pelo CNPJ junto com o número; sem nenhum dos dois, as duas entram na carga.
3. Junte num JSON `[{"arquivo": "x.pdf", "extracao": {...}}, ...]`.
4. ```
   python scripts/ler_notas.py processar-pdf --extracoes extracoes.json --perfil omie --out resultado
   ```

## Como narrar o resumo

Em português, direto: quantas notas chegaram (`recebidas`), quantas foram **auto-aprovadas**, quantas pedem
**conferir**, quantas falharam e, se `fora_do_limite` for maior que zero, que é preciso rodar de novo com o
resto. Se `repetidas` for maior que zero, a mesma nota veio mais de uma vez no lote: a carga leva só a primeira,
e as outras estão no `excecoes.csv`. Os motivos de cada nota ficam na coluna `motivos` da `carga.xlsx` e no `excecoes.csv`: oriente a pessoa a
abrir a planilha e começar pelas linhas em "conferir". Aponte a `carga.csv` para subir no ERP. **Nunca** invente
valor que o motor não extraiu.

## Captura e sinaliza, a pessoa decide

A ferramenta **extrai os dados e sinaliza** o que merece atenção; **as decisões financeiras são da pessoa**:

- **Retenções:** o motor captura IRRF, PIS, COFINS, CSLL, INSS e ISS e o `valor_liquido` que a nota declara.
  O líquido a pagar quem decide é a pessoa; a ferramenta não calcula nem impõe.
- **Devolução ou retorno:** captura a natureza da operação (natOp) e sinaliza que o valor pode ser crédito,
  mandando para conferir. Não inverte o sinal por conta própria.
- **Cancelada:** com o carimbo CANCELADA (PDF) ou o status homologado de cancelamento (NF-e em XML: cStat
  101/151 ou evento 110111 com 135), a nota vai para conferir com "não pagar / não lançar". O cancelamento de
  NFS-e é evento na prefeitura, fora do XML; só o carimbo no PDF pega.
- **ISS sem alíquota na NFS-e nacional:** o XML do Sistema Nacional pode vir sem a alíquota. Aí o motor não
  confere o ISS, segue pelas outras regras e anota "Aliquota de ISS nao veio no XML: ISS nao conferido".

## Limites honestos

- Auto-aprova só com confiança alta; na dúvida, deixa para conferir (errar uma nota é pior).
- O **centro de custo** sai em branco para a pessoa preencher; a **Categoria** (`natureza`) vem com a natureza
  da operação capturada. O **vencimento** vem quando a leitura o pega (NFS-e na discriminação; NF-e no bloco
  Fatura/Duplicata do PDF); senão, fica em branco. No XML da NF-e, as duplicatas ainda não são lidas: a coluna
  sai em branco mesmo quando a nota traz o vencimento.
- **Uma nota por arquivo XML.** O arquivo com várias notas num envelope só (a consulta de lote de algumas
  prefeituras, por exemplo) vai para as exceções, com o motivo: separe uma nota por arquivo.
- **Retenções federais no ABRASF** (IR, PIS, COFINS, CSLL e INSS) ainda não são lidas: as colunas saem vazias e
  a nota vai para conferir, para a pessoa conferir o valor líquido na própria nota.
- **NF-e com FCP-ST** (o fundo de combate à pobreza na substituição tributária) não fecha o total no motor: vai
  para conferir mesmo estando certa.
- Texto da nota que começa com `=`, `+`, `-` ou `@` ganha um apóstrofo na frente no CSV, para o Excel não executar
  como fórmula; na planilha, a célula é gravada como texto. No ERP, esse nome entra com o apóstrofo.
- XML fora de UTF-8 (alguns municipais antigos) e CNPJ alfanumérico novo da Receita ainda não são lidos: a nota
  vira exceção ou vai para conferir, contada no resumo.
- **Lê só nota fiscal (NFS-e e NF-e).** Boleto, recibo, nota de débito, fatura e invoice internacional ficam
  fora (são rejeitados e não viram linha de carga). Importação de produto (DI/DUIMP), CT-e e duplicata
  escritural também ficam fora.
