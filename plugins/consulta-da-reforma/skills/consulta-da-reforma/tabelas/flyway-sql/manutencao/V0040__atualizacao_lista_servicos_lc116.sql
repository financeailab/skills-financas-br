-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-06-24
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-06-24'),
    'V0040',
    'Atualiza a tabela LISTA_SERVICOS_LC_116.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- Atualiza a tabela LISTA_SERVICOS_LC_116
-- -----------------------------------------------------------------------------------------------

INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.01.01', 'Outros serviços sem a incidência de ISSQN e ICMS.', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.02.01', 'Operação com Bens Imateriais não classificados em itens anteriores.', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.03.01', 'Locação de Bens Imóveis.', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.03.02', 'Cessão Onerosa de Bens Imóveis.', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.03.03', 'Arrendamento de Bens Imóveis.', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.03.04', 'Servidão, Cessão de Uso ou de Espaço de Bens Imóveis (quando não caracterizem operações tributáveis pelo ISSQN).', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.03.05', 'Permissão de Uso ou Direito de Passagem de Bens Imóveis (quando não caracterizem operações tributáveis pelo ISSQN).', '2026-01-01', NULL);
 
INSERT INTO LISTA_SERVICOS_LC_116
VALUES ('99.04.01', 'Locação de Bens Móveis.', '2026-01-01', NULL);