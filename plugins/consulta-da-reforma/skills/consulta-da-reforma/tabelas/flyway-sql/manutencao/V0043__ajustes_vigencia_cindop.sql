-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-31
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-31'),
    'V0043',
    'Ajustes na vigência das tabelas CLASSIF_NBS_INDOP_LC e INDICADOR_OPERACAO_IBS_CBS.'
);

-- ============================================================
-- Ajustes de vigência da tabela CLASSIF_NBS_INDOP_LC e INDICADOR_OPERACAO_IBS_CBS
-- Registros com inicio de vigência em 01/09/2026 passam a ter inicio de vigencia em 01/10/2026
-- Registros com fim de vigência em 31/08/2026 passam ter fim de vigência em 30/09/2026
-- ============================================================
UPDATE CLASSIF_NBS_INDOP_LC SET CNIL_FIM_VIGENCIA = '2026-09-30' WHERE CNIL_FIM_VIGENCIA = '2026-08-31';
UPDATE CLASSIF_NBS_INDOP_LC SET CNIL_INICIO_VIGENCIA = '2026-10-01' WHERE CNIL_INICIO_VIGENCIA = '2026-09-01';

UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_FIM_VIGENCIA = '2026-09-30' WHERE IOIC_FIM_VIGENCIA = '2026-08-31';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_INICIO_VIGENCIA = '2026-10-01' WHERE IOIC_INICIO_VIGENCIA = '2026-09-01';