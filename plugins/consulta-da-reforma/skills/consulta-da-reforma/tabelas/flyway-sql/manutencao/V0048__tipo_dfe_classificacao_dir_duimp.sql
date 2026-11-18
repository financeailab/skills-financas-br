-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-25
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-25'),
    'V0048',
    'Relações entre os tipos de DFE DIR e Duimp e as Classificações Tributárias da CBS; correção das relações de NFAg e NFGas com os cClassTribs 410005 e 000002.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Inclusão das relações do tipo de DFE DIR (TPDF_ID = 17) na tabela TIPO_DFE_CLASSIFICACAO
--    (planilha cClassTrib 2026-06-22, aba "cClass 2026-06-01 Pub", coluna indDIR - 8 códigos)
-- 2. Inclusão das relações do tipo de DFE Duimp (TPDF_ID = 18) na tabela TIPO_DFE_CLASSIFICACAO
--    (planilha cClassTrib 2026-06-22, aba "cClass 2026-06-01 Pub", coluna indDUIMP - 58 códigos)
-- 3. Correção de relações divergentes da planilha: inclusão de NFAg (TPDF_ID = 14) para o
--    cClassTrib 410005 e exclusão da relação indevida de NFGas (TPDF_ID = 15) com o
--    cClassTrib 000002
--
-- Todas as cargas são RESTRITAS às classificações do tributo CBS (TBTO_ID = 2).
-- -----------------------------------------------------------------------------------------------

-- IMPORTANTE - CLTR_CD NÃO É ÚNICO: a tabela CLASSIFICACAO_TRIBUTARIA contém DOIS grupos
-- de classificações, um do Imposto Seletivo (TBTO_ID = 1) e outro da CBS (TBTO_ID = 2),
-- com códigos que podem colidir entre os grupos. As colunas indDIR e indDUIMP pertencem
-- exclusivamente à tabela cClassTrib do IBS/CBS; por isso, os INSERTs abaixo restringem
-- o alvo via EXISTS em TRIBUTO_SITUACAO_TRIBUTARIA com TRST_TBTO_ID = 2 (CBS).
--
-- Os TDCL_IDs são gerados sequencialmente a partir do maior TDCL_ID existente (359 nas
-- bases pro e nonpro): DIR ocupa 360-367 e Duimp ocupa 368-425.

-- ==========================================================================================
-- 1. Relações do DIR (TPDF_ID = 17) com as classificações tributárias da CBS (8 códigos)
-- ==========================================================================================

INSERT INTO TIPO_DFE_CLASSIFICACAO (TDCL_ID, TDCL_CLTR_ID, TDCL_TPDF_ID, TDCL_INICIO_VIGENCIA, TDCL_FIM_VIGENCIA)
SELECT (SELECT MAX(TDCL_ID) FROM TIPO_DFE_CLASSIFICACAO) + ROW_NUMBER() OVER (ORDER BY CT.CLTR_CD),
       CT.CLTR_ID,
       17,
       '2026-01-01',
       NULL
  FROM CLASSIFICACAO_TRIBUTARIA CT
 WHERE CT.CLTR_CD IN (
    '000001','200009','200012','200032','200033','200053','410008','410009'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CT.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- ===========================================================================================
-- 2. Relações do Duimp (TPDF_ID = 18) com as classificações tributárias da CBS (58 códigos)
-- ===========================================================================================

INSERT INTO TIPO_DFE_CLASSIFICACAO (TDCL_ID, TDCL_CLTR_ID, TDCL_TPDF_ID, TDCL_INICIO_VIGENCIA, TDCL_FIM_VIGENCIA)
SELECT (SELECT MAX(TDCL_ID) FROM TIPO_DFE_CLASSIFICACAO) + ROW_NUMBER() OVER (ORDER BY CT.CLTR_CD),
       CT.CLTR_ID,
       18,
       '2026-01-01',
       NULL
  FROM CLASSIFICACAO_TRIBUTARIA CT
 WHERE CT.CLTR_CD IN (
    '000001','200002','200003','200004','200005','200006','200007','200008',
    '200009','200010','200011','200012','200013','200014','200030','200031',
    '200032','200033','200034','200035','200036','200038','200039','200043',
    '200053','410001','410003','410008','410009','410037','410999','510001',
    '515001','550002','550003','550004','550006','550007','550008','550009',
    '550010','550011','550013','550014','550015','550016','550017','550018',
    '550019','550020','550021','550022','550023','550024','550025','620001',
    '620002','620003'
 )
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CT.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- ===========================================================================================
-- 3. Correção de relações divergentes da planilha cClassTrib 2026-06-22
--    (aba "cClass 2026-06-01 Pub", colunas indNFAg e indNFGas)
-- ===========================================================================================

-- 3.1. O cClassTrib 410005 (CBS) possui indNFAg = 1 na planilha, mas a relação com o tipo de
--      DFE NFAg (TPDF_ID = 14) não havia sido carregada. Inclusão da relação faltante.

INSERT INTO TIPO_DFE_CLASSIFICACAO (TDCL_ID, TDCL_CLTR_ID, TDCL_TPDF_ID, TDCL_INICIO_VIGENCIA, TDCL_FIM_VIGENCIA)
SELECT (SELECT MAX(TDCL_ID) FROM TIPO_DFE_CLASSIFICACAO) + 1,
       CT.CLTR_ID,
       14,
       '2026-01-01',
       NULL
  FROM CLASSIFICACAO_TRIBUTARIA CT
 WHERE CT.CLTR_CD = '410005'
   AND EXISTS (
       SELECT 1
         FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
        WHERE TST.TRST_SITR_ID = CT.CLTR_SITR_ID
          AND TST.TRST_TBTO_ID = 2
   );

-- 3.2. O cClassTrib 000002 (CBS) possui indNFGas = 0 na planilha (apenas indNFSe Via = 1),
--      mas havia sido carregada uma relação indevida com o tipo de DFE NFGas (TPDF_ID = 15).
--      Exclusão da relação indevida.

DELETE FROM TIPO_DFE_CLASSIFICACAO
 WHERE TDCL_TPDF_ID = 15
   AND TDCL_CLTR_ID IN (
       SELECT CT.CLTR_ID
         FROM CLASSIFICACAO_TRIBUTARIA CT
        WHERE CT.CLTR_CD = '000002'
          AND EXISTS (
              SELECT 1
                FROM TRIBUTO_SITUACAO_TRIBUTARIA TST
               WHERE TST.TRST_SITR_ID = CT.CLTR_SITR_ID
                 AND TST.TRST_TBTO_ID = 2
          )
   );
