# Resultado esperado da demo

Este é o resultado de conciliar o `extrato.ofx` contra o `razao.csv` deste exemplo
(Comércio Alfa, janeiro/2026), com **saldo final do razão = R$ 17.690,00**.

Use isto para conferir que a skill está rodando certo na sua máquina: rode a demo e
compare os números abaixo. (No terminal, nada sai do seu computador. No Claude Code em sessão local, a skill foi feita para o Claude ler só o resumo agregado, mas o seu pedido, esse resumo e qualquer arquivo que o Claude abrir vão para a Anthropic. No Cowork e no claude.ai, o arquivo sobe para a nuvem da Anthropic.)

## Comando

```
python scripts/conciliar.py conciliar --extrato exemplo/extrato.ofx --razao exemplo/razao.csv --saldo-razao 17690,00 --out resultado
```

## O que deve aparecer

**Status:**

| Status | Qtd |
|---|---|
| CONCILIADO | 7 |
| CONCILIADO_COM_DIFERENCA | 1 |
| PENDENTE_EXTRATO | 4 |
| PENDENTE_RAZAO | 3 |

**A "cauda" (pendências) explicada por categoria:**

| Categoria | Qtd | Ação |
|---|---|---|
| TARIFA_IOF | 2 | lançar no razão (despesa bancária) — a tarifa de pacote e o IOF |
| RENDIMENTO | 1 | lançar no razão (receita financeira) — o rendimento da aplicação |
| LIQUIDO_ADQUIRENTE | 1 | conciliar pelo líquido + linha de taxa — a venda no cartão caiu líquida (R$ 2.744 vs R$ 2.800 da venda) |
| CHEQUE_NAO_COMPENSADO | 1 | aguardar compensação — o cheque 5004 ainda não foi descontado |
| DEPOSITO_TRANSITO | 1 | aguardar crédito — o depósito do cliente Kappa ainda não caiu |
| EM_TRANSITO | 1 | aguardar / conferir — a venda bruta do cartão, esperando o líquido |

**Amarração (o checksum que prova que fechou):**

```
saldo_extrato_final        16629.30
saldo_razao_final          17690.00
ajuste_pendente_extrato     2699.35
ajuste_pendente_razao       3760.00
ajuste_diferenca            -0.05
saldo_extrato_esperado     16629.30
residuo                        0.00   <-- FECHA (integridade OK)
```

Se o `residuo` for **0,00**, a conciliação fechou e você pode confiar nos números.
Se não fechar, há erro de integridade a investigar — a skill avisa, não maquia.

## O que conferir no relatório local

O detalhe linha-a-linha fica em `resultado/conciliacao.xlsx` (ou `.csv` se você não
tiver o `openpyxl`), com a **categoria** e a **ação sugerida** de cada pendência.
Esse arquivo é seu, fica no seu computador. No Claude Code em sessão local, a skill foi feita
para o Claude ler só o `resumo.json` agregado, não os seus lançamentos.
