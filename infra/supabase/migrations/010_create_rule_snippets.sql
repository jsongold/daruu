-- Migration: Create rule_snippets table (replaces rule_cache)
-- Stores persistent, searchable rule snippets with vector embeddings

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rule_snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    applicable_fields TEXT[] DEFAULT '{}',
    source_document TEXT,
    confidence FLOAT DEFAULT 1.0,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast document-based lookups
CREATE INDEX IF NOT EXISTS idx_rule_snippets_document_id
    ON rule_snippets (document_id);

-- HNSW index for fast approximate nearest-neighbor search on embeddings
CREATE INDEX IF NOT EXISTS idx_rule_snippets_embedding_hnsw
    ON rule_snippets USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
