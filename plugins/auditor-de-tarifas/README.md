# Auditor de Tarifas

Responde "quanto seu banco te cobrou de tarifa esse ano?". Você entrega o extrato do ano (OFX
ou CSV, um por conta) e o motor Python soma as tarifas (manutenção, TED/DOC, Pix PJ, boleto,
custódia, câmbio) por banco, mês e tipo, com o **IOF separado** (imposto, não tarifa). O número
do ano é o argumento para renegociar a cesta PJ com o gerente ou para avaliar a portabilidade.

> Rascunho operacional: a decisão e a revisão são do profissional responsável.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `auditor-de-tarifas`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install auditor-de-tarifas@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `auditor-de-tarifas.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. **Aqui o arquivo anexado e os scripts rodam na nuvem da Anthropic**, não no seu computador. |
| **Terminal** | `python scripts/auditar_tarifas.py extrato.ofx --ano 2025` (de dentro de `skills/auditor-de-tarifas/`). |

Requisitos: Python 3.12 ou mais. Sem dependência externa (só a biblioteca padrão).

Para testar sem dado seu, use o extrato fictício em
[`skills/auditor-de-tarifas/exemplo/extrato_341.ofx`](skills/auditor-de-tarifas/exemplo/extrato_341.ofx).

## Como usar

```
python scripts/auditar_tarifas.py <extrato.ofx> [<extrato2.csv> ...] [--ano 2025] [--saida auditoria.csv]
```

- `--ano` filtra um ano-calendário (o total anual é o número que importa).
- `--saida` grava um CSV local só com as linhas que ele classificou como tarifa ou IOF (data, descrição, valor, banco e tipo), para conferir linha a linha. Ele não vai para a tela.
- A tela traz só o resumo: total anual de tarifa, tabela por banco, por mês e por tipo, o IOF à
  parte, o veredicto e quantos lançamentos ficaram para conferir.

## Privacidade

- **Terminal**: o motor lê o extrato no seu computador e nada sai dele.
- **Claude Code, em sessão local**: basta dar o caminho do extrato, sem colar nem anexar o conteúdo.
  O motor lê o arquivo no disco e o Claude lê só o que ele imprime: o resumo agregado, com o banco
  pelo rótulo que está no arquivo (o BANKID do OFX ou a coluna `banco` do CSV), e avisos de linha
  ilegível que dizem só o arquivo e o número da linha, nunca o conteúdo dela. O seu pedido, esse
  resumo e qualquer arquivo que você mandar o Claude abrir vão para a Anthropic.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra) e **claude.ai** (web ou app): o trabalho
  roda na nuvem da Anthropic e o extrato sobe para lá. Nesse caso, anonimize o extrato ou rode
  no terminal ou no Claude Code em sessão local.

## Limites

- Soma **só tarifa**. Não é categorizador de fluxo de caixa: não classifica o resto do extrato,
  não concilia, não compara bancos (audita o que já te cobraram). Juros de cheque especial e de
  antecipação não são tratados como tarifa.
- Tarifa PJ é livre e negociável. Um total alto **não** é cobrança indevida: é argumento de
  renegociação da cesta, ou de portabilidade. Não é caso de PF nem de restituição.
- Entrada OFX ou CSV. Extrato só em **PDF** fica fora deste motor.
- Quando aparece lançamento com cara de tarifa que o dicionário não reconhece, o veredicto vira
  `CONFERIR` e ele mostra a pendência em vez de esconder. Se o extrato não tem termo de tarifa
  reconhecível, ele diz `SEM TARIFA ENCONTRADA`: nunca inventa um número.
- Somar tarifa é algo que uma planilha faz, desde que você tenha o dicionário de termos certo.
  Esta ferramenta traz o dicionário pronto e a soma determinística, não mágica.

## Testes

```
pip install pytest
pytest -q plugins/auditor-de-tarifas/tests
```

## Licença

[Apache-2.0](../../LICENSE).
