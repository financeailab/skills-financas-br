-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-07-08
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-07-08'),
    'V0044',
    'Criação e carga de tabelas relacionadas a grupos de DFE.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Criação e carga da tabela GRUPO_DFE
-- 2. Atualização de tipos de DFE para correspondência com os dados do ROC
-- 3. Inclusão de tipos de DFE para correspondência com os dados do ROC
-- 4. Criação de chave estrangeira para a tabela TIPO_DFE, com referência à tabela GRUPO_DFE
-- -----------------------------------------------------------------------------------------------

-- ================================================
-- 1. Criação e carga da tabela GRUPO_DFE
-- ================================================

CREATE TABLE GRUPO_DFE (
    GRDF_ID INTEGER NOT NULL,
    GRDF_DESCRICAO TEXT NOT NULL,
    GRDF_INICIO_VIGENCIA TEXT NOT NULL,
    GRDF_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("GRDF_FIM_VIGENCIA" IS NULL OR "GRDF_FIM_VIGENCIA" >= "GRDF_INICIO_VIGENCIA"),
    PRIMARY KEY (GRDF_ID)
);

INSERT INTO GRUPO_DFE
VALUES (1, 'MERCADORIAS', '2026-01-01', NULL);

INSERT INTO GRUPO_DFE
VALUES (2, 'SERVIÇOS', '2026-01-01', NULL);

INSERT INTO GRUPO_DFE
VALUES (3, 'TRANSPORTES', '2026-01-01', NULL);

INSERT INTO GRUPO_DFE
VALUES (4, 'FATURAS', '2026-01-01', NULL);

INSERT INTO GRUPO_DFE
VALUES (5, 'DOCUMENTOS ESPECIAIS E COMÉRCIO EXTERIOR', '2026-01-01', NULL);

-- ==========================================================================
-- 2. Atualização de tipos de DFE para correspondência com os dados do ROC
-- ==========================================================================

UPDATE TIPO_DFE
SET TPDF_TIPO=77, TPDF_SIGLA='NF-e ABI', TPDF_DESCRICAO='Nota Fiscal Eletrônica de Alienação de Bens Imóveis', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=1;
UPDATE TIPO_DFE
SET TPDF_TIPO=55, TPDF_SIGLA='NF-e', TPDF_DESCRICAO='Nota Fiscal Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=2;
UPDATE TIPO_DFE
SET TPDF_TIPO=65, TPDF_SIGLA='NFC-e', TPDF_DESCRICAO='Nota Fiscal de Consumidor Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=3;
UPDATE TIPO_DFE
SET TPDF_TIPO=57, TPDF_SIGLA='CT-e', TPDF_DESCRICAO='Conhecimento de Transporte Eletrônico', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=4;
UPDATE TIPO_DFE
SET TPDF_TIPO=67, TPDF_SIGLA='CT-e OS', TPDF_DESCRICAO='Conhecimento de Transporte Eletrônico para Outros Serviços ', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=5;
UPDATE TIPO_DFE
SET TPDF_TIPO=63, TPDF_SIGLA='BP-e', TPDF_DESCRICAO='Bilhete de Passagem Eletrônico', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=6;
UPDATE TIPO_DFE
SET TPDF_TIPO=83, TPDF_SIGLA='BP-e TA', TPDF_DESCRICAO='Bilhete de Passagem Eletrônico para Transporte Aéreo', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=7;
UPDATE TIPO_DFE
SET TPDF_TIPO=93, TPDF_SIGLA='BP-e TM', TPDF_DESCRICAO='Bilhete de Passagem Eletrônico de Transporte Metropolitano', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=8;
UPDATE TIPO_DFE
SET TPDF_TIPO=66, TPDF_SIGLA='NF3-e', TPDF_DESCRICAO='Nota Fiscal de Energia Elétrica Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=9;
UPDATE TIPO_DFE
SET TPDF_TIPO=91, TPDF_SIGLA='NFS-e', TPDF_DESCRICAO='Nota Fiscal de Serviços Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=10;
UPDATE TIPO_DFE
SET TPDF_TIPO=92, TPDF_SIGLA='NFS-e Via', TPDF_DESCRICAO='Nota Fiscal de Serviço Eletrônica de Exploração de Vias', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=11;
UPDATE TIPO_DFE
SET TPDF_TIPO=62, TPDF_SIGLA='NFCom', TPDF_DESCRICAO='Nota Fiscal de Fatura de Serviços de Comunicação Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=12;
UPDATE TIPO_DFE
SET TPDF_TIPO=94, TPDF_SIGLA='DERE', TPDF_DESCRICAO='Declaração de Regimes Específicos', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=13;
UPDATE TIPO_DFE
SET TPDF_TIPO=75, TPDF_SIGLA='NFAg', TPDF_DESCRICAO='Nota Fiscal da Água e Saneamento Eletrônica', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=14;
UPDATE TIPO_DFE
SET TPDF_TIPO=76, TPDF_SIGLA='NFGas', TPDF_DESCRICAO='Nota Fiscal Eletrônica do Gás', TPDF_INICIO_VIGENCIA='2026-01-01', TPDF_FIM_VIGENCIA=NULL
WHERE TPDF_ID=15;

-- ==========================================================================
-- 3. Inclusão de tipos de DFE para correspondência com os dados do ROC
-- ==========================================================================

INSERT INTO TIPO_DFE
(TPDF_ID, TPDF_TIPO, TPDF_SIGLA, TPDF_DESCRICAO, TPDF_INICIO_VIGENCIA, TPDF_FIM_VIGENCIA)
VALUES(16, 97, 'CT-e Simplificado', 'Conhecimento de Transporte Eletrônico Simplificado', '2026-01-01', NULL);
INSERT INTO TIPO_DFE
(TPDF_ID, TPDF_TIPO, TPDF_SIGLA, TPDF_DESCRICAO, TPDF_INICIO_VIGENCIA, TPDF_FIM_VIGENCIA)
VALUES(17, 95, 'DIR', 'Declaração de Importação de Remessa', '2026-01-01', NULL);
INSERT INTO TIPO_DFE
(TPDF_ID, TPDF_TIPO, TPDF_SIGLA, TPDF_DESCRICAO, TPDF_INICIO_VIGENCIA, TPDF_FIM_VIGENCIA)
VALUES(18, 96, 'Duimp', 'Declaração Única de Importação ', '2026-01-01', NULL);

-- ==========================================================================================
-- 4. Criação de chave estrangeira para a tabela TIPO_DFE, com referência à tabela GRUPO_DFE
-- ==========================================================================================

-- O SQLite não permite ADD COLUMN com REFERENCES e DEFAULT não nulo com foreign_keys ligado.
-- A checagem é desligada só para este comando (o Flyway executa este script fora de transação).
PRAGMA foreign_keys = OFF;
ALTER TABLE TIPO_DFE ADD COLUMN TPDF_GRDF_ID INTEGER NOT NULL default 1 REFERENCES GRUPO_DFE(GRDF_ID);
PRAGMA foreign_keys = ON;

-- MERCADORIAS

UPDATE TIPO_DFE SET TPDF_GRDF_ID = 1 WHERE TPDF_ID = 2; -- NF-e
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 1 WHERE TPDF_ID = 3; -- NFC-e

-- SERVIÇOS

UPDATE TIPO_DFE SET TPDF_GRDF_ID = 2 WHERE TPDF_ID = 10; -- NFS-e
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 2 WHERE TPDF_ID = 11; -- NFS-e Via

-- TRANSPORTES

UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 4; -- CT-e
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 5; -- CT-e OS
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 16; -- CT-e Simplificado
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 6; -- BP-e
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 7; -- BP-e TA
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 3 WHERE TPDF_ID = 8; -- BP-e TM

-- FATURAS

UPDATE TIPO_DFE SET TPDF_GRDF_ID = 4 WHERE TPDF_ID = 14; -- NFAg
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 4 WHERE TPDF_ID = 15; -- NFGas
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 4 WHERE TPDF_ID = 12; -- NFCom
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 4 WHERE TPDF_ID = 9; -- NF3-e

-- DOCUMENTOS ESPECIAIS E COMÉRCIO EXTERIOR

UPDATE TIPO_DFE SET TPDF_GRDF_ID = 5 WHERE TPDF_ID = 13; -- DERE
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 5 WHERE TPDF_ID = 17; -- DIR
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 5 WHERE TPDF_ID = 18; -- Duimp
UPDATE TIPO_DFE SET TPDF_GRDF_ID = 5 WHERE TPDF_ID = 1; -- NF-e ABI

