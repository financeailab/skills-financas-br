# Passo de setup — referência do tomador (uma vez por lote)

Antes de processar o lote, a skill pergunta ao operador (via checkpoint/AskUserQuestion):

> "Para conferir a retenção de ISS corretamente, qual é o **CNPJ** e o **município** da sua empresa (o tomador)?"

Campos coletados → `TomadorReferencia(cnpj, municipio_ibge)`:
- **CNPJ** (só dígitos ou formatado; o motor normaliza).
- **Município**: nome → o operador confirma; a skill resolve para o **código IBGE de 7 dígitos** (ex.: São Paulo = 3550308). Se o operador não souber o código, a skill pode sugerir pelo nome do município/UF.

Esse contexto é passado a `engine.batch.processar_lote(arquivos, perfil, tomador_ref=...)`. Sem ele, o produto ainda roda (retenção em modo best-effort, sem endereçamento nem alerta §2).

**Por que pedir:** quem decide se a SUA empresa retém o ISS é o cruzamento entre o município de incidência da nota e o seu município. Sem isso, o produto não consegue (a) confirmar a retenção sem chutar, (b) avisar quando a nota veio endereçada a outro CNPJ, (c) alertar quando há obrigação de reter que o fornecedor não destacou (LC116 §2).
