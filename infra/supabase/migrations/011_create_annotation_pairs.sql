-- Annotation pairs: label-to-field pairings for the annotation tool.

CREATE TABLE IF NOT EXISTS annotation_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    label_id TEXT NOT NULL,
    label_text TEXT NOT NULL,
    label_bbox JSONB NOT NULL,
    label_page INTEGER NOT NULL,
    field_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_bbox JSONB NOT NULL,
    field_page INTEGER NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 100.0,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'flagged')),
    is_manual BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_annotation_pairs_document_id
    ON annotation_pairs (document_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_annotation_pairs_unique
    ON annotation_pairs (document_id, label_id, field_id);
