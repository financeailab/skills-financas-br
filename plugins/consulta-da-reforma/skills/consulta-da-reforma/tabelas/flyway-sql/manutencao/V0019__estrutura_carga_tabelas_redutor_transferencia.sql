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
    'V0019',
    'Criação da tabela REDUTOR_COMPRA_GOVERNAMENTAL e TRANSFERENCIA_CBS_ENTE_GOV e carga de dados.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1 - Criação da tabela REDUTOR_COMPRA_GOVERNAMENTAL;
-- 2 - Carga de dados da tabela REDUTOR_COMPRA_GOVERNAMENTAL;
-- 3 - Criação da tabela TRANSFERENCIA_CBS_ENTE_GOV;
-- 4 - Carga de dados da tabela TRANSFERENCIA_CBS_ENTE_GOV.
-- -----------------------------------------------------------------------------------------------

-- -----------------------------------------------------------------------------------------------
-- Início da migração
-- -----------------------------------------------------------------------------------------------

-- -----------------------------------------------------------------------------------------------
-- Criação da tabela REDUTOR_COMPRA_GOVERNAMENTAL
-- -----------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS REDUTOR_COMPRA_GOVERNAMENTAL (
	RCGO_ID INTEGER NOT NULL,
	RCGO_VALOR REAL NOT NULL,
	RCGO_INICIO_VIGENCIA TEXT NOT NULL,
	RCGO_FIM_VIGENCIA TEXT DEFAULT NULL CHECK (RCGO_FIM_VIGENCIA IS NULL OR RCGO_FIM_VIGENCIA >= RCGO_INICIO_VIGENCIA),
PRIMARY KEY (RCGO_ID)
);

-----------------------------------------------------------------------------------------
-- Carga de dados da tabela REDUTOR_COMPRA_GOVERNAMENTAL
-----------------------------------------------------------------------------------------

INSERT INTO REDUTOR_COMPRA_GOVERNAMENTAL VALUES (1, 50.0, '2027-01-01', NULL);


-- -----------------------------------------------------------------------------------------------
-- Criação da tabela TRANSFERENCIA_CBS_ENTE_GOV
-- -----------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS TRANSFERENCIA_CBS_ENTE_GOV (
	TCEG_ID INTEGER NOT NULL,
	TCEG_VALOR REAL NOT NULL,
	TCEG_INICIO_VIGENCIA TEXT NOT NULL,
	TCEG_FIM_VIGENCIA TEXT DEFAULT NULL CHECK (TCEG_FIM_VIGENCIA IS NULL OR TCEG_FIM_VIGENCIA >= TCEG_INICIO_VIGENCIA),
PRIMARY KEY (TCEG_ID)
);

-----------------------------------------------------------------------------------------
-- Carga de dados da tabela TRANSFERENCIA_CBS_ENTE_GOV
-----------------------------------------------------------------------------------------

INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (1, 10.0, '2029-01-01', '2029-12-31');
 
INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (2, 20.0, '2030-01-01', '2030-12-31');
 
INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (3, 30.0, '2031-01-01', '2031-12-31');
 
INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (4, 40.0, '2032-01-01', '2032-12-31');
 
INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (5, 100.0, '2033-01-01', NULL);
