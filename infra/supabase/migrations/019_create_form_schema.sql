-- Migration 019: Create form_rules and form_schema tables
-- form_rules: global rules per form (description, rulebook, structured rules)
-- form_schema: global field schema per form (JSONB array of fields)

-- Ensure pgvector extension is available (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------
-- form_rules: one row per form, holds rules + description
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS form_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id         UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    description     TEXT,
    rulebook_text   TEXT,
    rules           JSONB NOT NULL DEFAULT '[]'::jsonb,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT form_rules_unique_form UNIQUE (form_id)
);

COMMENT ON TABLE form_rules IS 'One row per form: global rules extracted by Understand mode';
COMMENT ON COLUMN form_rules.description IS 'LLM-generated English summary for semantic search';
COMMENT ON COLUMN form_rules.rulebook_text IS 'Full Markdown rulebook for human reading';
COMMENT ON COLUMN form_rules.rules IS 'JSONB array of structured RuleItem objects';
COMMENT ON COLUMN form_rules.conversation_id IS 'Conversation entry that triggered the last update';

CREATE INDEX IF NOT EXISTS idx_form_rules_form_id ON form_rules(form_id);

CREATE OR REPLACE TRIGGER form_rules_updated_at
    BEFORE UPDATE ON form_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------
-- form_schema: one row per form, JSONB field array + FK to form_rules
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS form_schema (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id         UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    form_name       TEXT,
    form_rules_id   UUID REFERENCES form_rules(id) ON DELETE SET NULL,
    schema          JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding       VECTOR(1536),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    updated_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT form_schema_unique_form UNIQUE (form_id)
);

COMMENT ON TABLE form_schema IS 'One row per form: consolidated field schema built by annotate + map operations';
COMMENT ON COLUMN form_schema.form_name IS 'LLM-detected form name (e.g. I-130, W-2)';
COMMENT ON COLUMN form_schema.form_rules_id IS 'FK to form_rules for this form';
COMMENT ON COLUMN form_schema.schema IS 'JSONB array of field objects with label, semantic_key, bbox, etc.';
COMMENT ON COLUMN form_schema.embedding IS 'pgvector embedding of form_name + description + semantic_keys for RAG similarity search';
COMMENT ON COLUMN form_schema.conversation_id IS 'Conversation entry that triggered the last update';
COMMENT ON COLUMN form_schema.updated_by IS 'Session that last updated this row (NULL for form-level ops like Map)';

CREATE INDEX IF NOT EXISTS idx_form_schema_form_id ON form_schema(form_id);
CREATE INDEX IF NOT EXISTS idx_form_schema_embedding
    ON form_schema USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE OR REPLACE TRIGGER form_schema_updated_at
    BEFORE UPDATE ON form_schema
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------
-- Backfill form_schema from existing field_label_maps + annotation_pairs
-- -----------------------------------------------------------------------

INSERT INTO form_schema (form_id, schema)
SELECT
    flm.form_id,
    jsonb_agg(
        jsonb_build_object(
            'field_id', flm.field_id,
            'field_name', flm.field_name,
            'field_type', 'text',
            'bbox', null,
            'page', 1,
            'default_value', null,
            'label_text', COALESCE(ap.label_text, flm.label_text),
            'label_source', CASE
                WHEN ap.label_text IS NOT NULL THEN 'annotation'
                WHEN flm.source = 'manual' THEN 'map_manual'
                ELSE 'map_auto'
            END,
            'label_bbox', ap.label_bbox,
            'label_page', ap.label_page,
            'semantic_key', flm.semantic_key,
            'confidence', flm.confidence,
            'is_confirmed', CASE WHEN ap.label_text IS NOT NULL THEN true ELSE false END
        )
    )
FROM (
    SELECT DISTINCT ON (form_id, field_id)
        form_id, field_id, field_name, label_text, semantic_key, confidence, source
    FROM field_label_maps
    ORDER BY form_id, field_id, created_at DESC
) flm
LEFT JOIN (
    SELECT DISTINCT ON (form_id, field_id)
        form_id, field_id, label_text, label_bbox, label_page
    FROM annotation_pairs
    ORDER BY form_id, field_id, created_at DESC
) ap ON ap.form_id = flm.form_id AND ap.field_id = flm.field_id
GROUP BY flm.form_id
ON CONFLICT (form_id) DO NOTHING;
