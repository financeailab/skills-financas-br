-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-06-25
-- =====================================================

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
   datetime('2026-06-25'),
   'V0036',
   'Nova tabela de Classificações Tributárias publicada em 23/06/2026 - somente alterações, as inclusões estão na V0035.'
);

-------------------------------------------------------------------------------------------------
-- Descrição:
-- Atualizações de Classificação Tributária e dependências.
-------------------------------------------------------------------------------------------------

-- ================================================
-- 1. Fim de vigência de classificações tributárias
-- ================================================
UPDATE CLASSIFICACAO_TRIBUTARIA
SET CLTR_FIM_VIGENCIA = '2026-01-01'
WHERE CLTR_ID IN (64, 65, 66);

-- ================================================
-- 2.  Fim de vigência das dependências
-- ================================================
UPDATE PERCENTUAL_REDUCAO
SET PERE_FIM_VIGENCIA = '2026-01-01'
WHERE PERE_CLTR_ID IN (64, 65, 66);

UPDATE TRATAMENTO_CLASSIFICACAO
SET TRCL_FIM_VIGENCIA = '2026-01-01'
WHERE TRCL_CLTR_ID IN (64, 65, 66);

UPDATE FUNDAMENTACAO_CLASSIFICACAO
SET FDCL_FIM_VIGENCIA = '2026-01-01'
WHERE FDCL_CLTR_ID IN (64, 65, 66);

UPDATE TIPO_DFE_CLASSIFICACAO
SET TDCL_FIM_VIGENCIA = '2026-01-01'
WHERE TDCL_CLTR_ID IN (64, 65, 66);

-- ==============================================
-- 3. Atualizações de Fundamentação Legal
-- ==============================================
UPDATE FUNDAMENTACAO_LEGAL
SET FDLG_TEXTO = 'Art. 26. Não são contribuintes do IBS e da CBS, ressalvado o disposto no\ninciso II do § 1º do art. 156-A da Constituição Federal:\nI – condomínio edilício;\n§ 2º Em relação ao condomínio edilício de que trata o inciso I do caput deste artigo:\nI – caso exerça a opção pelo regime regular de que trata o § 1º deste artigo, o IBS e a CBS incidirão sobre todas as taxas e demais valores cobrados pelo condomínio dos seus condôminos e de terceiros; e\nII – caso não exerça a opção pelo regime regular e desde que as taxas e demais valores condominiais cobrados de seus condôminos representem menos de 80% (oitenta por cento) da receita total do condomínio:\na) ficará sujeito à incidência do IBS e da CBS sobre as operações com bens e com serviços que realizar de acordo com o disposto no inciso I do caput do art. 21 desta Lei Complementar; e\nb) apropriará créditos na proporção da receita decorrente das operações tributadas na forma da alínea “a” deste inciso, em relação à receita total do condomínio.'
WHERE FDLG_ID = 81;

UPDATE FUNDAMENTACAO_LEGAL
SET FDLG_TEXTO = 'Art. 107. O Regime Tributário para Incentivo à Atividade Econômica Naval – Renaval permite aos beneficiários previamente habilitados suspensão do pagamento de IBS e CBS:\nI - nos fornecimentos de embarcações registradas ou pré-registradas no Registro Especial Brasileiro - REB instituído pelo art. 11 da Lei nº 9.432, de 8 de janeiro de 1997, para incorporação ao ativo imobilizado de adquirente sujeito ao regime regular do IBS e da CBS;'
WHERE FDLG_ID = 115;

UPDATE FUNDAMENTACAO_LEGAL
SET FDLG_TEXTO = 'Art. 450. São concedidos à indústria incentivada na Zona Franca de Manaus créditos presumidos de IBS e de CBS relativos à operação que destine ao território nacional, inclusive para a própria Zona Franca de Manaus, bem material produzido pela própria indústria incentivada na referida área nos termos do projeto econômico aprovado, exceto em relação às operações previstas no art. 448 desta Lei Complementar.\n§ 1º O crédito presumido de IBS de que trata o caput será calculado mediante a aplicação dos seguintes percentuais sobre o saldo devedor do IBS no período de apuração:'
WHERE FDLG_ID = 128;

-- ==============================================
-- 4. Atualizações de Classificação Tributária
-- ==============================================
UPDATE CLASSIFICACAO_TRIBUTARIA
SET CLTR_DESCRICAO = 'Regime Tributário para Incentivo à Atividade Naval - Renaval (Art. 107, I)'
WHERE CLTR_ID = 115;

UPDATE CLASSIFICACAO_TRIBUTARIA
SET CLTR_DESCRICAO = 'Documento com informações de fornecimento de serviço continuado, mas com tributação realizada em fatura anterior'
WHERE CLTR_ID = 175;

UPDATE CLASSIFICACAO_TRIBUTARIA
SET CLTR_IND_GMONOPADRAO = 0
WHERE CLTR_ID IN (122, 123);

-- ========================================================
-- 5. Ajustes na tabela associativa TIPO_DFE_CLASSIFICACAO
-- ========================================================
DELETE FROM TIPO_DFE_CLASSIFICACAO
WHERE (TDCL_CLTR_ID, TDCL_TPDF_ID) IN (
    (1, 8),
    (70, 8),
    (72, 8),
    (95, 8),
    (72, 11),
    (95, 11),
    (100, 2)
);

INSERT INTO TIPO_DFE_CLASSIFICACAO
    (TDCL_ID, TDCL_CLTR_ID, TDCL_TPDF_ID, TDCL_INICIO_VIGENCIA, TDCL_FIM_VIGENCIA)
VALUES
    (359, 31, 4, '2026-01-01', NULL);
