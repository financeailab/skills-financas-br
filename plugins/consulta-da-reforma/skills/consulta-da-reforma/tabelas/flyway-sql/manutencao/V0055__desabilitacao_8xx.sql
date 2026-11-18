-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-09-01
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-09-01'),
    'V0055',
    'Desabilitação de 8xx para implementação futura.'
);

-- ============================================================
-- Desabilitação de 8xx para implementação futura
-- ============================================================

UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=1
WHERE TRTR_ID=29;
UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=1
WHERE TRTR_ID=30;
UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=1
WHERE TRTR_ID=31;
UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=1
WHERE TRTR_ID=32;
UPDATE TRATAMENTO_TRIBUTARIO
SET TRTR_IN_POSSUI_AJUSTE=1
WHERE TRTR_ID=33;

UPDATE CLASSIFICACAO_TRIBUTARIA
SET CLTR_TIPO_ALIQUOTA='Padrão'
WHERE CLTR_ID=97;