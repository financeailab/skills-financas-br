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
    'V0047',
    'Tipo de Receita Bruta do Simples Nacional (tpRBSN) na tabela de Classificações Tributárias.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Inclusão da coluna CLTR_TPRBSN na tabela CLASSIFICACAO_TRIBUTARIA e carga (planilha
--    cClassTrib 2026-06-22, aba "cClass 2026-06-01 Pub", coluna tpRBSN - 164 códigos),
--    RESTRITA às classificações do tributo CBS (TBTO_ID = 2)
--
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

ALTER TABLE CLASSIFICACAO_TRIBUTARIA
    ADD COLUMN CLTR_TPRBSN INTEGER NOT NULL DEFAULT 0
        CHECK (CLTR_TPRBSN IN (0, 1, 2, 3, 4, 5, 9));

-- tpRBSN = 0 - Não é receita bruta (34 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 0
 WHERE CLTR_CD IN (
    '200019','410001','410002','410003','410017','410022','410026','410029',
    '410030','410032','410036','410037','410999','550002','550003','550006',
    '550007','550008','550009','550010','550019','550020','620007','800001',
    '800002','810001','811001','811002','811003','820005','820006','820008',
    '820009','830001'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 1 - Receita bruta - interna (81 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 1
 WHERE CLTR_CD IN (
    '000001','000002','000003','000004','000005','010002','011001','011002',
    '011003','011004','011005','200002','200003','200004','200005','200006',
    '200007','200008','200009','200010','200011','200012','200013','200014',
    '200015','200020','200021','200022','200023','200024','200025','200027',
    '200028','200029','200030','200031','200032','200033','200034','200035',
    '200036','200037','200038','200039','200040','200041','200042','200043',
    '200044','200045','200046','200047','200048','200049','200050','200051',
    '200052','200053','220003','221001','221004','400001','400002','410014',
    '410016','410019','410020','410024','410031','515001','550011','550012',
    '550013','550015','550016','550017','550018','550022','550023','550024',
    '550025'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 2 - Receita bruta - interna sem cálculo de IBS e CBS (6 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 2
 WHERE CLTR_CD IN (
    '410008','410009','410010','410011','510001','620006'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 3 - Receita bruta - exportação direta (4 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 3
 WHERE CLTR_CD IN (
    '200001','410004','410013','410027'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 4 - Receita bruta - exportação indireta (5 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 4
 WHERE CLTR_CD IN (
    '550001','550004','550005','550014','550021'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 5 - Receita bruta - mercado interno e exportação 50/50 (1 código)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 5
 WHERE CLTR_CD IN (
    '222001'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- tpRBSN = 9 - Fornecimento incompatível com SN (33 códigos)

UPDATE CLASSIFICACAO_TRIBUTARIA
   SET CLTR_TPRBSN = 9
 WHERE CLTR_CD IN (
    '010001','200016','200017','200018','200026','200054','220001','220002',
    '221002','221003','410005','410006','410007','410012','410015','410018',
    '410021','410023','410025','410028','410033','410034','410035','620001',
    '620002','620003','620004','620005','820001','820002','820003','820004',
    '820007'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CLASSIFICACAO_TRIBUTARIA.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

