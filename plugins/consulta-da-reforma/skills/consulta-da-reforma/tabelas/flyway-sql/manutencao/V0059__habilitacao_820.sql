-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-09-30
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-09-30'),
    'V0059',
    'Habilitação de 820 para NFSe.'
);

-- ============================================================
-- Habilitação de 820 para NFSe
-- ============================================================

UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=0
WHERE TRTR_ID=32;