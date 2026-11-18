-- =====================================================
-- MIGRAÇÃO DE MANUTENÇÃO
-- Data: 2026-07-08
-- =====================================================

INSERT INTO VERSAO_BASE_DADO (VRBD_DATA, VRBD_VERSAO_BASE_DADO, VRBD_DESCRICAO) VALUES
(
    datetime('2026-07-08'),
    'V0039',
    'Ajustes na tabela NCM para incluir 20 novos registros e extinguir 5 registros.'
);

-------------------------------------------------------------------------------------------------
-- Descrição:
-- Ajustes na tabela NCM para incluir 20 novos registros e extinguir 5 registros.
-----------------------------------------------------------------------------------------------

INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('23099070','Preparações com um teor de vitamina B<sub>12</sub> igual ou superior a 0,1 %, mas não superior a 1 %, em peso, com suporte à base de carbonato de cálcio','2025-10-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('26011220','Em briquetes de volume igual ou superior a 4 cm³, mas não superior a 60 cm³','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('29159070','Ácidos perfluoroctanoicos e seus sais','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('39072992','Éter metalílico de poli(oxietileno) (HPEG)','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('590390','- Outros','2026-02-01','9999-12-31');
UPDATE NCM SET NCM_FIM_VIGENCIA='2026-01-31' WHERE NCM_CD='59039000';
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('59039010','De fios de poliéster, impregnados com uma ou mais resinas sintéticas, perceptíveis ou não à vista desarmada, e recobertos com uma ou mais resinas sintéticas perceptíveis à vista desarmada numa de suas faces, do tipo utilizado como suporte para fabricação de abrasivos (lixas), em rolos','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('59039090','Outros','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('650610','- Capacetes e artigos de uso semelhante, de proteção','2026-02-01','9999-12-31');
UPDATE NCM SET NCM_FIM_VIGENCIA='2026-01-31' WHERE NCM_CD='65061000';
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('65061010','Do tipo utilizado por bombeiros, com viseira e protetor facial incorporados','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('65061090','Outros','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('730630','- Outros, soldados, de seção circular, de ferro ou aço não ligado','2026-02-01','9999-12-31');
UPDATE NCM SET NCM_FIM_VIGENCIA='2026-01-31' WHERE NCM_CD='73063000';
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('73063010','De diâmetro exterior igual a 22,25 mm, espessura igual a 2,64 mm e comprimento igual a 448,2 mm','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('73063090','Outros','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('740610','- Pós de estrutura não lamelar','2026-02-01','9999-12-31');
UPDATE NCM SET NCM_FIM_VIGENCIA='2026-01-31' WHERE NCM_CD='74061000';
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('74061010','Com um teor, em peso, de chumbo igual ou superior a 9,5 %, mas inferior ou igual a 25,0 % e de estanho igual ou superior a 1,75 %, mas inferior ou igual a 11,0 %, sem outros elementos','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('74061020','Com um teor, em peso, de estanho igual ou superior a 7,0 %, mas inferior ou igual a 9,0 % e de níquel igual ou superior a 0,7 %, mas inferior ou igual a 1,3 %, sem outros elementos','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('74061090','Outros','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('76129020','Recipientes (cápsulas) para embalagem de café e produtos semelhantes, do tipo utilizado em máquinas para preparação de bebidas','2025-10-01','9999-12-31');
UPDATE NCM SET NCM_FIM_VIGENCIA='2026-01-31' WHERE NCM_CD='84129020';
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('85177120','Antenas próprias para estações-base de telefonia celular','2026-02-01','9999-12-31');
INSERT INTO NCM(NCM_CD,NCM_DESCRICAO,NCM_INICIO_VIGENCIA,NCM_FIM_VIGENCIA) VALUES('90189097','Aparelhos destinados a procedimentos cirúrgicos assistidos por robótica','2025-10-01','9999-12-31');

