# Resultado esperado do exemplo

Rode (a partir da pasta onde a skill foi instalada):

```
python scripts/fluxo_caixa.py --extratos exemplo/extrato-conta-corrente.ofx \
    --pagar exemplo/contas-a-pagar.csv --receber exemplo/contas-a-receber.csv \
    --data-base 2026-07-20 --saida exemplo/resultado
```

Todos os dados são **fictícios** (1 conta corrente, 7 lançamentos, 3 títulos a pagar, 2 a
receber; nenhum CNPJ, nome ou valor real).

## Saída no console

```
== FLUXO DE CAIXA DIRETO ==
  extratos: 1 arquivo(s) | 1 conta(s) | 7 lancamento(s)
  saldo atual: R$ 6721.10
  titulos em aberto: 4
  alertas: 2 (ver aba/arquivo Alertas)
  saida: exemplo/resultado/fluxo-de-caixa.xlsx
  Projeção assume título pago no vencimento. Não é conciliação nem garantia.
```

## Por quê

| Item | Valor esperado | Por quê |
|---|---|---|
| Lançamentos realizados | 7 | os 7 lançamentos do extrato, todos categorizados: 6 batem uma keyword do dicionário, 1 (`XPTO ASSINATURA SERVICO ONLINE`) não bate nenhuma e vira **"Não classificado"** (o motor nunca chuta). |
| Saldo atual | R$ 6.721,10 | `LEDGERBAL` do OFX (não é soma dos lançamentos: é o saldo que o banco informou). |
| Títulos em aberto | 4 | 2 futuros (`NF-3001` a pagar 15/08, `NF-R700` a receber 20/08) + 2 vencidos ainda em aberto (`NF-3002`, `NF-R701`). O título `NF-2999` (já **pago**) e nenhum outro baixado **não** entram: invariante do motor, título baixado nunca aparece na projeção. |
| Alertas | 2× `ATRASADO_EM_ABERTO` | `NF-3002` (a pagar, venceu 10/07) e `NF-R701` (a receber, venceu 12/07): venceram antes da data-base e ainda não foram baixados no ERP. Entram na semana 0 da projeção, mas ficam marcados como atrasados. |
| Semana negativa | nenhuma | neste exemplo o saldo projetado fica sempre positivo (a maior saída, R$ 4.200 na semana 3, não derruba o saldo abaixo de zero). Com o seu dado real, uma semana negativa dispara o alerta `SEMANA_NEGATIVA`. |

Se o seu resultado bater com esta saída, a instalação está correta e você pode seguir com o
export do seu ERP e os extratos reais.
