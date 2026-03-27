-- Migration 013: field_label_maps table for Map mode
-- Stores LLM-identified label-to-field associations (structural form knowledge)

CREATE TABLE IF NOT EXISTS field_label_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    field_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    label_text TEXT,           -- identified label text (null if no match found)
    semantic_key TEXT,         -- English snake_case semantic name, e.g. "applicant_name"
    confidence INT DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 100),
    source TEXT DEFAULT 'auto' CHECK (source IN ('auto', 'manual')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE field_label_maps IS 'LLM-identified label-to-field mappings produced by Map mode';
COMMENT ON COLUMN field_label_maps.field_id IS 'AcroForm field identifier (UUID assigned at extraction time)';
COMMENT ON COLUMN field_label_maps.field_name IS 'AcroForm field name string';
COMMENT ON COLUMN field_label_maps.label_text IS 'Text block identified as the label for this field';
COMMENT ON COLUMN field_label_maps.semantic_key IS 'English snake_case description of the field purpose';
COMMENT ON COLUMN field_label_maps.confidence IS '0-100 confidence from LLM';
COMMENT ON COLUMN field_label_maps.source IS 'auto = Map mode LLM; manual = promoted from annotation';

CREATE INDEX IF NOT EXISTS idx_field_label_maps_document_id ON field_label_maps(document_id);

-- Update sessions mode constraint to include 'map'
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_mode_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_mode_check
    CHECK (mode IN ('preview', 'edit', 'annotate', 'map', 'fill', 'ask'));
