# Fluxo de Caixa Direto

Junta os **extratos OFX das contas** com o **contas a pagar e a receber do ERP** e devolve o **fluxo de caixa pelo
método direto**: o realizado por categoria e mês e a projeção rolante das próximas 13 semanas, com alerta de semana
que fica negativa e de título vencido que segue em aberto. O motor Python categoriza cada lançamento por um
dicionário de termos em português, editável em CSV, e o que ele não reconhece vira "Não classificado", nunca um
chute. É para quem monta essa planilha à mão todo mês, copiando o extrato ao lado do export do ERP.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `fluxo-de-caixa-direto`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install fluxo-de-caixa-direto@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `fluxo-de-caixa-direto.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. **Aqui o arquivo anexado e os scripts rodam na nuvem da Anthropic**, não no seu computador. |
| **Terminal** | `python scripts/fluxo_caixa.py --extratos PASTA_DOS_OFX --pagar contas-a-pagar.csv --receber contas-a-receber.csv` (de dentro de `skills/fluxo-de-caixa-direto/`). |

## Requisitos

- **Python 3.10 ou mais**.
- **Dependência**, instalada uma vez com `pip install -r requirements.txt` (dentro de
  `skills/fluxo-de-caixa-direto/`): `openpyxl`, que gera a planilha de saída e lê títulos em XLSX. O resto é
  biblioteca-padrão do Python.

Para testar sem dado seu, use o cenário fictício em
[`skills/fluxo-de-caixa-direto/exemplo/`](skills/fluxo-de-caixa-direto/exemplo/) (um extrato, contas a pagar e a
receber e o resultado esperado).

## Como usar

```
python scripts/fluxo_caixa.py --extratos PASTA_OU_ARQUIVOS.ofx \
       --pagar contas-a-pagar.csv --receber contas-a-receber.csv \
       --perfil generico --semanas 13 --saida resultado
```

- `--perfil omie` lê o export padrão do Omie; `generico` (padrão) aceita os cabeçalhos comuns (fornecedor ou
  cliente, documento, vencimento, valor, status).
- `--contas-proprias contas.txt` marca como "Transferências Internas" o lançamento entre contas suas.
- `--dicionario meu.csv` troca o dicionário de categorias pelo seu (`categoria,keyword`).

Sai no seu disco: `fluxo-de-caixa.xlsx` com 5 abas (Resumo, Realizado, Lançamentos, Títulos em aberto, Alertas) e,
se pedir, um CSV por aba (`--csv`) e um JSON (`--json`). Na tela sai só o resumo: contagens, o saldo total, quantas
semanas ficam negativas e quantos alertas há.

## Privacidade

- **Terminal**: o motor lê os arquivos no seu computador e nada sai dele.
- **Claude Code, em sessão local**: o motor também lê os arquivos no disco, e a skill foi feita para o Claude ler
  só o resumo que ele imprime, mas o seu pedido, esse resumo e qualquer arquivo que o Claude abrir vão para a
  Anthropic. A skill pede ao Claude que não abra os extratos, os títulos nem os arquivos de saída, que trazem
  conta, contraparte, documento e valores.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra) e **claude.ai** (web ou app): o trabalho roda na nuvem
  da Anthropic e o arquivo sobe para lá. Nesse caso, rode no terminal ou no Claude Code em sessão local.

O motor não faz chamada de rede.

## Limites

- **A projeção assume que todo título em aberto é pago no vencimento.** Não é conciliação nem garantia: a frase
  sai no rodapé de toda saída.
- **Não concilia título com lançamento bancário.** Título vencido em aberto vira alerta. Para conciliar, use a
  [Conciliação Bancária](../conciliacao-bancaria/README.md), deste mesmo repositório.
- **A baixa do título depende do status no export do ERP.** O motor não deduz pagamento pelo extrato; status
  desconhecido fica em aberto, por segurança.
- **O perfil Omie** foi mapeado do export padrão, sem um export real conferido; se as colunas do seu diferirem,
  use o `generico`.
- **Saldo ilegível no OFX** não derruba a rodada: a conta fica com o saldo estimado pela soma dos lançamentos e
  sai o alerta `SALDO_ESTIMADO`. Lançamento sem data ou valor legível fica de fora, com o alerta
  `LANCAMENTO_ILEGIVEL` e a contagem no terminal.
- **Extrato em PDF não entra**: o motor lê OFX, uma conta por arquivo e só em reais. Arquivo com duas contas (ou conta e
  cartão) ou em outra moeda é recusado. Descrição em bloco CDATA do OFX XML não é lida: o lançamento vai para "Não classificado".
- Texto que começa com `=`, `+`, `-` ou `@` ganha um apóstrofo na frente, no CSV e na planilha, para o Excel não
  executar como fórmula.

## Testes

Da raiz do repositório:

```
cd plugins/fluxo-de-caixa-direto
python -m pip install -r skills/fluxo-de-caixa-direto/requirements.txt pytest
python -m pytest -q tests
```

Um teste é pulado aqui: o de aceite com o OFX que o Conversor de Extrato emite, que só roda no repositório de
origem.

## Licença

[Apache-2.0](../../LICENSE).
