-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-12
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-12'),
    'V0051',
    'Habilitação dos documentos das NTs 2026.003 (CT-e, CT-e OS, BP-e, BP-e TM e NFCom) para o cálculo do Simples Nacional: carga da whitelist global de documentos e dos vínculos atividade × documento (atividade 05 nos documentos de transporte, atividade 06 na NFCom e código 90 em todos).'
);

-- -----------------------------------------------------------------------------------------------
-- Descrição:
-- 1. Inclusão na whitelist global TIPO_DFE_CALCULO_SIMPLES_NACIONAL dos documentos com NT
--    2026.003 publicada (CT-e, CT-e OS, BP-e, BP-e TM e NFCom)
-- 2. Carga dos vínculos na associativa TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL:
--      - atividade 05 (transporte intermunicipal/interestadual, Anexo III): CT-e, CT-e OS,
--        BP-e e BP-e TM;
--      - atividade 06 (serviços de comunicação, Anexo III): NFCom;
--      - código 90 (Operações não Tributáveis): todos os cinco documentos.
--
-- FONTE (fato afirmativo publicado, conforme o racional de whitelist da V0045):
--   - NT 2026.003 do CT-e (v1.00, 03/06/2026): leiautes dos modelos 57 e 67 (CT-e e CT-e OS);
--     "Caso a operação tpRBSN = 1,2,3,4 ou 5: cAtivSN = 5 (...). Caso tpRBSN 0: cAtivSN = 90";
--   - NT 2026.003 do BP-e (v1.00, 03/06/2026): leiautes do BP-e e do BP-e Transporte
--     Metropolitano; mesmos cAtivSN 5 e 90;
--   - NT 2026.003 da NFCom (v1.00, 03/06/2026): leiaute do modelo 62;
--     "cAtivSN = 6 (...) - Anexo III" e cAtivSN = 90 para tpRBSN 0.
--
-- EXCLUSÕES DELIBERADAS (sem publicação, sem permissão — whitelist falha para o lado seguro):
--   - CT-e Simplificado (tpDoc 97, TPDF_ID 16): a NT do CT-e delimita seu objeto a
--     "leiautes do CTe e do CTeOS (modelos 57 e 67)" e não menciona o leiaute simplificado.
--     Se NT futura (ou errata) o abranger, a habilitação são dois INSERTs monotônicos;
--   - BP-e TA - Transporte Aéreo (tpDoc 83, TPDF_ID 7): a NT do BP-e abrange "BPe e BPe
--     Transporte Metropolitano"; o transporte aéreo não é citado;
--   - GTVe: figura na capa da NT do CT-e, mas não é tratado no corpo (não possui valor de
--     prestação);
--   - atividade 10 (transporte municipal, subitem 16.01): as NTs publicam apenas o
--     cAtivSN 5 (intermunicipal/interestadual); a atividade 10 permanece sem vínculo.
--
-- VIGÊNCIA: 2027-01-01, alinhada às cargas da V0042/V0044/V0045 e à resolução pela data do
-- fato gerador. O cronograma de implantação das NTs (produção dos campos em 05/10/2026;
-- evento de tributação "A DEFINIR") disciplina os autorizadores/autorizadoras, não a
-- incidência do regime.
--
-- Referências de chaves (cargas da V0042/V0044):
--   TIPO_DFE: 4 = CT-e (57), 5 = CT-e OS (67), 6 = BP-e (63), 8 = BP-e TM (93),
--             12 = NFCom (62);
--   ATIVIDADE_SIMPLES_NACIONAL: 5 = cAtivSN '05', 6 = cAtivSN '06', 15 = cAtivSN '90'.
-- -----------------------------------------------------------------------------------------------

-- ==========================================================================================
-- 1. Whitelist global de documentos habilitados (TIPO_DFE_CALCULO_SIMPLES_NACIONAL)
-- ==========================================================================================
--
-- Continuação da carga da V0045 (ids 1-3: NF-e, NFC-e e NFS-e). tpDoc sem vínculo vigente
-- aqui é rejeitado com HTTP 422 (VSN-015) antes de qualquer item ser processado.

INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (4, 4,  '2027-01-01', NULL); -- CT-e    (tpDoc 57)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (5, 5,  '2027-01-01', NULL); -- CT-e OS (tpDoc 67)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (6, 6,  '2027-01-01', NULL); -- BP-e    (tpDoc 63)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (7, 8,  '2027-01-01', NULL); -- BP-e TM (tpDoc 93)
INSERT INTO TIPO_DFE_CALCULO_SIMPLES_NACIONAL VALUES (8, 12, '2027-01-01', NULL); -- NFCom   (tpDoc 62)

-- ==========================================================================================
-- 2. Vínculos atividade × documento (TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL)
-- ==========================================================================================
--
-- Continuação da carga da V0045 (ids 1-19). Todos os vínculos explícitos, por TIPO_DFE
-- individual (sem atalho via GRUPO_DFE), no padrão da carga anterior.

-- Atividade 05 - transporte intermunicipal e interestadual (Anexo III): primeiros vínculos
-- da atividade, publicados pelas NTs do CT-e e do BP-e.

INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (20, 5,  4,  '2027-01-01', NULL); -- atividade 05 x CT-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (21, 5,  5,  '2027-01-01', NULL); -- atividade 05 x CT-e OS
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (22, 5,  6,  '2027-01-01', NULL); -- atividade 05 x BP-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (23, 5,  8,  '2027-01-01', NULL); -- atividade 05 x BP-e TM

-- Atividade 06 - serviços de comunicação (Anexo III): primeiro vínculo da atividade,
-- publicado pela NT da NFCom.

INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (24, 6,  12, '2027-01-01', NULL); -- atividade 06 x NFCom

-- Código 90 - Operações não Tributáveis: as três NTs o atribuem para tpRBSN = 0 em todos
-- os documentos abrangidos.

INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (25, 15, 4,  '2027-01-01', NULL); -- código 90 x CT-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (26, 15, 5,  '2027-01-01', NULL); -- código 90 x CT-e OS
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (27, 15, 6,  '2027-01-01', NULL); -- código 90 x BP-e
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (28, 15, 8,  '2027-01-01', NULL); -- código 90 x BP-e TM
INSERT INTO TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL VALUES (29, 15, 12, '2027-01-01', NULL); -- código 90 x NFCom

-- Após esta migração, as atividades 05 e 06 deixam de ser as únicas do catálogo sem
-- vínculo (situação registrada no final da V0045): todas as atividades vigentes (01-14
-- e 90) passam a ter ao menos um vínculo. A observação sobre a atividade 10 no cabeçalho
-- refere-se apenas aos documentos DESTAS NTs (as NTs de transporte publicam somente o
-- cAtivSN 5): a atividade 10 permanece vinculada exclusivamente à NFS-e (V0045, id 14).

-- VERIFICAÇÃO (executar manualmente após a migração; deve retornar exatamente os pares
-- listados nos comentários acima):
--
-- SELECT A.ATSN_CATIVSN, T.TPDF_SIGLA
--   FROM TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL V
--   JOIN ATIVIDADE_SIMPLES_NACIONAL A ON A.ATSN_ID = V.TDAS_ATSN_ID
--   JOIN TIPO_DFE T ON T.TPDF_ID = V.TDAS_TPDF_ID
--  WHERE V.TDAS_ID >= 20
--  ORDER BY A.ATSN_CATIVSN, T.TPDF_TIPO;
