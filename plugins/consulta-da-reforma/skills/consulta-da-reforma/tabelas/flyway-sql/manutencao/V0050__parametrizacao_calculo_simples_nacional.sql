-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-07
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-07'),
    'V0050',
    'Parametrização do cálculo do Simples Nacional (NT 2026.005): coluna tpRBSN na classificação tributária (restrita ao tributo CBS), tipos de receita bruta, whitelist de documentos habilitados (NF-e, NFC-e e NFS-e), matriz de regime de apuração, transição de alíquotas de compra governamental e associativa atividade × documento (whitelist: atividade admissível somente nos documentos vinculados por NT publicada).'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Inclusão da coluna CLTR_TPRBSN na tabela CLASSIFICACAO_TRIBUTARIA e carga (planilha
--    cClassTrib 2026-06-22, aba "cClass 2026-06-01 Pub", coluna tpRBSN - 164 códigos),
--    RESTRITA às classificações do tributo CBS (TBTO_ID = 2)
-- 2. Criação e carga da tabela TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL (efeito de cada tpRBSN
--    no cálculo, com descrição para a saída da API)
-- 3. Criação e carga da tabela TIPO_DFE_CALCULO_SIMPLES_NACIONAL (whitelist global de tipos
--    de documento fiscal habilitados para o cálculo do Simples Nacional)
-- 4. Criação e carga da tabela REGIME_APURACAO_SIMPLES_NACIONAL (matriz de regime:
--    quais campos são gerados e o destino dos valores calculados)
-- 5. Criação e carga da tabela TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL (fator de
--    deslocamento de alíquotas CBS->IBS em compras governamentais)
-- 6. Criação e carga da tabela TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL (associativa de
--    admissibilidade de atividade por documento — whitelist)
--
-- Todas as tabelas das seções 2 a 6 são EXCLUSIVAS do cálculo do Simples Nacional: não
-- possuem vínculo com as tabelas de parâmetro do regime geral (TRATAMENTO_TRIBUTARIO,
-- TRANSFERENCIA_CBS_ENTE_GOV, REDUTOR_COMPRA_GOVERNAMENTAL), que permanecem proibidas
-- para o cálculo do Simples. Com elas, o comportamento do cálculo é parametrizado em
-- banco: mudanças futuras (novo documento habilitado, novo tipo de receita bruta, mudança
-- de efeito ou de cronograma, novo vínculo atividade × documento) são feitas apenas por
-- scripts de migração, sem alterar Java, sempre resolvidas pela vigência da data do fato
-- gerador.
-- -----------------------------------------------------------------------------------------------

-- ==========================================================================================
-- 1. Inclusão da coluna CLTR_TPRBSN na tabela CLASSIFICACAO_TRIBUTARIA e carga
--    (restrita ao tributo CBS)
-- ==========================================================================================
--
-- Tipo de Receita Bruta do Simples Nacional (tpRBSN) do cClassTrib, conforme NT 2026.005:
--   0 = Não é receita bruta
--   1 = Receita bruta - interna
--   2 = Receita bruta - interna sem cálculo de IBS e CBS
--   3 = Receita bruta - exportação direta
--   4 = Receita bruta - exportação indireta
--   5 = Receita bruta - mercado interno e exportação (50/50)
--   9 = Fornecimento incompatível com SN
--
-- IMPORTANTE - CLTR_CD NÃO É ÚNICO: a tabela CLASSIFICACAO_TRIBUTARIA contém DOIS grupos
-- de classificações, um do Imposto Seletivo (TBTO_ID = 1) e outro da CBS (TBTO_ID = 2),
-- com códigos que podem colidir entre os grupos. O tpRBSN pertence exclusivamente à
-- tabela cClassTrib do IBS/CBS; por isso, TODOS os UPDATEs abaixo restringem o alvo via
-- EXISTS em TRIBUTO_SITUACAO_TRIBUTARIA com TRST_TBTO_ID = 2 (CBS).
-- As classificações do Imposto Seletivo permanecem no DEFAULT 0, que para elas é inerte
-- (o cálculo do Simples nunca resolve tpRBSN a partir do grupo do IS).
--
-- O DEFAULT 0 existe também para viabilizar o ALTER no SQLite; a carga abaixo cobre os
-- 164 cClassTrib publicados. Códigos futuros DEVEM ser carregados com o tpRBSN correto.

-- tpRBSN = 0 - Não é receita bruta (34 códigos)

-- VERIFICAÇÃO (executar manualmente após a migração; deve retornar vazio - nenhuma
-- classificação de CBS vigente pode permanecer no DEFAULT sem constar da lista de
-- tpRBSN = 0 da planilha):
--
-- SELECT CLTR_CD, CLTR_DESCRICAO
--   FROM CLASSIFICACAO_TRIBUTARIA CT
--  WHERE CT.CLTR_TPRBSN = 0
--    AND CT.CLTR_FIM_VIGENCIA IS NULL
--    AND EXISTS (SELECT 1 FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
--                 WHERE TST.TRST_SITR_ID = CT.CLTR_SITR_ID AND TST.TRST_TBTO_ID = 2)
--    AND CT.CLTR_CD NOT IN (
--        '200019','410001','410002','410003','410017','410022','410026','410029',
--        '410030','410032','410036','410037','410999','550002','550003','550006',
--        '550007','550008','550009','550010','550019','550020','620007','800001',
--        '800002','810001','811001','811002','811003','820005','820006','820008',
--        '820009','830001'
--    );

-- ==========================================================================================
-- 2. Criação e carga da tabela TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL
-- ==========================================================================================
--
-- Materializa a tabela de efeitos do tpRBSN da NT 2026.005 (seções 5.3.2 e 5.3.4).
-- Cada linha descreve como um Tipo de Receita Bruta do Simples Nacional afeta o cálculo:
--
--   TRBS_CD: código do tpRBSN (mesmo domínio da coluna CLTR_TPRBSN);
--   TRBS_DESCRICAO: texto oficial do leiaute do evento (campo P27 da NT), exposto na
--     saída da API (campo tpRBSNDescricao);
--   TRBS_IN_COMPOE_RECEITA: 0 = a receita bruta do item é zero (vRBSNitem = 0);
--     1 = a receita bruta do item é computada (baseCalculo, somada ao vIS apenas quando
--     TRBS_IN_IS_COMPOE_RECEITA = 1 — ver abaixo);
--   TRBS_IN_IS_COMPOE_RECEITA: 1 = o valor do Imposto Seletivo (vIS) integra a receita
--     bruta computada; 0 = a receita bruta é apenas a baseCalculo. CARGA ATUAL: 0 em
--     TODAS as linhas/vigências — por decisão de negócio, o vIS NÃO compõe a RBSNitem em
--     nenhuma vigência. Trata-se de DIVERGÊNCIA DELIBERADA com a fórmula do campo P26 da
--     NT 2026.005 (RBSNitem = vProd + vFrete + vSeg + vOutro + vIS - vDesc), que soma o
--     vIS incondicionalmente. A coluna existe como alavanca de PARAMETRIZAÇÃO POR
--     VIGÊNCIA: se a regra legal mudar, a mudança é um script de vigência nesta tabela
--     (encerrar vigência + inserir linhas novas), resolvida pela DATA DO FATO GERADOR,
--     sem alteração de código Java. Inerte quando TRBS_IN_COMPOE_RECEITA = 0. O DEFAULT 0
--     não tem semântica de negócio — a carga é sempre explícita (padrão destes scripts);
--   TRBS_FATOR_RECEITA: fração da receita bruta tributada (1.0 = integral; 0.5 = metade,
--     caso "mercado interno e exportação"; 0.0 = nada é tributado);
--   TRBS_IN_PENDENTE_SUSPENSO: 1 = o valor calculado fica pendente/suspenso em vez de
--     devido (caso da exportação indireta, que aguarda a efetivação da exportação);
--   TRBS_IN_EXIGE_ALIQUOTA: 1 = as alíquotas efetivas (pIBSSN/pCBSSN) são exigidas
--     quando o cálculo as usa (item com cAtivSN válido e regime que gera o tributo);
--   TRBS_IN_VEDADO_NAO_TRIBUTAVEL: 1 = incompatível com código de atividade de operações
--     não tributáveis (regra UB14-90 da NT 2026.005, msg 1277) - vale para os tpRBSN 1 a 5,
--     que declaram receita bruta de operação tributável, imune ou de exportação. O mesmo
--     indicador alimenta o filtro por cClassTrib do endpoint de atividades, que marca as
--     atividades não tributáveis como indisponíveis para esses tpRBSN — prevenção na
--     origem do erro que o cálculo devolveria (VSN-023).
--
-- Não há chave estrangeira formal entre CLTR_TPRBSN e TRBS_CD: o SQLite exige alvo com
-- restrição de unicidade e TRBS_CD admite versionamento por vigência. A coerência é
-- garantida pelos CHECKs de domínio dos dois lados e por teste automatizado de carga.
--
-- Código de tpRBSN presente na classificação tributária mas SEM linha vigente nesta tabela
-- na data do fato gerador resulta em erro de item VSN-026 (falha de parametrização; o
-- cálculo nunca assume efeito implícito).

CREATE TABLE TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL (
    TRBS_ID INTEGER NOT NULL,
    TRBS_CD INTEGER NOT NULL CHECK (TRBS_CD IN (0, 1, 2, 3, 4, 5, 9)),
    TRBS_DESCRICAO TEXT NOT NULL,
    TRBS_IN_COMPOE_RECEITA INTEGER NOT NULL CHECK (TRBS_IN_COMPOE_RECEITA IN (0, 1)),
    TRBS_IN_IS_COMPOE_RECEITA INTEGER NOT NULL DEFAULT 0 CHECK (TRBS_IN_IS_COMPOE_RECEITA IN (0, 1)),
    TRBS_FATOR_RECEITA REAL NOT NULL CHECK (TRBS_FATOR_RECEITA >= 0 AND TRBS_FATOR_RECEITA <= 1),
    TRBS_IN_PENDENTE_SUSPENSO INTEGER NOT NULL CHECK (TRBS_IN_PENDENTE_SUSPENSO IN (0, 1)),
    TRBS_IN_EXIGE_ALIQUOTA INTEGER NOT NULL CHECK (TRBS_IN_EXIGE_ALIQUOTA IN (0, 1)),
    TRBS_IN_VEDADO_NAO_TRIBUTAVEL INTEGER NOT NULL CHECK (TRBS_IN_VEDADO_NAO_TRIBUTAVEL IN (0, 1)),
    TRBS_INICIO_VIGENCIA TEXT NOT NULL,
    TRBS_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("TRBS_FIM_VIGENCIA" IS NULL OR "TRBS_FIM_VIGENCIA" >= "TRBS_INICIO_VIGENCIA"),
    PRIMARY KEY (TRBS_ID)
);

-- Carga EXPLÍCITA (padrão destes scripts), inclusive do isCompoeReceita = 0 em todas as
-- linhas (o vIS fora da RBSNitem em toda vigência — ver o comentário da coluna acima).
--                                                             (id, cd, descricao, compoeReceita, isCompoeReceita, fatorReceita, pendenteSuspenso, exigeAliquota, vedadoNaoTributavel, vigencias)
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (1, 0, 'Não é receita bruta',                               0, 0, 0.0, 0, 0, 0, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (2, 1, 'Receita bruta - interna',                           1, 0, 1.0, 0, 1, 1, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (3, 2, 'Receita bruta - interna sem cálculo de IBS e CBS',  1, 0, 0.0, 0, 0, 1, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (4, 3, 'Receita bruta - exportação direta',                 1, 0, 0.0, 0, 0, 1, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (5, 4, 'Receita bruta - exportação indireta',               1, 0, 1.0, 1, 1, 1, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (6, 5, 'Receita bruta - mercado interno e exportação',      1, 0, 0.5, 0, 1, 1, '2027-01-01', NULL);
INSERT INTO TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL VALUES (7, 9, 'Fornecimento incompatível com SN',                  1, 0, 0.0, 0, 0, 0, '2027-01-01', NULL);

-- ==========================================================================================
-- 3. Criação e carga da tabela TIPO_DFE_CALCULO_SIMPLES_NACIONAL
-- ==========================================================================================
--
-- Whitelist GLOBAL de tipos de documento fiscal eletrônico habilitados para o cálculo do
-- Simples Nacional: tpDoc sem vínculo vigente nesta tabela é rejeitado com HTTP 422
-- (erro VSN-015) antes de qualquer item ser processado.
--
-- Esta whitelist é uma camada DISTINTA da associativa por atividade (seção 6):
-- aqui decide-se se a OPERAÇÃO inteira pode ser calculada; lá decide-se, por item, se o
-- código de atividade é admissível no documento.
--
-- Carga: exatamente os documentos com nota técnica publicada — NF-e/NFC-e (NT 2026.005)
-- e NFS-e (NT do padrão nacional da NFS-e). Habilitar um novo documento, quando a NT
-- correspondente for publicada, é um único INSERT com a vigência da NT, sem alteração de
-- código Java.
-- Referências de TPDF_ID (conforme carga da V0042): 2 = NF-e (tpDoc 55), 3 = NFC-e
-- (tpDoc 65), 10 = NFS-e (tpDoc 91).

CREATE TABLE TIPO_DFE_CALCULO_SIMPLES_NACIONAL (
    TDCS_ID INTEGER NOT NULL,
    TDCS_TPDF_ID INTEGER NOT NULL,
    TDCS_INICIO_VIGENCIA TEXT NOT NULL,
    TDCS_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("TDCS_FIM_VIGENCIA" IS NULL OR "TDCS_FIM_VIGENCIA" >= "TDCS_INICIO_VIGENCIA"),
    PRIMARY KEY (TDCS_ID),
    FOREIGN KEY (TDCS_TPDF_ID) REFERENCES TIPO_DFE(TPDF_ID)
);

INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (1, 2,  '2027-01-01', NULL); -- NF-e  (tpDoc 55)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (2, 3,  '2027-01-01', NULL); -- NFC-e (tpDoc 65)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (3, 10, '2027-01-01', NULL); -- NFS-e (tpDoc 91)

-- ==========================================================================================
-- 4. Criação e carga da tabela REGIME_APURACAO_SIMPLES_NACIONAL
-- ==========================================================================================
--
-- Matriz de regime do cálculo (fórmulas P28 a P33 da NT 2026.005): para cada combinação
-- de CRT e tpRegimeIBSCBS que CALCULA, define quais campos são gerados e o destino dos
-- valores calculados.
--
--   RASN_CRT / RASN_TPREGIMEIBSCBS: a combinação (tpRegimeIBSCBS nulo = regime informado
--     sem essa tag). As combinações que NÃO calculam (MEI, regime regular, regime normal
--     puro, incoerências) são rejeitadas ANTES desta tabela, pela validação de escopo do
--     serviço (HTTP 422 com códigos VSN próprios por combinação);
--   RASN_IN_GERA_IBS: 0 = o bloco de IBS (pIBSSN, vIBSSN, vIBSPendSusp) é suprimido da
--     saída. Caso do CRT=2 (excesso de sublimite): o IBS desse contribuinte é declarado
--     pelo próprio emitente no gIBSCBS da nota, fora do evento do Simples;
--   RASN_DESTINO_DEVIDO: para onde vai o valor que o tpRBSN qualificou como devido -
--     'DEVIDO' (campos vIBSSN/vCBSSN) ou 'PENDENTE_SUSPENSO' (campos vIBSPendSusp/
--     vCBSPendSusp);
--   RASN_DESTINO_PENDENTE_SUSPENSO: para onde vai o valor que o tpRBSN qualificou como
--     pendente/suspenso (exportação indireta) - 'PENDENTE_SUSPENSO' ou 'ZERO' (o valor é
--     descartado).
--
-- ATENÇÃO à linha do CRT=3 + tpRegimeIBSCBS=2: o destino 'ZERO' para o valor já suspenso
-- reproduz LITERALMENTE as fórmulas P32/P33 da NT (exportação indireta nesse regime cai
-- em "outro valor" e resulta em tudo zero). É contraintuitivo e INTENCIONAL - não
-- "corrigir" sem nova NT.
--
-- Combinação aprovada pela validação de escopo mas SEM linha vigente aqui resulta em
-- HTTP 422 com erro VSN-026 (falha de parametrização).

CREATE TABLE REGIME_APURACAO_SIMPLES_NACIONAL (
    RASN_ID INTEGER NOT NULL,
    RASN_CRT INTEGER NOT NULL,
    RASN_TPREGIMEIBSCBS INTEGER,
    RASN_DESCRICAO TEXT NOT NULL,
    RASN_IN_GERA_IBS INTEGER NOT NULL CHECK (RASN_IN_GERA_IBS IN (0, 1)),
    RASN_DESTINO_DEVIDO TEXT NOT NULL CHECK (RASN_DESTINO_DEVIDO IN ('DEVIDO', 'PENDENTE_SUSPENSO')),
    RASN_DESTINO_PENDENTE_SUSPENSO TEXT NOT NULL CHECK (RASN_DESTINO_PENDENTE_SUSPENSO IN ('PENDENTE_SUSPENSO', 'ZERO')),
    RASN_INICIO_VIGENCIA TEXT NOT NULL,
    RASN_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("RASN_FIM_VIGENCIA" IS NULL OR "RASN_FIM_VIGENCIA" >= "RASN_INICIO_VIGENCIA"),
    PRIMARY KEY (RASN_ID)
);

INSERT INTO REGIME_APURACAO_SIMPLES_NACIONAL VALUES
(1, 1, NULL, 'Simples Nacional', 1, 'DEVIDO', 'PENDENTE_SUSPENSO', '2027-01-01', NULL);

INSERT INTO REGIME_APURACAO_SIMPLES_NACIONAL VALUES
(2, 2, NULL, 'Simples Nacional - excesso de sublimite de receita bruta (IBS declarado pelo emitente no gIBSCBS, fora do evento)', 0, 'DEVIDO', 'PENDENTE_SUSPENSO', '2027-01-01', NULL);

INSERT INTO REGIME_APURACAO_SIMPLES_NACIONAL VALUES
(3, 3, 2, 'Regime Normal com opção pelo Simples Nacional pendente (valores integralmente pendentes/suspensos; exportação indireta resulta em tudo zero - literal nas fórmulas P32/P33 da NT)', 1, 'PENDENTE_SUSPENSO', 'ZERO', '2027-01-01', NULL);

-- ==========================================================================================
-- 5. Criação e carga da tabela TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL
-- ==========================================================================================
--
-- Fator de deslocamento de alíquotas CBS->IBS em compras governamentais de ente estadual,
-- distrital ou municipal (tpEnteGov = 2, 3 ou 4), conforme NT 2026.005, seção 5.3.3, e
-- arts. 372 e 473 da LC 214/2025. Fórmulas aplicadas pelo cálculo:
--
--   pIBS' = pIBS + fator × pCBS
--   pCBS' = (1 - fator) × pCBS
--
--   TACG_FATOR é FRAÇÃO (0.10, e não 10).
--
-- O caso União (tpEnteGov = 1) NÃO está nesta tabela: é regra estrutural e atemporal do
-- art. 372 da LC 214/2025 (pCBS' = pCBS + pIBS; pIBS' = 0), sem parâmetro temporal, e a
-- fórmula desloca no sentido oposto (IBS->CBS); permanece implementada no serviço de
-- cálculo.
--
-- A primeira vigência começa em 2027-01-01 (fator zero) para cobrir o período de
-- implantação da NT; a transição efetiva ocorre de 2029 a 2033. Data do fato gerador
-- SEM vigência correspondente (anterior a 2027-01-01) resulta em erro de item VSN-025
-- (falha de parametrização; o cálculo nunca assume fator zero implícito).
--
-- As vigências devem ser CONTÍGUAS e SEM SOBREPOSIÇÃO (exatamente uma linha vigente para
-- toda data >= 2027-01-01) - propriedade garantida por teste automatizado.
--
-- Tabela EXCLUSIVA do Simples Nacional: não confundir com TRANSFERENCIA_CBS_ENTE_GOV e
-- REDUTOR_COMPRA_GOVERNAMENTAL, que parametrizam a mecânica do regime geral.

CREATE TABLE TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL (
    TACG_ID INTEGER NOT NULL,
    TACG_FATOR REAL NOT NULL CHECK (TACG_FATOR >= 0 AND TACG_FATOR <= 1),
    TACG_INICIO_VIGENCIA TEXT NOT NULL,
    TACG_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("TACG_FIM_VIGENCIA" IS NULL OR "TACG_FIM_VIGENCIA" >= "TACG_INICIO_VIGENCIA"),
    PRIMARY KEY (TACG_ID)
);

INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (1, 0.00, '2027-01-01', '2028-12-31');
INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (2, 0.10, '2029-01-01', '2029-12-31');
INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (3, 0.20, '2030-01-01', '2030-12-31');
INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (4, 0.30, '2031-01-01', '2031-12-31');
INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (5, 0.40, '2032-01-01', '2032-12-31');
INSERT INTO TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL VALUES (6, 1.00, '2033-01-01', NULL);

-- ==========================================================================================
-- 6. Criação e carga da tabela TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL (whitelist por atividade)
-- ==========================================================================================
--
-- SEMÂNTICA (whitelist — mundo fechado): uma atividade é admissível em um documento SE E
-- SOMENTE SE existe vínculo vigente (na data do fato gerador) entre a atividade e o tipo
-- de documento nesta tabela. Atividade SEM vínculo vigente algum NÃO é admissível em
-- documento nenhum.
--
-- RACIONAL: a admissibilidade é um fato afirmativo publicado por nota técnica; ausência
-- de publicação significa ausência de permissão. A whitelist falha para o lado seguro
-- (esquecer uma carga torna a atividade indisponível — erro visível e corrigível com um
-- INSERT — em vez de admissível em tudo — erro silencioso), cada INSERT é monotônico
-- (só adiciona permissão) e cada vínculo carrega naturalmente a vigência da NT que o
-- publicou.
--
-- EFEITOS: no cálculo, item com atividade sem vínculo para o tpDoc da operação resulta em
-- NAO_CALCULADO (sem erro — NT 2026.005, §5.3.4, Observação 2); no endpoint de atividades,
-- a atividade aparece com admissivelNoDocumento = false para o documento (e
-- tpDocsAdmissiveis lista apenas os vínculos vigentes — vazia quando não há nenhum).
--
-- CARGA (vínculos publicados pelas NTs de NF-e/NFC-e e NFS-e):
--   - atividades 01, 02, 03, 04 e 90: NF-e (55) e NFC-e (65);
--   - atividades 07, 08, 09, 10, 11, 12, 13, 14 e 90: NFS-e (91);
--   - atividades 05 e 06: NENHUM vínculo — constam do catálogo (códigos oficiais), mas
--     não são admissíveis em documento algum até que uma NT (CT-e, NFCom etc.) as
--     publique;
--   - o 90 é admissível em NF-e, NFC-e E NFS-e.
--
-- Todos os vínculos são explícitos, por TIPO_DFE individual (sem atalho via GRUPO_DFE).
-- Referências de chaves (cargas da V0042/V0044): TIPO_DFE 2 = NF-e (55), 3 = NFC-e (65),
-- 10 = NFS-e (91); ATIVIDADE_SIMPLES_NACIONAL 1..14 = códigos '01'..'14', 15 = código '90'.

CREATE TABLE TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL (
    TDAS_ID INTEGER NOT NULL,
    TDAS_ATSN_ID INTEGER NOT NULL,
    TDAS_TPDF_ID INTEGER NOT NULL,
    TDAS_INICIO_VIGENCIA TEXT NOT NULL,
    TDAS_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("TDAS_FIM_VIGENCIA" IS NULL OR "TDAS_FIM_VIGENCIA" >= "TDAS_INICIO_VIGENCIA"),
    PRIMARY KEY (TDAS_ID),
    FOREIGN KEY (TDAS_ATSN_ID) REFERENCES ATIVIDADE_SIMPLES_NACIONAL(ATSN_ID),
    FOREIGN KEY (TDAS_TPDF_ID) REFERENCES TIPO_DFE(TPDF_ID)
);

-- NF-e (55) e NFC-e (65): atividades 01-04 e 90.

INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (1,  1,  2,  '2027-01-01', NULL); -- atividade 01 x NF-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (2,  1,  3,  '2027-01-01', NULL); -- atividade 01 x NFC-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (3,  2,  2,  '2027-01-01', NULL); -- atividade 02 x NF-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (4,  2,  3,  '2027-01-01', NULL); -- atividade 02 x NFC-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (5,  3,  2,  '2027-01-01', NULL); -- atividade 03 x NF-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (6,  3,  3,  '2027-01-01', NULL); -- atividade 03 x NFC-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (7,  4,  2,  '2027-01-01', NULL); -- atividade 04 x NF-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (8,  4,  3,  '2027-01-01', NULL); -- atividade 04 x NFC-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (9,  15, 2,  '2027-01-01', NULL); -- código 90 x NF-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (10, 15, 3,  '2027-01-01', NULL); -- código 90 x NFC-e

-- NFS-e (91): atividades 07-14 e 90.

INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (11, 7,  10, '2027-01-01', NULL); -- atividade 07 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (12, 8,  10, '2027-01-01', NULL); -- atividade 08 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (13, 9,  10, '2027-01-01', NULL); -- atividade 09 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (14, 10, 10, '2027-01-01', NULL); -- atividade 10 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (15, 11, 10, '2027-01-01', NULL); -- atividade 11 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (16, 12, 10, '2027-01-01', NULL); -- atividade 12 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (17, 13, 10, '2027-01-01', NULL); -- atividade 13 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (18, 14, 10, '2027-01-01', NULL); -- atividade 14 x NFS-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (19, 15, 10, '2027-01-01', NULL); -- código 90 x NFS-e

-- Atividades 05 e 06: sem vínculo — não admissíveis em documento algum até publicação da
-- NT do documento correspondente (transporte intermunicipal/interestadual e comunicação:
-- CT-e, NFCom etc.).
