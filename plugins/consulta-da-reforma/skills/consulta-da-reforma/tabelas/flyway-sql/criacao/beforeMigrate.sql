-- =====================================================
-- CALLBACK FLYWAY: beforeMigrate.sql
-- Executado UMA única vez por ambiente, no início do "flyway:migrate",
-- antes do baseline B0001 e de todas as migrações V*. Não roda antes de
-- cada migração (isso seria o callback beforeEachMigrate).
-- Como o Flyway usa uma única conexão para o SQLite, os PRAGMAs abaixo
-- valem para toda a geração do banco. O script roda fora de transação
-- porque contém "PRAGMA foreign_keys".
-- Gerado em: 2025-09-24 / cabeçalho revisado em: 2026-09-04
-- =====================================================

-- Configurações essenciais de encoding
PRAGMA encoding = 'UTF-8';
-- Checagem de chave estrangeira. Atenção: o B0001 desliga a checagem no seu
-- início e a religa no seu fim; é esse "PRAGMA foreign_keys = ON" do B0001
-- que vale para as migrações V0002 em diante.
PRAGMA foreign_keys = ON;

-- Modo de journal. Fica gravado dentro do arquivo .db, então vale para quem
-- abrir o banco depois. O banco é distribuído somente leitura: o modo WAL não
-- traz benefício e deixa arquivos -wal/-shm ao lado do .db (uma conexão
-- mode=ro não consegue apagá-los) e falha em diretório sem escrita.
PRAGMA journal_mode = DELETE;

-- Configurações de performance (valem só para a conexão desta geração)
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = 10000;
PRAGMA page_size = 4096;
PRAGMA mmap_size = 268435456; -- 256MB

-- Configurações de integridade
PRAGMA recursive_triggers = ON;
PRAGMA case_sensitive_like = OFF;
PRAGMA secure_delete = OFF;
PRAGMA trusted_schema = ON;

-- =====================================================
-- PRAGMA statements configurados com sucesso
-- =====================================================
