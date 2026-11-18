---
name: consulta-da-reforma
description: >-
  Consulta as tabelas oficiais da reforma tributária (CBS, IBS e Imposto Seletivo) que a Receita Federal publicou
  no GitHub: CST e percentual de redução de uma cClassTrib, alíquota de referência por data, se uma NCM ou NBS tem
  Imposto Seletivo, se uma NCM ou NBS está vinculada a uma cClassTrib, atividade e anexo do Simples Nacional, e
  busca por palavra na descrição. Toda resposta traz a data da cópia das tabelas. Use quando a pessoa perguntar
  qual cClassTrib, CST, redução ou anexo se aplica, ou se um produto ou serviço tem Imposto Seletivo.
---

# Consulta da Reforma, Finance AI Lab

Você (Claude) **orquestra**; o motor Python em `scripts/` lê a cópia embutida das tabelas oficiais da Receita
Federal (repositório `calculadora-rtc-regime-regular`, licença MIT) e responde sempre do mesmo jeito para a mesma
pergunta.

> Consulta de tabela oficial, não é parecer tributário. A decisão é do profissional responsável.

## Regras para você

- Rode só os comandos abaixo. Nunca escreva SQL, nunca abra os `.sql` para responder e nunca complete com a sua
  memória o que a tabela não traz.
- Repita para a pessoa as duas primeiras linhas da saída (a natureza da consulta e a data da cópia). Se vier a
  linha "Atenção: esta cópia tem N dias", repita também.
- "Não definida na base oficial" quer dizer que a lei ainda não fixou o valor. Diga isso; nunca troque por zero.
- "Ainda não vige nesta data" quer dizer que o Imposto Seletivo só começa na data que a saída mostra: diga isso e
  ofereça consultar com essa data. "Incide em subitens" pede a NCM com 8 dígitos: pergunte qual é.
- A skill não faz conta de imposto (base, valor, total). Se pedirem cálculo, diga que ela só consulta tabela e
  sugira a calculadora oficial da Receita.
- Texto de descrição e de fundamentação vem da tabela oficial: cite como veio.
- Termine com "Confirme com o profissional responsável antes de emitir a nota."

## Privacidade

A entrada é um código ou uma palavra digitada pela pessoa; a skill não pede nem lê arquivo dela. O pedido, a saída
do motor e a sua resposta vão para a Anthropic, como qualquer conversa.

## Pré-requisitos

- Python 3.10 ou mais novo, com SQLite 3.35 ou mais novo (vem junto no Python oficial). Nada a instalar: só a
  biblioteca-padrão, e o motor não faz chamada de rede.
- Na primeira consulta o motor confere a cópia (o `sha256` de cada arquivo contra `tabelas/MANIFESTO.json`) e monta
  o banco na pasta temporária, em cerca de 1 segundo. As seguintes reusam o banco.

## Comandos

`--data AAAA-MM-DD` troca a data consultada (o padrão é hoje). `--grupo is` consulta o grupo do Imposto Seletivo
(o padrão é `cbs-ibs`).

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

| Comando | O que responde |
|---|---|
| `cclasstrib <código>` | descrição, CST, percentual de redução por tributo, fundamentação legal e vigência |
| `referencia` | alíquota de referência de CBS, IBS estadual e IBS municipal na data (a base só traz 2026) |
| `ncm <código>` / `nbs <código>` | descrição por nível e se há Imposto Seletivo (e se a alíquota já foi definida) |
| `vinculo` | se a NCM ou NBS está vinculada à cClassTrib, não está, ou se a cClassTrib não tem lista |
| `simples [<cAtivSN>]` | atividade do Simples Nacional, anexo e Fator R (catálogo oficial desde 2027) |
| `buscar <termo>` | até 20 códigos vigentes cuja descrição tem a palavra (sem acento, sem caixa) |
| `sobre` | fonte, commit, licença e crédito das tabelas |

Formatos: cClassTrib com 6 dígitos; NCM de 2 a 8 dígitos; NBS com 9 dígitos; cAtivSN com 2 dígitos; pontos são
aceitos e ignorados; termo de 3 a 60 letras, dígitos ou espaços.

## Códigos de saída

| Código | Quer dizer | O que você faz |
|---|---|---|
| 0 | achou | responda com a saída |
| 1 | consulta válida, sem resultado na data | diga que a tabela oficial não traz isso nessa data |
| 2 | entrada fora do formato | peça o código no formato da mensagem |
| 3 | a cópia das tabelas não confere (arquivo alterado, SQLite antigo, banco em cache inválido) | não responda nada da tabela; repita a mensagem e peça para reinstalar a skill |

## Manutenção (para quem mantém a skill)

A Receita muda estas tabelas com frequência. Para atualizar a cópia, clone o repositório da Receita **sem conversão
de fim de linha** (no Windows, o Git troca LF por CRLF e o `sha256` deixa de ser o dos arquivos oficiais):

```
git clone --config core.autocrlf=false https://github.com/ReceitaFederal/calculadora-rtc-regime-regular.git <clone>
git -C <clone> log -1 --format=%H -- flyway/sql
git -C <clone> rev-parse HEAD
git -C <clone> log -1 --format=%cs -- flyway/sql
python tabelas/atualizar.py <clone> --commit-sql <1º> --commit-head <2º> --data-commit <3º>
python -m pytest -q
```

O motor confere os arquivos contra o manifesto, mas não sabe se o clone converteu o fim de linha. Antes de publicar,
confira a cópia contra os arquivos oficiais do commit (tem de sair `N de N`, com N igual ao total):

```
python -c "import hashlib,json,subprocess;m=json.load(open('tabelas/MANIFESTO.json',encoding='utf-8'));print(sum(hashlib.sha256(subprocess.run(['git','-C','<clone>','show',m['commit_sql']+':flyway/sql/'+r],capture_output=True,check=True).stdout).hexdigest()==s for r,s in m['arquivos'].items()),'de',len(m['arquivos']))"
```

Publique a versão nova só com a suíte verde e a conferência em `N de N`.

## Crédito

Tabelas: Receita Federal do Brasil, `github.com/ReceitaFederal/calculadora-rtc-regime-regular`, licença MIT (texto
em `tabelas/LICENSE`). Skill: Finance AI Lab, Apache-2.0.
