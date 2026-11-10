# Leitor de Notas Fiscais

Lê as **notas fiscais que os fornecedores mandam** (NFS-e de serviço e NF-e de produto, em XML, PDF ou foto) e
monta a **carga de contas a pagar** para o seu ERP. O motor Python confere cada nota com regras fiscais (o ISS
fecha com base e alíquota? o líquido fecha com as retenções? o CNPJ tem dígito válido? a nota está
cancelada?), dá uma confiança de 0 a 1 e separa o que pode subir direto do que pede conferência. É para quem
digita nota de entrada no contas a pagar, uma a uma.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `leitor-de-notas-fiscais`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install leitor-de-notas-fiscais@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `leitor-de-notas-fiscais.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. **Aqui o arquivo anexado e os scripts rodam na nuvem da Anthropic**, não no seu computador. |
| **Terminal** | `python scripts/ler_notas.py processar --entrada PASTA_DAS_NOTAS --perfil generico --out resultado` (de dentro de `skills/leitor-de-notas-fiscais/`). |

## Requisitos

- **Python 3.12 ou mais**.
- **Dependências**, instaladas uma vez com `pip install -r requirements.txt` (dentro de
  `skills/leitor-de-notas-fiscais/`): `pydantic` (modelo da nota), `defusedxml` (leitura segura do XML, contra
  nota maliciosa) e `openpyxl` (a planilha `carga.xlsx`). O motor não roda sem elas.

Para testar sem dado seu, use as notas fictícias em
[`skills/leitor-de-notas-fiscais/exemplo/`](skills/leitor-de-notas-fiscais/exemplo/) (uma por família de XML,
uma extração de PDF e o resultado esperado).

## Como usar

```
# quantas notas por família (nacional, ABRASF, São Paulo, NF-e)
python scripts/ler_notas.py validar   --entrada PASTA_OU_ARQUIVO

# a carga: pasta, ZIP ou um XML; perfil generico, omie ou contaazul
python scripts/ler_notas.py processar --entrada PASTA|LOTE.zip|NOTA.xml --perfil omie \
       --tomador-cnpj 11222333000181 --tomador-municipio 3550308 --out resultado

# PDF ou foto: o Claude lê o documento e entrega as extrações em JSON
python scripts/ler_notas.py processar-pdf --extracoes extracoes.json --perfil omie --out resultado
```

Sai no seu disco: `carga.csv` (para o ERP), `carga.xlsx` (planilha de conferência, colorida pela confiança),
`excecoes.csv` (o que pede atenção, com o motivo) e `resumo.json` (as contagens). Até 50 notas por rodada:
acima disso, as excedentes ficam listadas no `excecoes.csv` e o resumo avisa quantas ficaram fora.
A mesma nota repetida no lote (mesma chave) entra uma vez só na carga; as cópias vão para o `excecoes.csv`.
No PDF ou na foto, isso depende de a leitura trazer a chave de acesso, ou o CNPJ e o número da nota.

## Privacidade

- **Terminal**: o motor lê o XML no seu computador e nada sai dele.
- **Claude Code, em sessão local, com XML**: o motor também lê o XML no disco, e a skill foi feita para o Claude
  ler só o resumo que ele imprime (contagens por família e por status), mas o seu pedido, esse resumo e qualquer
  arquivo que o Claude abrir vão para a Anthropic. A skill pede ao Claude que não abra o XML nem os arquivos de
  saída, que trazem fornecedor, CNPJ e valores.
- **PDF ou foto**: o Claude lê o documento, então ele vai para a Anthropic, em qualquer plataforma. Se você tem
  o XML da mesma nota, prefira o XML.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra) e **claude.ai** (web ou app): o trabalho roda na nuvem
  da Anthropic e o arquivo sobe para lá. Nesse caso, rode no terminal ou no Claude Code em sessão local.

O motor não faz chamada de rede.

## Limites

- **Lê nota fiscal, e só ela** (NFS-e nacional, ABRASF e São Paulo; NF-e modelo 55). Boleto, recibo, nota de
  débito, fatura, invoice internacional, CT-e e importação (DI/DUIMP) ficam fora e são rejeitados.
- **A ferramenta captura e sinaliza; quem decide é você.** O líquido a pagar, o sentido de uma devolução e o
  lançamento de uma nota cancelada ficam com você.
- **NFS-e nacional sem alíquota:** o XML do Sistema Nacional pode vir sem a alíquota de ISS; aí o motor não
  confere o ISS e anota isso na nota, em vez de reprovar.
- **Uma nota por arquivo XML:** o arquivo com várias notas num envelope só vai para o `excecoes.csv`, com o
  motivo; separe uma nota por arquivo.
- **Retenções federais no ABRASF** (IR, PIS, COFINS, CSLL e INSS) ainda não são lidas: as colunas saem vazias e
  a nota vai para conferir. Confira o valor líquido na própria nota.
- **NF-e com FCP-ST** (fundo de combate à pobreza na substituição tributária) não fecha o total no motor: vai
  para conferir mesmo estando certa.
- **Centro de custo** sai em branco; **vencimento** só quando a leitura o pega. No XML da NF-e, as duplicatas
  ainda não são lidas: a coluna sai em branco mesmo quando a nota traz o vencimento.
- Texto que começa com `=`, `+`, `-` ou `@` ganha um apóstrofo no CSV, para o Excel não executar como fórmula; na
  planilha, a célula é gravada como texto. No ERP, esse nome entra com o apóstrofo.
- XML fora de UTF-8 (alguns municipais antigos) e CNPJ alfanumérico novo da Receita ainda não são lidos: a nota
  vira exceção ou vai para conferir.
- O layout de importação de cada ERP muda: confira a primeira carga antes de apoiar o fechamento nela.

## Testes

Da raiz do repositório:

```
cd plugins/leitor-de-notas-fiscais
python -m pip install -r skills/leitor-de-notas-fiscais/requirements.txt pytest
python -m pytest -q tests
```

## Licença

[Apache-2.0](../../LICENSE).
