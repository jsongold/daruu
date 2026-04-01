-- Migration 026: Replace annotation_pairs state table with unified append-only changelog.
-- Stores two kinds of changes:
--   kind='annotation' — spatial label-field pairing (existing purpose)
--   kind='fill'       — user correction of an LLM-filled field value (new)

-- Step 1: Rename old table for rollback safety
ALTER TABLE annotation_pairs RENAME TO annotation_pairs_v1_backup;

-- Step 2: Create new unified changelog table
CREATE TABLE form_annotation_pairs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id    UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    pair_id    UUID NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('annotation', 'fill')),
    operation  TEXT NOT NULL CHECK (operation IN ('added', 'removed')),
    role       TEXT NOT NULL,   -- 'label'|'field' for annotation; 'value' for fill
    value      TEXT NOT NULL,   -- label_text / field_name / filled value
    bbox       JSONB,           -- null for fill corrections
    page       INTEGER NOT NULL DEFAULT 1,
    field_id   TEXT,            -- set for annotation field role and all fill entries
    source     TEXT,            -- null for annotation; 'user_edit'|'user_delete' for fill
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_form_annotation_pairs_form_id
    ON form_annotation_pairs (form_id);

CREATE INDEX idx_form_annotation_pairs_pair_id
    ON form_annotation_pairs (pair_id);

CREATE INDEX idx_form_annotation_pairs_kind
    ON form_annotation_pairs (form_id, kind);

CREATE INDEX idx_form_annotation_pairs_form_created
    ON form_annotation_pairs (form_id, created_at DESC);

-- Step 3: Backfill existing annotation pairs as kind='annotation' added events.
-- pair_id = old annotation_pairs.id so form_mappings.annotation_id references stay valid.
INSERT INTO form_annotation_pairs
    (form_id, pair_id, kind, operation, role, value, bbox, page, field_id, created_at)
SELECT
    form_id,
    id,
    'annotation',
    'added',
    'label',
    label_text,
    label_bbox,
    label_page,
    NULL,
    created_at
FROM annotation_pairs_v1_backup;

INSERT INTO form_annotation_pairs
    (form_id, pair_id, kind, operation, role, value, bbox, page, field_id, created_at)
SELECT
    form_id,
    id,
    'annotation',
    'added',
    'field',
    field_name,
    field_bbox,
    field_page,
    field_id,
    created_at
FROM annotation_pairs_v1_backup;
