-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-28
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-28'),
    'V0053',
    'Ajustes nas alíquotas de IS, CBS e IBS, para excluir e ajustar vigências.'
);

-- ============================================================
-- Excluir vigências superiores a 31/12/2026 de CBS/IBS (2, 3 e 4)
-- ============================================================
-- EXCECAO_AD_VALOREM_PRODUTO — filha de ALIQUOTA_AD_VALOREM_PRODUTO → ALIQUOTA_AD_VALOREM  (0 registro(s))
DELETE FROM EXCECAO_AD_VALOREM_PRODUTO
WHERE  EAVP_AAVP_ID IN (
    SELECT p.AAVP_ID
    FROM   ALIQUOTA_AD_VALOREM_PRODUTO p
           INNER JOIN ALIQUOTA_AD_VALOREM a ON a.AADV_ID = p.AAVP_AADV_ID
    WHERE  a.AADV_TBTO_ID IN (2, 3, 4)
      AND  a.AADV_INICIO_VIGENCIA > '2026-12-31'
);

-- ALIQUOTA_AD_VALOREM_PRODUTO — filha de ALIQUOTA_AD_VALOREM  (0 registro(s))
DELETE FROM ALIQUOTA_AD_VALOREM_PRODUTO
WHERE  AAVP_AADV_ID IN (
    SELECT AADV_ID
    FROM   ALIQUOTA_AD_VALOREM
    WHERE  AADV_TBTO_ID IN (2, 3, 4)
      AND  AADV_INICIO_VIGENCIA > '2026-12-31'
);

-- ALIQUOTA_AD_VALOREM_SERVICO — filha de ALIQUOTA_AD_VALOREM  (0 registro(s))
DELETE FROM ALIQUOTA_AD_VALOREM_SERVICO
WHERE  AAVS_AADV_ID IN (
    SELECT AADV_ID
    FROM   ALIQUOTA_AD_VALOREM
    WHERE  AADV_TBTO_ID IN (2, 3, 4)
      AND  AADV_INICIO_VIGENCIA > '2026-12-31'
);

-- ALIQUOTA_AD_REM_PRODUTO — filha de ALIQUOTA_AD_REM  (0 registro(s))
DELETE FROM ALIQUOTA_AD_REM_PRODUTO
WHERE  AARP_AARE_ID IN (
    SELECT AARE_ID
    FROM   ALIQUOTA_AD_REM
    WHERE  AARE_TBTO_ID IN (2, 3, 4)
      AND  AARE_INICIO_VIGENCIA > '2026-12-31'
);

-- ALIQUOTA_AD_REM  (0 registro(s))
DELETE FROM ALIQUOTA_AD_REM
WHERE  AARE_TBTO_ID IN (2, 3, 4)
  AND  AARE_INICIO_VIGENCIA > '2026-12-31';

-- ALIQUOTA_AD_VALOREM  (6 registro(s))
DELETE FROM ALIQUOTA_AD_VALOREM
WHERE  AADV_TBTO_ID IN (2, 3, 4)
  AND  AADV_INICIO_VIGENCIA > '2026-12-31';

-- ALIQUOTA_REFERENCIA  (21 registro(s))
DELETE FROM ALIQUOTA_REFERENCIA
WHERE  ALRE_TBTO_ID IN (2, 3, 4)
  AND  ALRE_INICIO_VIGENCIA > '2026-12-31';

-- ============================================================
-- UPDATE: FIM_VIGENCIA = '2026-12-31'
-- Tabelas: ALIQUOTA_AD_REM, ALIQUOTA_AD_VALOREM, ALIQUOTA_REFERENCIA
-- Filtro: apenas registros com INICIO_VIGENCIA <= '2026-12-31' e de CBS/IBS
-- (registros com inicio > '2026-12-31' violam CHECK e são alvo do script de DELETE)
-- ============================================================
-- ALIQUOTA_AD_REM  (9 registro(s))
UPDATE ALIQUOTA_AD_REM
SET    AARE_FIM_VIGENCIA = '2026-12-31'
WHERE  AARE_INICIO_VIGENCIA <= '2026-12-31' and AARE_TBTO_ID IN (2,3,4);

-- ALIQUOTA_AD_VALOREM  (27 registro(s))
UPDATE ALIQUOTA_AD_VALOREM
SET    AADV_FIM_VIGENCIA = '2026-12-31'
WHERE  AADV_INICIO_VIGENCIA <= '2026-12-31' and AADV_TBTO_ID IN (2,3,4);

-- ALIQUOTA_REFERENCIA  (3 registro(s))
UPDATE ALIQUOTA_REFERENCIA
SET    ALRE_FIM_VIGENCIA = '2026-12-31'
WHERE  ALRE_INICIO_VIGENCIA <= '2026-12-31' and ALRE_TBTO_ID IN (2,3,4);

-- ============================================================
-- Ajuste no REDUTOR_COMPRA_GOVERNAMENTAL
-- ============================================================
DELETE FROM REDUTOR_COMPRA_GOVERNAMENTAL WHERE RCGO_ID = 1;
UPDATE REDUTOR_COMPRA_GOVERNAMENTAL SET RCGO_FIM_VIGENCIA = NULL WHERE RCGO_ID = 2;

-- ============================================================
-- Remoção da alíquota do IS pra concurso de prognóstico e do vinculo com o NBS
-- ============================================================
DELETE FROM ALIQUOTA_AD_VALOREM_SERVICO WHERE AAVS_ID=1;
DELETE FROM ALIQUOTA_AD_VALOREM WHERE AADV_ID=38;

-- ============================================================
-- Ajuste na SITUACAO_TRIBUTARIA
-- ============================================================
UPDATE SITUACAO_TRIBUTARIA SET SITR_DESCRICAO = 'Ajustes de IBS na ZFM' WHERE SITR_ID = 15;
UPDATE SITUACAO_TRIBUTARIA SET SITR_DESCRICAO = 'Ajustes' WHERE SITR_ID = 16;

