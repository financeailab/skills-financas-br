-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-09-03
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-09-03'),
    'V0057',
    'Remoção de alíquotas da monofasia.'
);

-- =======================================================================
-- Remoção de alíquotas da monofasia (ALIQUOTA_AD_REM 3 a 11).
-- As tabelas filhas são apagadas antes para não deixar registros órfãos.
-- =======================================================================

DELETE FROM EXCECAO_AD_REM_PRODUTO
WHERE EARP_AARP_ID IN (
    SELECT AARP_ID
    FROM   ALIQUOTA_AD_REM_PRODUTO
    WHERE  AARP_AARE_ID IN (3, 4, 5, 6, 7, 8, 9, 10, 11)
);

DELETE FROM EXCECAO_AD_REM_SERVICO
WHERE EARS_AARS_ID IN (
    SELECT AARS_ID
    FROM   ALIQUOTA_AD_REM_SERVICO
    WHERE  AARS_AARE_ID IN (3, 4, 5, 6, 7, 8, 9, 10, 11)
);

DELETE FROM ALIQUOTA_AD_REM_PRODUTO
WHERE AARP_AARE_ID IN (3, 4, 5, 6, 7, 8, 9, 10, 11);

DELETE FROM ALIQUOTA_AD_REM_SERVICO
WHERE AARS_AARE_ID IN (3, 4, 5, 6, 7, 8, 9, 10, 11);

DELETE FROM ALIQUOTA_AD_REM
WHERE AARE_ID IN (3, 4, 5, 6, 7, 8, 9, 10, 11);
