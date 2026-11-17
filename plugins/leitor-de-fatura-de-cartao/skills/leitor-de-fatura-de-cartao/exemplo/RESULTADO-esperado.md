# Resultado esperado do exemplo

Rode (a partir de `scripts/`, dentro da skill instalada):

```
python ler_fatura.py ../exemplo/fatura-01-itau-ok.pdf --saida resultado-01
python ler_fatura.py ../exemplo/fatura-02-bradesco-total-nao-fecha.pdf --saida resultado-02
python ler_fatura.py ../exemplo/fatura-03-generico-baixa-confianca.pdf --saida resultado-03
```

Todas as 3 faturas são **fictícias** (banco "BANCO EXEMPLO ITA"/"BANCO EXEMPLO BRA", nomes de
portador e estabelecimento inventados, nenhum dado real).

| Arquivo | Veredicto esperado | Por quê |
|---|---|---|
| `fatura-01-itau-ok.pdf` | 🟢 **OK** | 4 lançamentos + 2 encargos (IOF, anuidade) somam exatamente o total impresso na fatura. Prova de completude fecha. |
| `fatura-02-bradesco-total-nao-fecha.pdf` | 🔴 **TOTAL NAO FECHA** | fatura com 1 lançamento suprimido de propósito (falta 1 dos 4 originais). A soma dos lançamentos + encargos fica R$ 145,00 abaixo do total impresso: o motor avisa em vez de fingir que leu tudo. |
| `fatura-03-generico-baixa-confianca.pdf` | 🟡 **BAIXA CONFIANCA** | layout de um emissor "de fora" dos 2 reconhecidos (nem tipo-Itaú, nem tipo-Bradesco). O parser genérico lê `data + estabelecimento + valor` de 3 linhas soltas, mas sem um total impresso reconhecido não há gabarito pra provar completude. |

**Resultado esperado:** 1 OK, 1 TOTAL NAO FECHA, 1 BAIXA CONFIANCA.

Se o seu resultado bater com esta tabela, a instalação está correta e você pode seguir com a
fatura real do mês. Repare que o motor **nunca inventa** um lançamento nem finge que uma fatura
fechou quando não fechou: é assim que ele se comporta com a sua fatura real também.
