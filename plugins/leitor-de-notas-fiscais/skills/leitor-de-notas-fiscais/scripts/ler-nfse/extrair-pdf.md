# Prompt de extração — leitura de nota fiscal (PDF/imagem) → dict canônico

> Recurso da skill `ler-nfse`. Usado **só quando não há XML** (XML-first: se houver XML, parsear é determinístico e melhor).
> O Claude lê o documento (PDF vetorial, PDF escaneado ou imagem/foto) e emite o **dicionário de extração**
> que `engine/extracao.py` consome. A leitura é a única parte probabilística; o resto do motor é determinístico.

## Saída exigida (formato exato)

Um único objeto JSON. Para **cada campo que você conseguir ler**, uma entrada:

```json
{
  "classe": "nfse" | "nfe",
  "simples_nacional": {"valor": "true"},
  "cancelada": {"valor": "true"},
  "campos": {
    "<campo_canonico>": {"valor": "<texto>", "rotulo_exato": true|false}
  }
}
```

> `simples_nacional`, `cancelada` (e `tipo_documento`, quando aplicável) são **meta** e ficam **fora** de `campos` (não são `{valor, rotulo_exato}` de leitura, e sim um flag). Inclua `simples_nacional` só quando a nota for de optante; inclua `cancelada` só quando a nota tiver carimbo/marca de cancelamento (ver gotcha 21).

- `rotulo_exato: true` → o valor veio de um **rótulo direto e inequívoco** no documento (ex.: "Valor do Serviço: R$ 10.000,00").
- `rotulo_exato: false` → o valor foi **inferido** (cálculo, dedução, ou rótulo ambíguo). Sinaliza menor confiança.
- Campo **ausente ou ilegível** → **não inclua** a entrada (ou `"valor": null`). **Nunca invente.**

## Campos canônicos (e rótulos típicos no DANFSE/DANFE)

| Campo canônico | Rótulos comuns | Formato do `valor` |
|---|---|---|
| `chave_acesso` | "Chave de Acesso" (NFS-e=50 díg., NF-e=44 díg.) | só dígitos |
| `numero` | "Número da NFS-e" / "Nº" | texto |
| `serie` | "Série" | texto |
| `data_emissao` | "Data e Hora da emissão" | texto |
| `emitente_cnpj` | "Prestador / Emitente: CNPJ" | só dígitos |
| `emitente_nome` | "Nome / Razão Social" do prestador | texto |
| `emitente_endereco` | "Endereço" do Prestador / Emitente | texto (endereço completo) |
| `destinatario_endereco` | "Endereço" do Tomador / Destinatário | texto (endereço completo) |
| `intermediario_doc` | CNPJ do "Intermediário de Serviços" (quando houver) | só dígitos |
| `intermediario_nome` | Nome / Razão do Intermediário de Serviços | texto |
| `codigo_servico` | "Código de Tributação Nacional" / "Item LC 116" | texto |
| `discriminacao` | "Descrição do Serviço" | texto |
| `valor_servicos` | "Valor do Serviço" | decimal "10000.00" |
| `valor_recebido` | "Valor Total Recebido" / "Valor Líquido Recebido" | decimal (informativo, ver gotcha 10) |
| `iss_base` | "BC ISSQN" / "Base de Cálculo" | decimal |
| `iss_aliquota` | "Alíquota Aplicada" | decimal "5.00" (percentual) |
| `iss_valor` | **ver gotcha abaixo** | decimal |
| `iss_retido` | "Retenção do ISSQN" | **"true" / "false"** |
| `valor_liquido` | "Valor Líquido da NFS-e" | decimal |
| `ret_irrf` | "IRRF" | decimal |
| `ret_csll` | "Contribuições Sociais - Retidas" / "CSLL" | decimal |
| `ret_pis` | "PIS - Retido" | decimal |
| `ret_cofins` | "COFINS - Retido" | decimal |
| `ret_inss` | "Contribuição Previdenciária - Retida" / "INSS" | decimal |
| `ret_inss_base` | "Base de Cálculo INSS" / "BC INSS" | decimal |
| `ret_inss_aliquota` | "Alíquota INSS" | decimal "11.00" (percentual) |
| `iss_tipo_retencao` | "Retenção do ISSQN" / "Retido pelo Tomador/Intermediário" | **"nao_retido" / "retido_tomador" / "retido_intermediario"** |
| `iss_municipio_incidencia` | "Município de Incidência do ISS" / "Local da Prestação" | código IBGE (7 díg.) |
| `ret_federal_total` | "Total Tributos Federais" / "Total das Retenções Federais" | decimal |
| `vencimento` | "Vencimento" na discriminação (NFS-e) / bloco **Fatura/Duplicata** (NF-e) | ISO `AAAA-MM-DD` |
| `simples_nacional` | "Optante do Simples Nacional" / "Reg. Especial Tributação ME EPP" | **"true"** (só quando optante; senão omita) |
| `cancelada` (meta) | carimbo/marca **"CANCELADA" / "NOTA FISCAL CANCELADA" / "CANCELAMENTO"** na nota | **"true"** (só com carimbo; senão omita; ver gotcha 21) |
| **NF-e:** `natureza_operacao` | "Natureza da Operação" (ex.: "VENDA", "DEVOLUCAO DE MERCADORIA", "REMESSA") | texto |
| **NF-e:** `total_produtos` | "Valor Total dos Produtos" | decimal |
| **NF-e:** `total_nota` | "Valor Total da Nota" | decimal |
| **NF-e:** `frete` / `seguro` / `outras_despesas` | "Valor do Frete" / "Valor do Seguro" / "Outras Despesas Acessórias" (bloco Cálculo do Imposto) | decimal (só as que aparecem) |
| **NF-e:** `desconto` | "Desconto" (bloco Cálculo do Imposto) | decimal |
| **NF-e:** `ipi_total` | "Valor Total do IPI" | decimal |
| **NF-e:** `icmsst_total` | "Valor do ICMS Substituição" (ICMS-ST). **Não** é o "Valor do ICMS" comum | decimal |
| **NF-e:** `vencimento` | bloco **Fatura/Duplicata** (ex.: "008664 02/04/2026 61.783,32") | ISO `AAAA-MM-DD` |

**Aliases de leitura por município** (o mesmo campo canônico tem rótulos variados): `valor_servicos` ← "Valor dos Serviços" / "Valor Total do Serviço"; `iss_base` ← "Base de Cálculo" / "Base de Cálculo ISS"; `iss_aliquota` ← "Alíquota (%)" / "Alíquota ISS (%)"; `valor_liquido` ← "Valor Líquido" / "Valor Líquido da NFS-e"; `codigo_servico` ← "Código do Serviço" / "Serviço Prestado". Retenções: "IRRF"/"IR" → `ret_irrf`; "PIS/PASEP"/"PIS" → `ret_pis`; "Outras Retenções" → some na retenção federal.

**Decimais:** sempre `"1000.00"` (ponto decimal, sem `R$`, sem separador de milhar). `"10.000,0000"` → `"10000.00"`.

## Gotchas (aprendidos no spike, §19/§20 do spec) — leia com atenção

1. **ISS retido = "ISSQN Apurado: 0".** Quando o ISS é **retido pelo tomador**, o DANFSE mostra `ISSQN Apurado: R$ 0,00` (o que o *prestador* paga = zero). **Esse 0 NÃO é o `iss_valor` canônico.** O ISS real = `iss_base × iss_aliquota`. Nesse caso: emita `iss_valor` = base×alíquota e marque **`rotulo_exato: false`** (inferido). E `iss_retido: "true"`.
2. **`iss_retido` canônico.** Emita sempre `"true"` ou `"false"`. "Retido pelo Tomador"/"Retido pelo Intermediário" → `"true"`. "Não Retido" → `"false"`. (Não emita "1"/"2" — o código varia por leiaute.)
2b. **`iss_tipo_retencao`.** Quando o DANFSE indicar "Retido pelo Tomador" → `"retido_tomador"`; "Retido pelo Intermediário" → `"retido_intermediario"`; "Não Retido"/ausente → `"nao_retido"`. Esse campo é mais rico que `iss_retido` (que continua "true"/"false").
3. **Chave de 50/44 dígitos.** É o campo mais frágil em foto/scan de baixa qualidade. Se a chave impressa estiver ilegível, **leia o QR code** do DANFSE. Se nem o QR, deixe `chave_acesso` ausente (o motor tem fallback por nome de arquivo).
4. **Degradação graciosa.** Documento torto, com sombra, recorte parcial ou baixíssima qualidade: leia o que der, deixe o resto ausente. **Não invente** para "completar".
5. **Só lê nota fiscal (NFS-e / NF-e).** Este leitor processa **apenas** NFS-e de serviço e NF-e de produto. Se o documento for **outra coisa** (nota de débito, recibo, fatura, boleto, invoice internacional, contrato/proposta): retorne `{"fora_do_escopo": true}` e **pare** — não emita `campos`, não invente. Avise a pessoa que esse documento fica fora do leitor de notas.
6. **Multi-página / vários docs.** Se houver mais de uma nota no arquivo, processe uma por vez (peça orientação se ambíguo).
7. **Vencimento que a nota já traz.** Muitas NFS-e escrevem "Vencimento: DD/MM/AAAA" dentro da **discriminação do serviço**; a NF-e traz no bloco **Fatura/Duplicata** (ex.: linha "008664 02/04/2026 61.783,32" → vence 02/04/2026). Extraia para `vencimento` em **ISO `AAAA-MM-DD`** (`30/05/2026` → `"2026-05-30"`). Se não houver, **deixe ausente** (o motor marca "a preencher", não inventa).
9. **Simples Nacional (ISS no DAS, não destacado).** Quando a nota disser "Optante do Simples Nacional" / "Documento emitido por ME ou EPP optante pelo SIMPLES NACIONAL" / "Reg. Especial Tributação ME EPP": emita `simples_nacional: {"valor": "true"}`. Nesses casos o **ISS costuma vir mascarado (`*****`) ou ausente** porque é recolhido no DAS → **não invente `iss_valor`**, deixe ausente. O motor entende que é Simples e **não penaliza** a nota por isso (ao contrário da nota normal sem ISS, que é suspeita).
10. **Valor oficial vence o texto livre — mas extraia OS DOIS quando divergirem.** O **valor fiscal** do serviço ("Valor Total do Serviço" / "Valor dos Serviços" / "Valor Total da Nota") vai em `valor_servicos`/`total_nota` e é o que a carga usa. O "Valor Total Recebido" / "Valor Líquido Recebido" é **informativo** e vai em `valor_recebido` (campo separado). Ex. real (SP): o documento tinha "VALOR TOTAL RECEBIDO = R$ 14.943,31" mas o valor fiscal da nota era R$ 4.483,00 → emita `valor_servicos: "4483.00"` **E** `valor_recebido: "14943.31"`. Nunca jogue o recebido no campo fiscal: o recebido pode ser um total de contrato/lote, não o da nota.
11. **NF-e (DANFE).** `total_produtos` ← "Valor Total dos Produtos"; `total_nota` ← "Valor Total da Nota"; `vencimento` ← bloco **Fatura/Duplicata**. Itens (NCM/CFOP) ficam em "DADOS DO PRODUTO/SERVIÇO" e entram só como agregado (sinal), nunca como grão de linha.

## Gotchas — traps das 18 notas reais (Reforma, IBPT, normalização)

12. **IBS/CBS (Reforma Tributária).** Já aparecem em NFS-e nacional (ex.: DF) e em DANFE: têm **base e município de incidência PRÓPRIOS** (o município do IBS pode **diferir** do município do ISS). **NÃO** são retenção — não jogue em `ret_*`. **NÃO** confunda o "Valor Total - IBS/CBS" com o valor do serviço nem com o ISS. Se conseguir ler, vão em `ibs_valor` / `cbs_valor` (opcionais); na dúvida, **ignore sem inventar**.
13. **IBPT / "Valor Aproximado dos Tributos" (Lei 12.741).** Em texto livre ("Carga Tributária Aproximada R$ X", "Trib. aprox. R$ Y", "Fonte: IBPT") é **estimativa, NÃO retenção** — nunca entra em `ret_*` nem como valor de nota.
14. **Vencimento mora em vários lugares.** Campo "Vencimento:", texto livre na discriminação ("Pagamento desta nota para DD/MM/AAAA") e nas NF-e o bloco **FATURA / DUPLICATA / PARCELAS** (Número / Vencimento / Valor). Procure nos **três**. Se houver **múltiplas parcelas**, use a **1ª** (e anote na `discriminacao` que há mais).
15. **`*N` (um asterisco) é nota de rodapé, NÃO máscara.** Ex.: `*2,79%`, `*24,83` são valores **reais** (limpe o `*` → `2.79`, `24.83`). Só `*****` (vários asteriscos) é campo **oculto** → ausente. `-` isolado = campo **vazio** → ausente (não emita `0,00`).
16. **Normalização.** CFOP = 4 dígitos sem ponto (`6.125` → `6125`); NCM = 8 dígitos sem ponto; **chave de acesso** = só dígitos, sem espaços/pontos (44 NF-e / 50 NFS-e nacional); **número da nota** = só dígitos, sem zeros à esquerda e sem milhar (`000.043.189` → `43189`); chave NFS-e às vezes vem com **prefixo textual** (`NFS...`) → guarde só os dígitos.
17. **"TOTAL DE ITENS: N" numa DANFE costuma ser a SOMA das quantidades, NÃO a contagem de linhas.** Conte os itens (`qtd_itens`) pelas **linhas de produto**.
18. **NF-e: o total é a soma que o motor confere.** `total_nota` = "VALOR TOTAL DA NOTA". O motor confere `total_produtos + frete + seguro + outras_despesas − desconto + ipi_total + icmsst_total = total_nota`: extraia cada parcela que a nota trouxer (a que não aparece fica ausente, vale zero). **IPI e ICMS-ST entram no total**: sem eles o total parece não fechar e a nota cai para conferir à toa. O ICMS **comum** ("Valor do ICMS", base de cálculo) já está no preço dos produtos: é informativo, **não** extraia.
19. **Simples Nacional (reforço).** "Optante do Simples", "ME/EPP", "PGDAS", "ISS a reter: Não", "para simples conferência" → `simples_nacional: {"valor":"true"}`. O ISS é **informativo** (pode vir `0`, pode vir calculado, pode vir `-`) → o motor **não o valida**.
20. **GTIN/EAN ≠ NCM.** O nome do destinatário pode variar (acento, "DO/DE") — **confie no CNPJ**, não no nome. "RS" no documento pode ser OCR de "R$".
21. **CANCELADA = carimbo na nota, não nome de arquivo.** Se a nota trouxer **carimbo, faixa, marca d'água ou selo** dizendo "CANCELADA" / "NOTA FISCAL CANCELADA" / "CANCELAMENTO" (visível por cima do documento), emita a meta `cancelada: {"valor": "true"}` (fora de `campos`). Senão, **omita** (não emita `false`). ⚠️ **Nunca** infira cancelamento do **nome do arquivo ou da pasta** — só do que está **impresso na nota**. O motor não calcula líquido nem inverte valor: a nota cancelada apenas cai para **conferir** com o motivo "Nota CANCELADA: nao pagar / nao lancar".
22. **`natureza_operacao` (NF-e) é SINAL de sentido, não inversão.** Capture o texto de "Natureza da Operação" (ex.: "VENDA", "DEVOLUCAO DE MERCADORIA", "REMESSA EM CONSIGNACAO") em `natureza_operacao`. Se for devolução/retorno/remessa, o motor **sinaliza para conferir** (o valor pode ser crédito, não débito) — mas **não inverte o valor nem rebaixa o score**. Só capture o texto como está; quem decide o sentido é a analista.

## Por que sinalizar em vez de chutar

O motor determinístico (invariantes) **confere** o que você leu: se `iss_valor ≠ base × alíquota`, ou se o líquido não fecha, o campo cai para **BAIXA** e a analista confere **só aquela célula**. Logo, um valor inferido honestamente (`rotulo_exato: false`) é muito melhor que um palpite disfarçado de certeza — a confiança 0–1 e as bandas dependem disso.
