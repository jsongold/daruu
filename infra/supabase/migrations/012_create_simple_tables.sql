-- Migration 012: Create tables for the simplified annotation/fill app

-- =============================================================================
-- SESSIONS TABLE
-- Stores ContextWindow state for the simplified app
-- =============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    user_info JSONB DEFAULT '{}'::jsonb,
    mode TEXT NOT NULL DEFAULT 'preview' CHECK (mode IN ('preview', 'edit', 'annotate', 'fill', 'ask')),
    history JSONB DEFAULT '[]'::jsonb,
    rules JSONB DEFAULT '{"items": []}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sessions IS 'ContextWindow persistence for the simplified annotation/fill app';
COMMENT ON COLUMN sessions.mode IS 'Active mode: preview, edit, annotate, fill, ask';
COMMENT ON COLUMN sessions.history IS 'Conversation/action history as JSON array';
COMMENT ON COLUMN sessions.rules IS 'Rule set JSON with items array';

-- Reuse the existing update_updated_at_column() function from migration 001
CREATE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- FORM_MAPPINGS TABLE
-- Simplified annotation-to-field mappings (no job dependency)
-- =============================================================================

CREATE TABLE IF NOT EXISTS form_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    annotation_id TEXT NOT NULL,
    field_id TEXT NOT NULL,
    inferred_value TEXT,
    confidence FLOAT DEFAULT 0.0,
    reason TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE form_mappings IS 'Simplified annotation-to-field mappings for the form fill tool';
COMMENT ON COLUMN form_mappings.annotation_id IS 'References annotation_pairs.label_id or similar annotation identifier';
COMMENT ON COLUMN form_mappings.field_id IS 'Form field identifier (acroform field name or generated ID)';
COMMENT ON COLUMN form_mappings.confidence IS 'Confidence score 0.0-1.0 for the inferred mapping';

CREATE INDEX IF NOT EXISTS idx_form_mappings_session_id ON form_mappings(session_id);
