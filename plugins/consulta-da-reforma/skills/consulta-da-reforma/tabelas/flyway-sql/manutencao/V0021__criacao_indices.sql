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
    'V0021',
    'Criação de índices.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1 - Criação de índices
-- -----------------------------------------------------------------------------------------------

-- -----------------------------------------------------------------------------------------------
-- Início da migração
-- -----------------------------------------------------------------------------------------------

-- Índices para REDUTOR_COMPRA_GOVERNAMENTAL
CREATE INDEX idx_redutor_compra_governamental_inicio_vigencia ON REDUTOR_COMPRA_GOVERNAMENTAL(RCGO_INICIO_VIGENCIA);
CREATE INDEX idx_redutor_compra_governamental_fim_vigencia ON REDUTOR_COMPRA_GOVERNAMENTAL(RCGO_FIM_VIGENCIA);

-- Índices para TRANSFERENCIA_CBS_ENTE_GOV
CREATE INDEX idx_transferencia_cbs_ente_gov_inicio_vigencia ON TRANSFERENCIA_CBS_ENTE_GOV(TCEG_INICIO_VIGENCIA);
CREATE INDEX idx_transferencia_cbs_ente_gov_fim_vigencia ON TRANSFERENCIA_CBS_ENTE_GOV(TCEG_FIM_VIGENCIA);

-- Índices para INDICADOR_OPERACAO_IBS_CBS
CREATE INDEX idx_indicador_operacao_ibs_cbs_local_incidencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_LOCAL_INCIDENCIA);
CREATE INDEX idx_indicador_operacao_ibs_cbs_inicio_vigencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_INICIO_VIGENCIA);
CREATE INDEX idx_indicador_operacao_ibs_cbs_fim_vigencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_FIM_VIGENCIA);

-- Índices para LISTA_SERVICOS_LC_116
CREATE INDEX idx_lista_servicos_lc_116_descricao ON LISTA_SERVICOS_LC_116(LSLC_DESCRICAO);
CREATE INDEX idx_lista_servicos_lc_116_inicio_vigencia ON LISTA_SERVICOS_LC_116(LSLC_INICIO_VIGENCIA);
CREATE INDEX idx_lista_servicos_lc_116_fim_vigencia ON LISTA_SERVICOS_LC_116(LSLC_FIM_VIGENCIA);

-- Índices para CLASSIF_NBS_INDOP_LC
CREATE INDEX idx_classif_nbs_indop_lc_lslc_cd ON CLASSIF_NBS_INDOP_LC(CNIL_LSLC_CD);
CREATE INDEX idx_classif_nbs_indop_lc_nbs_cd ON CLASSIF_NBS_INDOP_LC(CNIL_NBS_CD);
CREATE INDEX idx_classif_nbs_indop_lc_ioic_cd ON CLASSIF_NBS_INDOP_LC(CNIL_IOIC_CD);
CREATE INDEX idx_classif_nbs_indop_lc_cltr_id ON CLASSIF_NBS_INDOP_LC(CNIL_CLTR_ID);
CREATE INDEX idx_classif_nbs_indop_lc_inicio_vigencia ON CLASSIF_NBS_INDOP_LC(CNIL_INICIO_VIGENCIA);
CREATE INDEX idx_classif_nbs_indop_lc_fim_vigencia ON CLASSIF_NBS_INDOP_LC(CNIL_FIM_VIGENCIA);
