# Consulta da Reforma

Skill que consulta as tabelas oficiais da reforma tributária (CBS, IBS e Imposto Seletivo) que a Receita Federal
publicou no GitHub, no repositório
[`ReceitaFederal/calculadora-rtc-regime-regular`](https://github.com/ReceitaFederal/calculadora-rtc-regime-regular)
(licença MIT). A cópia das tabelas vem embutida, byte a byte, e toda resposta diz de quando ela é.

> Consulta de tabela oficial, não é parecer tributário. A decisão é do profissional responsável.

## Cópia das tabelas

| | |
|---|---|
| **Origem** | `flyway/sql` do repositório da Receita, commit `8c538c9b` de 22/10/2026 |
| **Data da cópia** | 18/11/2026 |
| **Conferência** | `sha256` de cada um dos 61 arquivos em `skills/consulta-da-reforma/tabelas/MANIFESTO.json`; a skill recusa cópia alterada |
| **Licença** | MIT, da Receita Federal (`skills/consulta-da-reforma/tabelas/LICENSE` e [`NOTICE`](../../NOTICE)) |

Acima de 60 dias de cópia, a resposta avisa que a tabela pode estar velha. Uma versão nova da skill traz a cópia nova.

## Como instalar

| Plataforma | Passo a passo |
|---|---|
| **Cowork** (plano pago) | Customize › Plugins › Add marketplace, informe `financeailab/skills-financas-br` e instale o `consulta-da-reforma`. |
| **Claude Code** | `/plugin marketplace add financeailab/skills-financas-br`, depois `/plugin install consulta-da-reforma@skills-financas-br`. |
| **claude.ai** (web ou app) | Baixe o `consulta-da-reforma.zip` da [última release](https://github.com/financeailab/skills-financas-br/releases/latest) e suba em Customize › Skills › Upload custom skill. Aqui os scripts rodam na nuvem da Anthropic. |
| **Terminal** | `python scripts/consultar.py cclasstrib 200028` (de dentro de `skills/consulta-da-reforma/`). |

No Windows, alguns nomes de arquivo das tabelas oficiais são longos: se a instalação pelo marketplace falhar com
"Filename too long", rode `git config --global core.longpaths true` e instale de novo.

## Requisitos

Python 3.10 ou mais novo, com SQLite 3.35 ou mais novo (vem junto no Python oficial). Nada a instalar: só a
biblioteca-padrão.

## Como usar

Pergunte ao Claude, por exemplo: "qual a redução da cClassTrib 200028?", "a NCM 2203.00.00 tem Imposto
Seletivo?", "qual a alíquota de referência em junho de 2026?". No terminal:

```
python scripts/consultar.py cclasstrib 200028 --data 2027-03-10
python scripts/consultar.py referencia --data 2026-06-01
python scripts/consultar.py ncm 2203.00.00
python scripts/consultar.py nbs 1.2201.12.00
python scripts/consultar.py vinculo --ncm 02071100 --cclasstrib 200003 --data 2026-06-01
python scripts/consultar.py simples 09 --data 2027-01-01
python scripts/consultar.py buscar "educacao" --em cclasstrib
python scripts/consultar.py sobre
```

Os comandos, os formatos aceitos e os códigos de saída estão no [`SKILL.md`](skills/consulta-da-reforma/SKILL.md).

## Privacidade

A skill não pede nem lê arquivo seu: a entrada é um código ou uma palavra digitada, e o motor não faz chamada de
rede. Numa conversa com o Claude, o pedido, a saída do motor e a resposta vão para a Anthropic, como qualquer
conversa.

## Limites

- Não calcula imposto (base, valor, total): isso é da calculadora oficial da Receita.
- Não é parecer tributário: o enquadramento do caso é decisão do profissional responsável.
- A base oficial só traz a alíquota de referência de 2026, e as alíquotas do Imposto Seletivo ainda não foram
  fixadas: a resposta diz "não definida na base oficial", nunca zero.
- A cópia envelhece quando a Receita publica tabela nova.

## Atualizar a cópia

Clone o repositório da Receita **sem conversão de fim de linha** (`git clone --config core.autocrlf=false ...`) e
rode `python skills/consulta-da-reforma/tabelas/atualizar.py <clone> --commit-sql <sha> --commit-head <sha>
--data-commit AAAA-MM-DD`; depois, a suíte. Os passos completos estão no `SKILL.md`.

## Testes

Da raiz do repositório:

```
cd plugins/consulta-da-reforma
python -m pip install pytest
python -m pytest -q tests
```

## Licença

Código: [Apache-2.0](../../LICENSE). Tabelas em `skills/consulta-da-reforma/tabelas/flyway-sql/`: MIT, da Receita
Federal ([`NOTICE`](../../NOTICE)).
