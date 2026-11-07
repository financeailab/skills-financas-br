# skills-financas-br

Ferramentas de IA grátis e abertas para a tesouraria brasileira, publicadas como skills para
Claude. Um repositório, uma ferramenta por vez: cada uma nasce testada, com o código aberto sob
Apache-2.0, e o nome do plugin não muda depois de publicado.

Mantido pelo [Finance AI Lab](https://financeailab.com.br), um hub brasileiro de IA aplicada a
Finanças Corporativas.

## Ferramentas abertas

| Ferramenta | O que faz | Plugin |
|---|---|---|
| Auditor de Tarifas | Soma as tarifas bancárias de um extrato (OFX/CSV) por banco, mês e tipo, com o IOF separado do que é tarifa de fato | [`plugins/auditor-de-tarifas`](plugins/auditor-de-tarifas/README.md) |

## Como instalar

Cada ferramenta tem um README próprio com o passo a passo por plataforma. Resumo:

- **Cowork** (plano pago): Customize › Plugins › Add marketplace, aponte para
  `financeailab/skills-financas-br`.
- **Claude Code**: `/plugin marketplace add financeailab/skills-financas-br`, depois
  `/plugin install <nome-da-ferramenta>@skills-financas-br`.
- **claude.ai** (sem Claude Code nem Cowork): baixe o `.zip` da ferramenta na
  [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill.
- **Terminal**: baixe o repositório e rode o script Python da ferramenta diretamente
  (os requisitos de cada ferramenta estão no README dela).

Detalhes, requisitos e limites de cada ferramenta estão no README do plugin dela, por exemplo o
do [Auditor de Tarifas](plugins/auditor-de-tarifas/README.md).

## Privacidade, por plataforma

- **Terminal**: o motor roda no seu computador e nada sai dele.
- **Claude Code, em sessão local**: o motor roda no seu computador e a skill foi feita para o Claude
  ler só o resumo que ele imprime; o seu pedido, esse resumo e qualquer arquivo que o Claude abrir
  vão para a Anthropic.
- **Cowork** (desde 06/10/2026, planos Pro, Max e Ultra): o trabalho roda na nuvem da Anthropic
  e o arquivo sobe para lá.
- **claude.ai (web ou app), com o `.zip` como skill**: o trabalho roda na nuvem da Anthropic e o
  arquivo que você anexa sobe para lá antes de o motor rodar, porque a conversa inteira roda lá. Isso vale para
  qualquer skill de claude.ai, não é específico desta ferramenta.

## Aviso

Rascunho operacional: a decisão e a revisão são do profissional responsável. Nenhuma ferramenta
aqui substitui o trabalho de quem concilia, audita ou fecha o resultado da empresa; o motor soma
e classifica, a decisão final é sua ou do profissional contábil/financeiro responsável.

## Reportar um problema ou pedir uma ferramenta

Abra uma [issue](https://github.com/financeailab/skills-financas-br/issues/new/choose). **Não anexe extrato nem dado real** (CNPJ, CPF,
agência, conta, nome de cliente, lançamento); se precisar ilustrar o problema, use um extrato
fictício.

## Licença

[Apache-2.0](LICENSE). Veja o [`NOTICE`](NOTICE).

## Autor

Douglas Ferreira ([LinkedIn](https://www.linkedin.com/in/douglasaf98)), Finance AI Lab
([financeailab.com.br](https://financeailab.com.br)).
