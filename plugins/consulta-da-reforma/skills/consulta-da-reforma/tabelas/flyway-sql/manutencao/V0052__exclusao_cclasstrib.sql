-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-08-28
-- =====================================================

-- *****************************************************************************************
-- ************** É OBRIGATÓRIO INCLUIR O REGISTRO NA TABELA VERSAO_BASE_DADO **************
-- *****************************************************************************************

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-08-28'),
    'V0052',
    'Exclusão da cClassTrib 000011 e suas dependências.'
);

-- 1. NBS_APLICAVEL (NBSA_ID=129) — NBS: 125080000
DELETE FROM NBS_APLICAVEL WHERE NBSA_ID = 129;

-- 2. TRATAMENTO_CLASSIFICACAO (TRCL_ID=149)
DELETE FROM TRATAMENTO_CLASSIFICACAO WHERE TRCL_ID = 149;

-- 3. FUNDAMENTACAO_CLASSIFICACAO (FDCL_ID=149)
DELETE FROM FUNDAMENTACAO_CLASSIFICACAO WHERE FDCL_ID = 149;

-- 4. FUNDAMENTACAO_LEGAL (FDLG_ID=149) — órfã após delete do FDCL
--    "Art. 412, VII" — nenhuma outra FDCL referencia este registro
DELETE FROM FUNDAMENTACAO_LEGAL WHERE FDLG_ID = 149;

-- 5. CLASSIFICACAO_TRIBUTARIA (CLTR_ID=149) — tabela alvo
DELETE FROM CLASSIFICACAO_TRIBUTARIA WHERE CLTR_ID = 149;


