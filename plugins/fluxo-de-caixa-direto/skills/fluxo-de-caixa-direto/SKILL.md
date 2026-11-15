---
name: fluxo-de-caixa-direto
description: >-
  Junta os extratos OFX das contas com os exports de contas a pagar e a receber do ERP
  (Omie ou genérico, CSV ou XLSX), categoriza o realizado por um dicionário em português
  editável e devolve o DFC método direto: realizado por categoria e mês e projeção rolante
  de 13 semanas, com alerta de semana negativa e de título vencido em aberto. Use quando a
  pessoa precisar montar o fluxo de caixa (DFC direto) ou projetar o caixa das próximas
  semanas a partir do ERP e do banco.
---

# Fluxo de Caixa Direto, Finance AI Lab

Você (Claude) **orquestra**; o **motor Python** em `scripts/` lê os extratos, cruza com os títulos do ERP,
categoriza e projeta, sempre do mesmo jeito para a mesma entrada.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Contrato de privacidade, por plataforma

O que vale depende de onde a conversa roda. Diga isso à pessoa, sem prometer o que a plataforma não entrega.

- **No terminal ou no Claude Code em sessão local:** o motor lê os OFX e os títulos no disco. Peça o caminho
  das pastas e dos arquivos; não peça para ela colar ou anexar o conteúdo e não abra esses arquivos. Você lê só
  o que o motor imprime: contagem de arquivos, contas, lançamentos e títulos, o saldo total, quantas semanas
  ficam negativas e quantos alertas há. O pedido dela, esse resumo e qualquer arquivo que você abrir vão para a
  Anthropic.
- **Os arquivos de saída** (`fluxo-de-caixa.xlsx`, os CSV e o JSON) trazem conta, descrição, contraparte,
  documento e valor de cada linha. Você não os abre. Para ver linha a linha, oriente a pessoa a abrir o XLSX. Se
  ela pedir que você confira, lembre que o que você abrir vai para a Anthropic e deixe a decisão com ela.
- **No Cowork ou numa conversa comum do Claude (web ou app):** o arquivo está na nuvem da Anthropic. Avise a
  pessoa antes de ela anexar, em vez de dizer que nada sobe, e sugira o terminal ou o Claude Code em sessão local.
- Se um arquivo não abre, o motor devolve um erro em português com a linha e a coluna, sem o conteúdo. A saída
  nunca é colar o extrato na conversa ou mandar print.

## Pré-requisitos

- Python 3.10 ou mais novo (`python --version`).
- A biblioteca do motor: `python -m pip install -r requirements.txt` (openpyxl, que gera o XLSX e lê títulos
  em XLSX). O resto do motor é biblioteca-padrão do Python, e o motor não faz chamada de rede.

## Primeiro uso: rode o exemplo

O `exemplo/` traz um cenário fictício completo (1 extrato OFX, contas a pagar e a receber):

```
python scripts/fluxo_caixa.py --extratos exemplo/extrato-conta-corrente.ofx \
    --pagar exemplo/contas-a-pagar.csv --receber exemplo/contas-a-receber.csv \
    --data-base 2026-07-20 --saida exemplo/resultado
```

Compare com `exemplo/RESULTADO-esperado.md`: **7 lançamentos, saldo R$ 6.721,10, 4 títulos em aberto, 2
alertas**. Se bater, está tudo certo na máquina.

## Fluxo com o dado real

```
python scripts/fluxo_caixa.py --extratos PASTA-COM-OFX \
    [--pagar contas-a-pagar.csv|.xlsx] [--receber contas-a-receber.csv|.xlsx] \
    [--perfil omie|generico] [--semanas 13] [--data-base AAAA-MM-DD] \
    [--contas-proprias contas.txt] [--dicionario custom.csv] \
    [--saida pasta] [--xlsx] [--csv] [--json]
```

- `--extratos`: um ou mais arquivos `.ofx` e/ou pastas com `.ofx` (várias contas; lançamento repetido entre
  arquivos sai uma vez, pela conta e pelo FITID).
- `--pagar` / `--receber`: os exports do ERP. Sem os dois, o motor roda só o realizado e avisa que a projeção
  fica vazia.
- `--perfil`: `omie` para o export padrão do Omie; `generico` (padrão) aceita os cabeçalhos comuns (fornecedor
  ou cliente, documento, vencimento, valor, status). Coluna obrigatória faltando gera erro dizendo qual.
- `--contas-proprias`: arquivo texto com um identificador de conta por linha; lançamento cuja descrição traga um
  deles vira "Transferências Internas" (não infla entrada nem saída).
- `--dicionario`: CSV `categoria,keyword` próprio (a pessoa pode editar o `dicionario-categorias.csv` que vem
  com a skill e passar aqui).
- Saída padrão: XLSX com 5 abas (Resumo, Realizado, Lançamentos, Títulos em aberto, Alertas). `--csv` gera um
  CSV por aba; `--json` grava tudo num arquivo. Texto que começa com `=`, `+`, `-` ou `@` sai com um apóstrofo,
  para o Excel não executar como fórmula.

## Como narrar a saída

Em português, direto, usando só o resumo que o terminal imprime: quantos extratos e lançamentos, o saldo atual,
quantos títulos em aberto, se há semana projetada negativa e quantos alertas. O detalhe (qual título, qual
lançamento, qual categoria) fica no XLSX, e a conferência lá é da pessoa. Sempre repita a frase que o motor
imprime: **"Projeção assume título pago no vencimento. Não é conciliação nem garantia."** Se a pessoa perguntar
"posso pagar X na semana 3?", a resposta é apontar a aba Resumo, nunca decidir por ela.

## Categorização sem chute

O realizado é categorizado por um **dicionário em português editável** (`dicionario-categorias.csv`, keyword →
categoria). Precedência: conta própria, depois a keyword mais longa, depois a primeira na ordem do arquivo.
Descrição que não bate nenhuma keyword vira **"Não classificado"**, nunca um palpite, e cada lançamento sai com a
`regra_aplicada`. Se mais de 20% dos lançamentos ficarem sem categoria, o motor emite `NAO_CLASSIFICADO_ALTO`: a
resposta é a pessoa **editar o CSV do dicionário** com os termos do banco dela, não você inventar categorias.

## Alertas que o motor emite

- `SEMANA_NEGATIVA`: saldo projetado abaixo de zero em alguma semana.
- `ATRASADO_EM_ABERTO`: título venceu antes da data-base e segue em aberto no ERP.
- `SALDO_ESTIMADO`: conta sem saldo legível no OFX (o saldo vira a soma dos lançamentos).
- `DADO_VELHO`: extrato com data de saldo mais de 7 dias antes da data-base.
- `LANCAMENTO_ILEGIVEL`: lançamento do OFX sem data ou valor legível ficou de fora; o terminal diz quantos.
- `NAO_CLASSIFICADO_ALTO`: mais de 20% dos lançamentos sem categoria.

## Limites

- **A projeção assume que todo título em aberto é pago no vencimento.** Não é conciliação nem garantia.
- **Não concilia título com lançamento bancário.** Título vencido em aberto vira alerta, não casamento. Para
  conciliar, a ferramenta é a Conciliação Bancária, do mesmo repositório.
- **A baixa de um título depende do status no export do ERP.** O motor não infere pagamento pelo extrato. Status
  desconhecido fica em aberto, por segurança (um título a mais para conferir, nunca um pagamento sumido).
- **Perfil `omie`** foi mapeado do export padrão, sem export real conferido; se as colunas diferirem, use o
  `generico`.
- **Extrato em PDF não entra direto.** Este motor lê OFX, uma conta por arquivo e só em reais: arquivo com duas
  contas (ou conta e cartão) ou em outra moeda é recusado com a mensagem do motor. Descrição em bloco CDATA do OFX XML não é lida e
  o lançamento vai para "Não classificado".
- **Sem Open Finance e sem machine learning.** O motor não move dinheiro nem sugere ação: monta o DFC e alerta.
