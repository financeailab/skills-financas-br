-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-04-07
-- =====================================================

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-04-07'),
    'V0031',
    'Atualizações de tratamento tributário'
);

-------------------------------------------------------------------------------------------------
-- Descrição:
-- Atualiza tratamentos tributários
-----------------------------------------------------------------------------------------------

UPDATE CLASSIFICACAO_TRIBUTARIA SET CLTR_IND_GCREDPRESOPER=1 WHERE CLTR_ID=85;
UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_EXPRESSAO_ALIQUOTA='0' WHERE TRTR_ID=22;
UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_EXPRESSAO_ALIQUOTA='0' WHERE TRTR_ID=33;
UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_EXPRESSAO_ALIQUOTA='0' WHERE TRTR_ID=38;
UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_EXPRESSAO_ALIQUOTA='0' WHERE TRTR_ID=39;
UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_DESCRICAO='Suspensão em operações com hidrocarbonetos líquidos', TRTR_IN_POSSUI_AJUSTE=1 WHERE TRTR_ID=41;


