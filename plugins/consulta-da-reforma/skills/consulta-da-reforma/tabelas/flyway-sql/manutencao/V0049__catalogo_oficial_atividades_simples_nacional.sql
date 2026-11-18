-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-07
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-07'),
    'V0049',
    'Criação e carga da tabela ATIVIDADE_SIMPLES_NACIONAL com o catálogo oficial de atividades do Simples Nacional (15 atividades: códigos 01 a 14 e 90), conforme a tabela publicada da NT 2026.005.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Criação e carga da tabela ATIVIDADE_SIMPLES_NACIONAL (catálogo oficial de atividades)
-- -----------------------------------------------------------------------------------------------

-- ==========================================================================================
-- 1. Criação e carga da tabela ATIVIDADE_SIMPLES_NACIONAL
-- ==========================================================================================
--
-- Catálogo oficial de atividades do Simples Nacional (endpoint
-- calculadora/simples-nacional/atividades e validação do cAtivSN no cálculo da NT 2026.005).
--
-- Colunas além das descritivas:
--   ATSN_ANEXO_SEM_FATOR_R / ATSN_ANEXO_COM_FATOR_R: anexos de apuração (numerais romanos),
--     AMBOS anuláveis — a linha do código 90 (Operações não Tributáveis) não possui anexo;
--   ATSN_CATIVSN: código oficial de atividade do Simples Nacional (tag cAtivSN dos leiautes
--     de DFe, 2 caracteres com zero à esquerda), único entre as linhas vigentes;
--   ATSN_IN_NAO_TRIBUTAVEL: 1 = linha de operações não tributáveis (o código 90).
--     O cálculo usa este indicador na validação de incompatibilidade com classificações
--     tributárias que declaram receita (regra UB14-90 da NT 2026.005) — o valor '90' não
--     fica fixo no código Java.
--
-- A numeração dos códigos é a da tabela oficial de atividades publicada: 01 a 14, mais o
-- código especial 90 (Operações não Tributáveis). A coluna "Mercado Externo" da tabela
-- oficial não é representada neste catálogo.
--
-- A atividade 09 é a única sujeita ao Fator R (Anexo III sem o fator, Anexo V com ele).
--
-- Correções futuras de numeração ou descrição devem ser feitas por VERSIONAMENTO DE
-- VIGÊNCIA das linhas afetadas (fechar ATSN_FIM_VIGENCIA e criar linha nova), nunca por
-- UPDATE destrutivo, para preservar recálculos retroativos.

CREATE TABLE ATIVIDADE_SIMPLES_NACIONAL (
    ATSN_ID INTEGER NOT NULL,
    ATSN_ORDEM INTEGER NOT NULL,
    ATSN_DESCRICAO TEXT NOT NULL,
    ATSN_ANEXO_SEM_FATOR_R TEXT,
    ATSN_ANEXO_COM_FATOR_R TEXT,
    ATSN_ROTULO TEXT NOT NULL,
    ATSN_ROTULO_CURTO TEXT NOT NULL,
    ATSN_CATIVSN TEXT,
    ATSN_IN_NAO_TRIBUTAVEL INTEGER NOT NULL DEFAULT 0 CHECK (ATSN_IN_NAO_TRIBUTAVEL IN (0, 1)),
    ATSN_INICIO_VIGENCIA TEXT NOT NULL,
    ATSN_FIM_VIGENCIA TEXT DEFAULT NULL CHECK ("ATSN_FIM_VIGENCIA" IS NULL OR "ATSN_FIM_VIGENCIA" >= "ATSN_INICIO_VIGENCIA"),
    PRIMARY KEY (ATSN_ID)
);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (1, 1, 'Revenda de mercadorias, venda de mercadorias industrializadas pelo contribuinte', 'I', NULL, 'I', 'I', '01', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (2, 2, 'Operações com os demais bens materiais, sem incidência de ICMS', 'I', NULL, 'I, menos ICMS', 'I', '02', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (3, 3, 'Venda de mercadorias industrializadas pelo contribuinte, com industrialização incentivada na Zona Franca de Manaus', 'II', NULL, 'II', 'II', '03', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (4, 4, 'Operações com os demais bens materiais, com industrialização incentivada na Zona Franca de Manaus, sem incidência de ICMS', 'II', NULL, 'II, menos ICMS', 'II', '04', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (5, 5, 'Prestação de serviços de transporte intermunicipal e interestadual de carga ou de passageiros autorizados no inciso VI do art. 17 da LC 123', 'III', NULL, 'III, menos ISS, mais ICMS do I', 'III', '05', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (6, 6, 'Prestação de serviços de comunicação', 'III', NULL, 'III, menos ISS, mais ICMS do I', 'III', '06', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (7, 7, 'Prestação de serviços, cessão de direitos, de uso ou de espaço com incidência do ISS, tributados exclusivamente pelo Anexo III', 'III', NULL, 'III', 'III', '07', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (8, 8, 'Prestação de serviços contábeis autorizados a pagar o ISS em valor fixo em guia do Município', 'III', NULL, 'III, menos o ISS', 'III', '08', 0, '2027-01-01', NULL);

-- Atividade 09: a única sujeita ao Fator R — Anexo III sem o fator, Anexo V com ele.

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (9, 9, 'Prestação de serviços — Sujeitos ao Fator "R"', 'III', 'V', 'III ou V', 'III ou V', '09', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (10, 10, 'Prestação de serviços de transporte municipal rodoviário, metroviário, ferroviário e aquaviário de passageiros relacionados no subitem 16.01 da lista anexa à LC 116/2003', 'III', NULL, 'III', 'III', '10', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (11, 11, 'Locação de bens móveis e operações com serviços, bens imateriais e direitos, inclusive com bens imóveis, sem incidência de ISS', 'III', NULL, 'III, menos o ISS', 'III', '11', 0, '2027-01-01', NULL);

-- Construção civil (subitens 7.02 e 7.05 da lista anexa à LC 116/2003): a tabela oficial
-- traz DUAS atividades com a mesma descrição, distinguidas pelo anexo de apuração —
-- a 12 apura pelo Anexo III e a 13, pelo Anexo IV.

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (12, 12, 'Prestação de serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da lista anexa à LC 116/2003', 'III', NULL, 'III', 'III', '12', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (13, 13, 'Prestação de serviços da área da construção civil relacionados nos subitens 7.02 e 7.05 da lista anexa à LC 116/2003', 'IV', NULL, 'IV', 'IV', '13', 0, '2027-01-01', NULL);

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (14, 14, 'Prestação de serviços', 'IV', NULL, 'IV', 'IV', '14', 0, '2027-01-01', NULL);

-- Código 90 - Operações não Tributáveis: linha própria do catálogo, SEM anexos de
-- apuração (não é atividade de apuração do Simples) e com o indicador de não tributável
-- ligado. Aparece na listagem do endpoint como item normal.

INSERT INTO ATIVIDADE_SIMPLES_NACIONAL
VALUES (15, 15, 'Operações não Tributáveis', NULL, NULL, 'Não tributável', 'Não tributável', '90', 1, '2027-01-01', NULL);
