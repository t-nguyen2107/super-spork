-- P2 migration: pgvector extension + contact_embeddings table
-- Run: Get-Content migration_p2.sql | docker exec -i crm_pg psql -U crm -d crm

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS contact_embeddings (
    contact_id  INT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
    embedding   vector(768)     NOT NULL,
    embed_text  TEXT            NOT NULL,
    model       TEXT            NOT NULL,
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contact_embeddings_hnsw
    ON contact_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'contact_embeddings';
