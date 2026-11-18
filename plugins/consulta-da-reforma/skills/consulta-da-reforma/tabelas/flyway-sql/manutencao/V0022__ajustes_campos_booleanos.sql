-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-01-08
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-01-08'),
    'V0022',
    'Ajustes na tabela CLASSIF_NBS_INDOP_LC.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1 - Ajustes das colunas CNIL_IN_PS_ONEROSA e CNIL_IN_ADQ_EXTERIOR como booleanas.
-- -----------------------------------------------------------------------------------------------

-- -----------------------------------------------------------------------------------------------
-- Início da migração
-- -----------------------------------------------------------------------------------------------

ALTER TABLE CLASSIF_NBS_INDOP_LC DROP COLUMN CNIL_IN_PS_ONEROSA;

ALTER TABLE CLASSIF_NBS_INDOP_LC DROP COLUMN CNIL_IN_ADQ_EXTERIOR;

ALTER TABLE CLASSIF_NBS_INDOP_LC
ADD COLUMN CNIL_IN_PS_ONEROSA INTEGER NOT NULL DEFAULT 1;

ALTER TABLE CLASSIF_NBS_INDOP_LC
ADD COLUMN CNIL_IN_ADQ_EXTERIOR INTEGER NOT NULL DEFAULT 0;
