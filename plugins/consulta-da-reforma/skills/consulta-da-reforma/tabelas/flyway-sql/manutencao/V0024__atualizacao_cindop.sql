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
    'V0024',
    'Atualizacao tabela INDICADOR_OPERACAO_IBS_CBS (cIndOp)'
);


-- inclusao de cIndOP que constavam no anexo VII mas não no anexo VIII
-- https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/anexovii-indop_ibscbs_v1-00-00.xlsx
-- https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/anexoviii-correlacaoitemnbsindopcclasstrib_ibscbs_v1-00-00.xlsx
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('070101', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('070102', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100102', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100201', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100302', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100401', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100502', 'NÃO DEFINIDO', '2026-01-01', NULL);
INSERT INTO INDICADOR_OPERACAO_IBS_CBS (IOIC_CD, IOIC_LOCAL_INCIDENCIA, IOIC_INICIO_VIGENCIA, IOIC_FIM_VIGENCIA) VALUES ('100601', 'NÃO DEFINIDO', '2026-01-01', NULL);

-- inclusao de colunas novas
ALTER TABLE INDICADOR_OPERACAO_IBS_CBS ADD COLUMN IOIC_TIPO_OPERACAO TEXT NULL;
ALTER TABLE INDICADOR_OPERACAO_IBS_CBS ADD COLUMN IOIC_CD_LOCAL_FORNECIMENTO_DFE INTEGER CHECK (IOIC_CD_LOCAL_FORNECIMENTO_DFE BETWEEN 1 AND 14);

-- atualizacao dos novos campos com base no anexo VII
UPDATE INDICADOR_OPERACAO_IBS_CBS SET
    IOIC_TIPO_OPERACAO = CASE IOIC_CD
        WHEN '020101' THEN 'Operação com bem imóvel, bem imaterial, inclusive direito, relacionada a bem imóvel'
        WHEN '020201' THEN 'Serviço prestado fisicamente sobre bem imóvel'
        WHEN '020301' THEN 'Serviço de administração e intermediação de bem imóvel'
        WHEN '030101' THEN 'Serviço prestado fisicamente sobre a pessoa ou fruído presencialmente por pessoa física'
        WHEN '030102' THEN 'Serviço prestado fisicamente sobre a pessoa ou fruído presencialmente por pessoa física'
        WHEN '030103' THEN 'Serviço prestado fisicamente sobre a pessoa ou fruído presencialmente por pessoa física'
        WHEN '030104' THEN 'Serviço prestado fisicamente sobre a pessoa ou fruído presencialmente por pessoa física'
        WHEN '040101' THEN 'Serviço de planejamento, organização e administração de feiras, exposições, congressos, espetáculos, exibições e congêneres'
        WHEN '050101' THEN 'Serviço prestado fisicamente sobre bem móvel material'
        WHEN '050102' THEN 'Serviço prestado fisicamente sobre bem móvel material'
        WHEN '050103' THEN 'Serviço prestado fisicamente sobre bem móvel material'
        WHEN '050104' THEN 'Serviço prestado fisicamente sobre bem móvel material'
        WHEN '050201' THEN 'Serviços portuários'
        WHEN '060101' THEN 'Serviço de transporte de passageiros'
        WHEN '070101' THEN 'Serviço de transporte de carga'
        WHEN '070102' THEN 'Serviço de transporte de carga'
        WHEN '080101' THEN 'Serviço de exploração de via'
        WHEN '100101' THEN 'Cessão de espaço para prestação de serviços publicitários, em operações onerosas'
        WHEN '100102' THEN 'Cessão de espaço para prestação de serviços publicitários, em operações onerosas'
        WHEN '100201' THEN 'Cessão de espaço para prestação de serviços publicitários, em operações não onerosas'
        WHEN '100301' THEN 'Demais serviços, em operações onerosas'
        WHEN '100302' THEN 'Demais serviços, em operações onerosas'
        WHEN '100401' THEN 'Demais serviços, em operações não onerosas'
        WHEN '100501' THEN 'Demais bens móveis imateriais, inclusive direitos, em operações onerosas'
        WHEN '100502' THEN 'Demais bens móveis imateriais, inclusive direitos, em operações onerosas'
        WHEN '100601' THEN 'Demais bens móveis imateriais, inclusive direitos, em operações não onerosas'
        ELSE IOIC_TIPO_OPERACAO
    END,
    IOIC_CD_LOCAL_FORNECIMENTO_DFE = CASE IOIC_CD
        WHEN '020101' THEN 14
        WHEN '020201' THEN 14
        WHEN '020301' THEN 14
        WHEN '030101' THEN 5
        WHEN '030102' THEN 2
        WHEN '030103' THEN 3
        WHEN '030104' THEN 1
        WHEN '040101' THEN 13
        WHEN '050101' THEN 5
        WHEN '050102' THEN 2
        WHEN '050103' THEN 3
        WHEN '050104' THEN 1
        WHEN '050201' THEN 6
        WHEN '060101' THEN 9
        WHEN '070101' THEN 4
        WHEN '070102' THEN 8
        WHEN '080101' THEN 7
        WHEN '100101' THEN 11
        WHEN '100102' THEN 10
        WHEN '100201' THEN 12
        WHEN '100301' THEN 11
        WHEN '100302' THEN 10
        WHEN '100401' THEN 12
        WHEN '100501' THEN 11
        WHEN '100502' THEN 10
        WHEN '100601' THEN 12
        ELSE IOIC_CD_LOCAL_FORNECIMENTO_DFE
    END
WHERE IOIC_CD IN (
    '020101','020201','020301','030101','030102','030103','030104','040101',
    '050101','050102','050103','050104','050201','060101','070101','070102',
    '080101','100101','100102','100201','100301','100302','100401','100501',
    '100502','100601'
);
