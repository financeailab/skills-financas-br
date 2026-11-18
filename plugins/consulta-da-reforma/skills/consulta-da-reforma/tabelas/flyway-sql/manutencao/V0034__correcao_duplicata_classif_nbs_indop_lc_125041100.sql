-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-05-26
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-05-26'),
    'V0034',
    'Correção de linha duplicada na CLASSIF_NBS_INDOP_LC para NBS 1.2504.11.00.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- A NBS 1.2504.11.00 (código 125041100) possui duas linhas na tabela CLASSIF_NBS_INDOP_LC
-- para a combinação LSLC_CD='38.01' e IOIC_CD='030101', ambas com CNIL_CLTR_ID=50 (cClassTrib
-- 200039). A migração V0025 incorretamente atualizou a linha de ID 1731 de CNIL_CLTR_ID=1
-- (cClassTrib 000001) para CNIL_CLTR_ID=50. Este script reverte essa linha para o valor correto.
-- -----------------------------------------------------------------------------------------------

UPDATE CLASSIF_NBS_INDOP_LC SET CNIL_CLTR_ID = 1 WHERE CNIL_ID = 1731;
