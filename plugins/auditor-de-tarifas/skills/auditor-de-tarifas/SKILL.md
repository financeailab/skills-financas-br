---
name: auditor-tarifas
description: >-
  Responde "quanto seu banco te cobrou de tarifa esse ano?". A pessoa cola ou anexa
  o extrato (OFX/CSV) e o motor Python local soma as tarifas (manutencao, TED/DOC,
  Pix PJ, boleto, custodia, cambio) por banco, mes e tipo, com o IOF separado (imposto,
  nao tarifa). O motor roda local; o Claude le so o resumo agregado (totais), nunca o
  lancamento individual. Use quando a pessoa quiser auditar/somar as tarifas do banco no Brasil.
---

# Auditor de Tarifas Bancárias, Finance AI Lab

Trilha **Tesouraria** (Caixa) · wedge **custo bancário**. O degrau de entrada da auditoria de tarifas.

Ninguém sabe quanto paga de tarifa por ano porque ela vem picada: R$12,90 de manutenção aqui, R$10,90 de um TED ali, R$2,90 de um boleto acolá. Cada linha é pequena demais pra doer. Somado em 12 meses, não. Este produto soma, separa o que é **tarifa** (negociável) do que é **imposto** (IOF), e devolve o número que vira argumento pra renegociar a cesta ou portar o relacionamento.

## Contrato de privacidade (o fosso do produto)

> Os extratos (OFX/CSV, valores, contrapartes) **não trafegam para fora da máquina da pessoa**. O motor Python classifica e soma **localmente** e grava um CSV no disco dela. Para você (Claude) sobe só o **resumo agregado** (total de tarifa, quebra por banco/mês/tipo, contagem de não-classificados). **Nenhum lançamento individual** com valor e contraparte aparece no stdout dirigido por IA. Se a pessoa quiser ver linha a linha, oriente-a a abrir o CSV local (`--saida`).

## O que ele faz (e o que não faz)

Faz: soma **só a tarifa** (não categoriza o resto do extrato), separa o IOF, mostra por banco, por mês e por tipo, e aponta os lançamentos que não reconheceu (transparência, não esconde).

Não faz: **não categoriza tudo** (isso é o Categorizador de Lançamentos, o produto maior), **não concilia**, **não renegocia** por você (orienta as duas jogadas), **não compara bancos** (audita o que já te cobraram). Não trata juros (cheque especial, antecipação) como tarifa.

## Como usar

O motor é o `scripts/auditar_tarifas.py`. A pessoa exporta o extrato do ano (OFX ou CSV, um por conta) e roda:

```
py scripts/auditar_tarifas.py <extrato.ofx> [<extrato2.csv> ...] [--ano 2025] [--saida auditoria.csv]
```

- Entrada: um ou mais extratos OFX/CSV, ou um diretório.
- `--ano`: filtra um ano-calendário (o total anual é o número que choca).
- `--saida`: grava o CSV **local** classificado (`data, descricao, valor, banco, tipo`) pra conferência linha a linha. Não sai no stdout.

O stdout traz **só o resumo seguro**: total anual de tarifa, tabela por banco, por mês, por tipo, o total de IOF à parte, o veredicto e quantos lançamentos ficaram pra conferir.

## Fluxo que você (Claude) conduz

1. Peça o extrato do período (OFX de preferência; CSV serve). Explique que é **um arquivo por conta** e que **nada sobe pra nuvem** (roda na máquina dela).
2. Rode o motor local. Leia **só o resumo**.
3. Apresente o número anual, a quebra por tipo (quase sempre manutenção e boleto lideram) e o mês fora da curva, se houver.
4. Aponte as **duas jogadas** com o número na mão:
   - **Renegociar a cesta.** Tarifa PJ é livre; o gerente tem margem. A frase que abre desconto: "paguei R$ X de tarifa esse ano, R$ Y só na cesta".
   - **Portar o relacionamento.** Se o banco não mexer, a portabilidade existe. O número anual torna a decisão fácil.
5. Se o veredicto for `CONFERIR`, avise que há lançamentos não reconhecidos e oriente abrir o CSV local antes de fechar o número.

## Veredictos

- `OK`: somou, nada pendente relevante.
- `CONFERIR`: há lançamentos com marca de tarifa que não caíram em nenhuma categoria (aparecem como `outra_tarifa`); confira o CSV local antes de confiar 100% na quebra por tipo. O total ainda vale.
- `SEM TARIFA ENCONTRADA`: o extrato não tinha termo de tarifa reconhecível (conta isenta, ou nome fora do dicionário). Nunca inventa um número.

## Honestidade

Somar tarifa é algo que uma planilha faz, desde que você tenha o dicionário de termos certo (que é o trabalho chato, e é o que este produto entrega pronto). Não é um robô que adivinha; é um dicionário de termos de tarifa BR + uma soma determinística, rodando no seu Claude, sem o extrato sair da sua máquina. Para o extrato só em **PDF**, ou pra categorizar **tudo** (não só tarifa) e conciliar, o caminho é o Categorizador de Lançamentos da trilha.
