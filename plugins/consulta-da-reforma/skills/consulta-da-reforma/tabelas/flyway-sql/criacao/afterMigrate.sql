-- =====================================================
-- CALLBACK FLYWAY: afterMigrate.sql
-- Verificações e otimizações pós-migração
-- Gerado em: 2025-09-24
-- =====================================================

-- ============================================================
-- Objetivo : Permitir NULL em AARE_VALOR e AADV_VALOR e
--            zerar o valor dos registros do Tributo TBTO_ID=1 (IS)
-- SQLite não suporta ALTER COLUMN: as tabelas são recriadas
-- sem o NOT NULL nas colunas VALOR.
-- ============================================================

-- ============================================================
-- ALIQUOTA_AD_REM
-- Remove NOT NULL de AARE_VALOR
-- ============================================================

PRAGMA foreign_keys = OFF;

CREATE TABLE ALIQUOTA_AD_REM_NEW (
    AARE_ID              INTEGER NOT NULL,
    AARE_VALOR           REAL,                          -- era NOT NULL
    AARE_UNMD_ID         INTEGER NOT NULL,
    AARE_TBTO_ID         INTEGER NOT NULL,
    AARE_INICIO_VIGENCIA TEXT    NOT NULL,
    AARE_FIM_VIGENCIA    TEXT    DEFAULT NULL
                                 CHECK (AARE_FIM_VIGENCIA IS NULL
                                     OR AARE_FIM_VIGENCIA >= AARE_INICIO_VIGENCIA),
    PRIMARY KEY (AARE_ID),
    FOREIGN KEY (AARE_TBTO_ID) REFERENCES TRIBUTO(TBTO_ID),
    FOREIGN KEY (AARE_UNMD_ID) REFERENCES UNIDADE_MEDIDA(UNMD_ID)
);

INSERT INTO ALIQUOTA_AD_REM_NEW
SELECT * FROM ALIQUOTA_AD_REM;

DROP TABLE ALIQUOTA_AD_REM;

ALTER TABLE ALIQUOTA_AD_REM_NEW RENAME TO ALIQUOTA_AD_REM;

CREATE INDEX idx_aliquota_ad_rem_tbto_id ON ALIQUOTA_AD_REM(AARE_TBTO_ID);
CREATE INDEX idx_aliquota_ad_rem_unmd_id ON ALIQUOTA_AD_REM(AARE_UNMD_ID);
CREATE INDEX idx_aliquota_ad_rem_inicio_vigencia ON ALIQUOTA_AD_REM(AARE_INICIO_VIGENCIA);
CREATE INDEX idx_aliquota_ad_rem_fim_vigencia ON ALIQUOTA_AD_REM(AARE_FIM_VIGENCIA);
CREATE INDEX idx_aliquota_ad_rem_vigencia ON ALIQUOTA_AD_REM (AARE_INICIO_VIGENCIA, AARE_FIM_VIGENCIA);

-- ============================================================
-- ALIQUOTA_AD_VALOREM
-- Remove NOT NULL de AADV_VALOR
-- ============================================================

CREATE TABLE ALIQUOTA_AD_VALOREM_NEW (
    AADV_ID              INTEGER NOT NULL,
    AADV_VALOR           REAL,                          -- era NOT NULL
    AADV_TBTO_ID         INTEGER NOT NULL,
    AADV_INICIO_VIGENCIA TEXT    NOT NULL,
    AADV_FIM_VIGENCIA    TEXT    DEFAULT NULL
                                 CHECK (AADV_FIM_VIGENCIA IS NULL
                                     OR AADV_FIM_VIGENCIA >= AADV_INICIO_VIGENCIA),
    AADV_CLTR_ID         INTEGER REFERENCES CLASSIFICACAO_TRIBUTARIA(CLTR_ID),
    PRIMARY KEY (AADV_ID),
    FOREIGN KEY (AADV_TBTO_ID) REFERENCES TRIBUTO(TBTO_ID)
);

INSERT INTO ALIQUOTA_AD_VALOREM_NEW
SELECT * FROM ALIQUOTA_AD_VALOREM;

DROP TABLE ALIQUOTA_AD_VALOREM;

ALTER TABLE ALIQUOTA_AD_VALOREM_NEW RENAME TO ALIQUOTA_AD_VALOREM;

CREATE INDEX idx_aliquota_ad_valorem_tbto_id ON ALIQUOTA_AD_VALOREM(AADV_TBTO_ID);
CREATE INDEX idx_aliquota_ad_valorem_inicio_vigencia ON ALIQUOTA_AD_VALOREM(AADV_INICIO_VIGENCIA);
CREATE INDEX idx_aliquota_ad_valorem_fim_vigencia ON ALIQUOTA_AD_VALOREM(AADV_FIM_VIGENCIA);
CREATE INDEX idx_aliquota_ad_valorem_vigencia ON ALIQUOTA_AD_VALOREM (AADV_INICIO_VIGENCIA, AADV_FIM_VIGENCIA);

-- ============================================================
-- UPDATEs: zera VALOR para NULL onde TBTO_ID = 1 (IS)
-- ============================================================

-- ALIQUOTA_AD_REM  (2 registro(s) com AARE_TBTO_ID = 1)
UPDATE ALIQUOTA_AD_REM
SET    AARE_VALOR = NULL
WHERE  AARE_TBTO_ID = 1;

-- ALIQUOTA_AD_VALOREM  (registros com AADV_TBTO_ID = 1)
UPDATE ALIQUOTA_AD_VALOREM
SET    AADV_VALOR = NULL
WHERE  AADV_TBTO_ID = 1;

PRAGMA foreign_keys = ON;

--
-- Fim ajustes
--

CREATE INDEX IF NOT EXISTS idx_ajuste_vigencia ON AJUSTE (AJST_INICIO_VIGENCIA, AJST_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_rem_vigencia ON ALIQUOTA_AD_REM (AARE_INICIO_VIGENCIA, AARE_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_rem_produto_vigencia ON ALIQUOTA_AD_REM_PRODUTO (AARP_INICIO_VIGENCIA, AARP_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_rem_servico_vigencia ON ALIQUOTA_AD_REM_SERVICO (AARS_INICIO_VIGENCIA, AARS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_valorem_vigencia ON ALIQUOTA_AD_VALOREM (AADV_INICIO_VIGENCIA, AADV_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_valorem_produto_vigencia ON ALIQUOTA_AD_VALOREM_PRODUTO (AAVP_INICIO_VIGENCIA, AAVP_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_ad_valorem_servico_vigencia ON ALIQUOTA_AD_VALOREM_SERVICO (AAVS_INICIO_VIGENCIA, AAVS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_padrao_vigencia ON ALIQUOTA_PADRAO (ALPA_INICIO_VIGENCIA, ALPA_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_aliquota_referencia_vigencia ON ALIQUOTA_REFERENCIA (ALRE_INICIO_VIGENCIA, ALRE_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_anexo_vigencia ON ANEXO (ANXO_INICIO_VIGENCIA, ANXO_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_apropriacao_credito_adquirente_vigencia ON APROPRIACAO_CREDITO_ADQUIRENTE (APCA_INICIO_VIGENCIA, APCA_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_classificacao_tributaria_vigencia ON CLASSIFICACAO_TRIBUTARIA (CLTR_INICIO_VIGENCIA, CLTR_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_ad_rem_produto_vigencia ON EXCECAO_AD_REM_PRODUTO (EARP_INICIO_VIGENCIA, EARP_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_ad_rem_servico_vigencia ON EXCECAO_AD_REM_SERVICO (EARS_INICIO_VIGENCIA, EARS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_ad_valorem_produto_vigencia ON EXCECAO_AD_VALOREM_PRODUTO (EAVP_INICIO_VIGENCIA, EAVP_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_ad_valorem_servico_vigencia ON EXCECAO_AD_VALOREM_SERVICO (EAVS_INICIO_VIGENCIA, EAVS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_nbs_aplicavel_vigencia ON EXCECAO_NBS_APLICAVEL (ENBS_INICIO_VIGENCIA, ENBS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_excecao_ncm_aplicavel_vigencia ON EXCECAO_NCM_APLICAVEL (ENCM_INICIO_VIGENCIA, ENCM_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_fundamentacao_classificacao_vigencia ON FUNDAMENTACAO_CLASSIFICACAO (FDCL_INICIO_VIGENCIA, FDCL_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_fundamentacao_legal_vigencia ON FUNDAMENTACAO_LEGAL (FDLG_INICIO_VIGENCIA, FDLG_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_nbs_vigencia ON NBS (NBS_INICIO_VIGENCIA, NBS_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_nbs_aplicavel_vigencia ON NBS_APLICAVEL (NBSA_INICIO_VIGENCIA, NBSA_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_ncm_vigencia ON NCM (NCM_INICIO_VIGENCIA, NCM_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_ncm_aplicavel_vigencia ON NCM_APLICAVEL (NCMA_INICIO_VIGENCIA, NCMA_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_percentual_reducao_vigencia ON PERCENTUAL_REDUCAO (PERE_INICIO_VIGENCIA, PERE_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_redutor_vigencia ON REDUTOR (RDTO_INICIO_VIGENCIA, RDTO_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_situacao_tributaria_vigencia ON SITUACAO_TRIBUTARIA (SITR_INICIO_VIGENCIA, SITR_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tipo_dfe_vigencia ON TIPO_DFE (TPDF_INICIO_VIGENCIA, TPDF_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tipo_dfe_classificacao_vigencia ON TIPO_DFE_CLASSIFICACAO (TDCL_INICIO_VIGENCIA, TDCL_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tomador_especifico_vigencia ON TOMADOR_ESPECIFICO (TMES_INICIO_VIGENCIA, TMES_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tratamento_classificacao_vigencia ON TRATAMENTO_CLASSIFICACAO (TRCL_INICIO_VIGENCIA, TRCL_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tratamento_tributario_vigencia ON TRATAMENTO_TRIBUTARIO (TRTR_INICIO_VIGENCIA, TRTR_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tributo_vigencia ON TRIBUTO (TBTO_INICIO_VIGENCIA, TBTO_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_tributo_situacao_tributaria_vigencia ON TRIBUTO_SITUACAO_TRIBUTARIA (TRST_INICIO_VIGENCIA, TRST_FIM_VIGENCIA);
CREATE INDEX IF NOT EXISTS idx_unidade_medida_vigencia ON UNIDADE_MEDIDA (UNMD_INICIO_VIGENCIA, UNMD_FIM_VIGENCIA);


-- =====================================================
-- SEÇÃO 1: VERIFICAÇÕES DE INTEGRIDADE
-- =====================================================

-- Verifica integridade geral do banco
PRAGMA integrity_check;

-- Verifica consistência de chaves estrangeiras
PRAGMA foreign_key_check;

-- Verifica se foreign keys estão habilitadas
SELECT 
    CASE 
        WHEN foreign_keys = 1 THEN '✅ Foreign keys HABILITADAS'
        ELSE '❌ Foreign keys DESABILITADAS - PROBLEMA!'
    END as status_fk
FROM PRAGMA_foreign_keys();

-- =====================================================
-- SEÇÃO 2: ANÁLISE DE PERFORMANCE
-- =====================================================

-- Atualiza estatísticas para otimização de consultas
ANALYZE;

-- Executa otimizações automáticas
PRAGMA optimize;

-- Verifica tamanho das tabelas principais
SELECT 
    name as tabela,
    ROUND((
        SELECT COUNT(*) * 
        (SELECT AVG(length(sql)) FROM sqlite_master WHERE type='table' AND name=m.name)
        FROM sqlite_master WHERE type='table' AND name=m.name
    ) / 1024.0, 2) || ' KB' as tamanho_estimado
FROM sqlite_master m
WHERE type = 'table' 
AND name NOT LIKE 'sqlite_%'
AND name NOT LIKE 'flyway_%'
ORDER BY name;

-- =====================================================
-- FIM DAS VERIFICAÇÕES
-- =====================================================

-- Mensagem final
SELECT '🎉 Verificações pós-migração concluídas com sucesso!' as status_final;

-- =====================================================
-- CALLBACK afterMigrate.sql - CONCLUÍDO
-- =====================================================
