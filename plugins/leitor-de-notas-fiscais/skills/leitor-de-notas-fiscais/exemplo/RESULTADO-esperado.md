# Resultado esperado do exemplo

Estas 4 notas sao ficticias (autoria propria, dados inventados), uma por familia de XML
que a skill le. Sao a demo do primeiro uso: rode-as antes do seu dado real para conferir
que o motor roda certo na sua maquina.

## Como rodar

```
python scripts/ler_notas.py processar --entrada exemplo --perfil generico --out resultado-exemplo
```

## O que o resumo deve mostrar

```json
{
  "total": 4,
  "auto_aprovadas": 4,
  "conferir": 0,
  "falhou": 0,
  "recebidas": 4,
  "fora_do_limite": 0,
  "repetidas": 0,
  "por_familia": {
    "nfe": 1,
    "nfse_abrasf": 1,
    "nfse_nacional": 1,
    "nfse_sp": 1
  }
}
```

- **total: 4** (uma nota por familia: nacional, ABRASF, SP, NF-e de produto).
- **auto_aprovadas: 4** (todas com confianca alta = 1,0; XML com invariante fiscal batendo).
- **conferir: 0** e **falhou: 0** (nenhuma exceção neste exemplo).

## As 4 notas

| Arquivo | Familia | Fornecedor (ficticio) | Valor | ISS |
|---|---|---|---|---|
| `nfse-nacional.xml` | nfse_nacional | Estudio Criativo Exemplo LTDA | 2.000,00 | 100,00 |
| `nfse-abrasf.xml` | nfse_abrasf | Oficina Digital Exemplo ME | 1.500,00 | 75,00 |
| `nfse-sp.xml` | nfse_sp | Consultoria Aurora Exemplo LTDA | 800,00 | 40,00 |
| `nfe-produto.xml` | nfe | Distribuidora Norte Exemplo LTDA | 3.300,00 | (nao se aplica) |

## Arquivos gerados

- `resultado-exemplo/carga.csv` — as 4 linhas no layout do perfil escolhido (4 linhas de dados + cabeçalho).
- `resultado-exemplo/resumo.json` — o resumo acima.
- `resultado-exemplo/excecoes.csv` — neste exemplo nao e gerado (zero notas para conferir).

> Se voce rodar com `--perfil omie`, a carga sai no layout de contas a pagar do Omie
> (Razao Social; CNPJ/CPF; Numero Documento; Data de Vencimento; Valor; Categoria; Conta
> Corrente; Observacao), tambem com 4 linhas de dados.

---

## O caminho PDF (NFS-e escaneada)

O exemplo acima cobre o caminho **XML** (o motor le a nota no disco). Quando a nota chega em PDF/imagem, o
Claude **le o documento** e produz um "dicionario de extracao". O `extracoes-exemplo.json`
ja traz um desses (uma NFS-e escaneada), para voce ver o caminho sem precisar de um PDF na mao:

```
python scripts/ler_notas.py processar-pdf --extracoes exemplo/extracoes-exemplo.json --perfil generico --out resultado-pdf
```

Resumo esperado: **total 1**, **1 conferir** (a NFS-e escaneada cai em "conferir" porque o
ISS foi **inferido** na leitura — o caso classico do "ISSQN Apurado 0"). `por_tipo`: `nfse: 1`.

Para testar a leitura de um arquivo de verdade, ha **`nota-servico.pdf`** (PDF vetorial) e
**`nota-foto.png`** (a mesma nota como "foto" de celular): diga ao Claude "le essa nota" e
aponte o arquivo. Ele extrai e gera a carga.

> **Fora do escopo:** boleto, recibo, nota de debito, fatura e invoice internacional **nao**
> sao processados (sao rejeitados com aviso). Este leitor le **so nota fiscal (NFS-e / NF-e)**.
