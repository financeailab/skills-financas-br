-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-03-27
-- =====================================================

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-03-27'),
    'V0030',
    'Ajustes nas tabelas CLASSIF_NBS_INDOP_LC e INDICADOR_OPERACAO_IBS_CBS para alterar a PK, FK e CK.'
);

-------------------------------------------------------------------------------------------------
-- Descrição:
-- Ajustes nas tabelas CLASSIF_NBS_INDOP_LC e INDICADOR_OPERACAO_IBS_CBS para alterar a PK, FK e CK.
-----------------------------------------------------------------------------------------------

-----------------------------------------------
-- 1) Recriar INDICADOR_OPERACAO_IBS_CBS
-----------------------------------------------

ALTER TABLE INDICADOR_OPERACAO_IBS_CBS RENAME TO INDICADOR_OPERACAO_IBS_CBS_OLD;

CREATE TABLE INDICADOR_OPERACAO_IBS_CBS (
    IOIC_ID INTEGER NOT NULL PRIMARY KEY,
    IOIC_CD TEXT NOT NULL,
    IOIC_LOCAL_INCIDENCIA TEXT NOT NULL,
    IOIC_INICIO_VIGENCIA TEXT NOT NULL,
    IOIC_FIM_VIGENCIA TEXT DEFAULT NULL CHECK (IOIC_FIM_VIGENCIA IS NULL OR IOIC_FIM_VIGENCIA >= IOIC_INICIO_VIGENCIA),
    IOIC_TIPO_OPERACAO TEXT NULL, 
    IOIC_CD_LOCAL_FORNECIMENTO_DFE INTEGER  CHECK (IOIC_CD_LOCAL_FORNECIMENTO_DFE BETWEEN 1 AND 28)
);

INSERT INTO INDICADOR_OPERACAO_IBS_CBS (
    IOIC_CD,
    IOIC_LOCAL_INCIDENCIA,
    IOIC_INICIO_VIGENCIA,
    IOIC_FIM_VIGENCIA,
    IOIC_TIPO_OPERACAO,
    IOIC_CD_LOCAL_FORNECIMENTO_DFE
)
SELECT 
    IOIC_CD,
    IOIC_LOCAL_INCIDENCIA,
    IOIC_INICIO_VIGENCIA,
    IOIC_FIM_VIGENCIA,
    IOIC_TIPO_OPERACAO,
    IOIC_CD_LOCAL_FORNECIMENTO_DFE
FROM INDICADOR_OPERACAO_IBS_CBS_OLD;

-----------------------------------------------
-- 2) Recriar CLASSIF_NBS_INDOP_LC
-----------------------------------------------

ALTER TABLE CLASSIF_NBS_INDOP_LC RENAME TO CLASSIF_NBS_INDOP_LC_OLD;

CREATE TABLE CLASSIF_NBS_INDOP_LC (
    CNIL_ID INTEGER NOT NULL PRIMARY KEY,
    CNIL_LSLC_CD TEXT NOT NULL,
    CNIL_NBS_CD TEXT NOT NULL,
    CNIL_IOIC_ID INTEGER NOT NULL,
    CNIL_CLTR_ID INTEGER NOT NULL,
    CNIL_INICIO_VIGENCIA TEXT NOT NULL,
    CNIL_FIM_VIGENCIA TEXT DEFAULT NULL CHECK (CNIL_FIM_VIGENCIA IS NULL OR CNIL_FIM_VIGENCIA >= CNIL_INICIO_VIGENCIA),
    CNIL_IN_PS_ONEROSA INTEGER NOT NULL DEFAULT 1,
    CNIL_IN_ADQ_EXTERIOR INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(CNIL_LSLC_CD) REFERENCES LISTA_SERVICOS_LC_116(LSLC_CD),
    FOREIGN KEY(CNIL_NBS_CD) REFERENCES NBS(NBS_CD),
    FOREIGN KEY(CNIL_IOIC_ID) REFERENCES INDICADOR_OPERACAO_IBS_CBS(IOIC_ID),
    FOREIGN KEY(CNIL_CLTR_ID) REFERENCES CLASSIFICACAO_TRIBUTARIA(CLTR_ID)
);

INSERT INTO CLASSIF_NBS_INDOP_LC (
    CNIL_ID,
    CNIL_LSLC_CD,
    CNIL_NBS_CD,
    CNIL_IOIC_ID,
    CNIL_CLTR_ID,
    CNIL_INICIO_VIGENCIA,
    CNIL_FIM_VIGENCIA,
    CNIL_IN_PS_ONEROSA,
    CNIL_IN_ADQ_EXTERIOR
)
SELECT
    OLD.CNIL_ID,
    OLD.CNIL_LSLC_CD,
    OLD.CNIL_NBS_CD,
    NEW.IOIC_ID,
    OLD.CNIL_CLTR_ID,
    OLD.CNIL_INICIO_VIGENCIA,
    OLD.CNIL_FIM_VIGENCIA,
    OLD.CNIL_IN_PS_ONEROSA,
    OLD.CNIL_IN_ADQ_EXTERIOR
FROM CLASSIF_NBS_INDOP_LC_OLD OLD
JOIN INDICADOR_OPERACAO_IBS_CBS NEW ON OLD.CNIL_IOIC_CD = NEW.IOIC_CD;

-----------------------------------------------
-- 3) Limpeza das tabelas antigas
-----------------------------------------------
DROP TABLE CLASSIF_NBS_INDOP_LC_OLD;
DROP TABLE INDICADOR_OPERACAO_IBS_CBS_OLD;

-----------------------------------------------
-- 4) Recriando índices
-----------------------------------------------
CREATE INDEX idx_indicador_operacao_ibs_cbs_local_incidencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_LOCAL_INCIDENCIA);
CREATE INDEX idx_indicador_operacao_ibs_cbs_ioic_cd ON INDICADOR_OPERACAO_IBS_CBS(IOIC_CD);
CREATE INDEX idx_indicador_operacao_ibs_cbs_inicio_vigencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_INICIO_VIGENCIA);
CREATE INDEX idx_indicador_operacao_ibs_cbs_fim_vigencia ON INDICADOR_OPERACAO_IBS_CBS(IOIC_FIM_VIGENCIA);

CREATE INDEX idx_classif_nbs_indop_lc_lslc_cd ON CLASSIF_NBS_INDOP_LC(CNIL_LSLC_CD);
CREATE INDEX idx_classif_nbs_indop_lc_nbs_cd ON CLASSIF_NBS_INDOP_LC(CNIL_NBS_CD);
CREATE INDEX idx_classif_nbs_indop_lc_ioic_id ON CLASSIF_NBS_INDOP_LC(CNIL_IOIC_ID);
CREATE INDEX idx_classif_nbs_indop_lc_cltr_id ON CLASSIF_NBS_INDOP_LC(CNIL_CLTR_ID);
CREATE INDEX idx_classif_nbs_indop_lc_inicio_vigencia ON CLASSIF_NBS_INDOP_LC(CNIL_INICIO_VIGENCIA);
CREATE INDEX idx_classif_nbs_indop_lc_fim_vigencia ON CLASSIF_NBS_INDOP_LC(CNIL_FIM_VIGENCIA);

-----------------------------------------------
-- 5) Atualização INDICADOR_OPERACAO_IBS_CBS conforme planilha enviada
-----------------------------------------------
INSERT INTO INDICADOR_OPERACAO_IBS_CBS 
 (IOIC_ID,IOIC_CD,IOIC_LOCAL_INCIDENCIA,IOIC_INICIO_VIGENCIA,IOIC_FIM_VIGENCIA,IOIC_TIPO_OPERACAO,IOIC_CD_LOCAL_FORNECIMENTO_DFE) 
VALUES
 (31,'010101','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',15),
 (32,'010102','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',16),
 (33,'010103','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',17),
 (34,'010104','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',18),
 (35,'010105','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',19),
 (36,'010106','NÃO DEFINIDO','2026-01-01',NULL,'Bem Móvel Material',20),
 (37,'010201','NÃO DEFINIDO','2026-01-01',NULL,'Aquisição de veículo automotor terrestre, aquático ou aéreo',21),
 (38,'090101','NÃO DEFINIDO','2026-01-01',NULL,'Serviço de telefonia fixa e demais serviços de comunicação prestados por meio de cabos, fios, fibras e meios similares',22),
 (39,'090102','NÃO DEFINIDO','2026-01-01',NULL,'Serviço de telefonia fixa e demais serviços de comunicação prestados por meio de cabos, fios, fibras e meios similares',23),
 (40,'110101','NÃO DEFINIDO','2026-01-01',NULL,'Operações com abastecimento de água, gás canalizado e energia elétrica',24),
 (41,'110201','NÃO DEFINIDO','2026-01-01',NULL,'Operações com abastecimento de água, gás canalizado e energia elétrica',25),
 (42,'120101','NÃO DEFINIDO','2026-01-01',NULL,'Nas aquisições de energia elétrica realizadas de forma multilateral',26),
 (43,'130101','NÃO DEFINIDO','2026-01-01',NULL,'Operações de transporte dutoviário de gás natural',27),
 (44,'130201','NÃO DEFINIDO','2026-01-01',NULL,'Operações de transporte dutoviário de gás natural',28);

UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = 'Operação com bem imóvel, bem imaterial, inclusive direito, relacionada a bem imóvel' WHERE IOIC_CD = '020101';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = NULL, IOIC_CD_LOCAL_FORNECIMENTO_DFE = NULL WHERE IOIC_CD = '030103';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = NULL, IOIC_CD_LOCAL_FORNECIMENTO_DFE = NULL WHERE IOIC_CD = '030104';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = NULL, IOIC_CD_LOCAL_FORNECIMENTO_DFE = NULL WHERE IOIC_CD = '050103';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = NULL, IOIC_CD_LOCAL_FORNECIMENTO_DFE = NULL WHERE IOIC_CD = '050104';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = 'Demais bens, em operações onerosas' WHERE IOIC_CD = '100501';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = 'Demais bens, em operações onerosas' WHERE IOIC_CD = '100502';
UPDATE INDICADOR_OPERACAO_IBS_CBS SET IOIC_TIPO_OPERACAO = 'Demais bens, em operações não onerosas' WHERE IOIC_CD = '100601';


