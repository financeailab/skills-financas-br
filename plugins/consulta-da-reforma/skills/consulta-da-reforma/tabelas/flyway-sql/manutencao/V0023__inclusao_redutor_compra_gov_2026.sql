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
    'V0023',
    'Inclusão de redutor compra governamental com valor Zero para 2026.'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1 - Inclusão de redutor compra governamental com valor Zero para 2026. Facilita a implementacao
-- -----------------------------------------------------------------------------------------------
INSERT INTO REDUTOR_COMPRA_GOVERNAMENTAL VALUES (2, 0.0, '2026-01-01', '2026-12-31');

-- nao transfere CBS para UF ou municipio entre 2026 e 2028
INSERT INTO TRANSFERENCIA_CBS_ENTE_GOV VALUES (6, 0.0, '2026-01-01', '2028-12-31');

UPDATE TRATAMENTO_TRIBUTARIO SET TRTR_EXPRESSAO_ALIQUOTA_EFETIVA = 'aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)' 
WHERE TRTR_ID IN (3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,29,30,31,32,33,34,35,36,37,38,39,40);
