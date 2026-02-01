-- Migration 004: Make issue field_id nullable for stage-level issues
-- This allows issues to be created without a specific field reference,
-- which is needed for ingest-stage errors and other stage-level issues.

-- Drop the existing foreign key constraint first
ALTER TABLE issues
DROP CONSTRAINT IF EXISTS issues_field_id_fkey;

-- Make field_id nullable
ALTER TABLE issues
ALTER COLUMN field_id DROP NOT NULL;

-- Re-add the foreign key constraint with ON DELETE SET NULL
-- This ensures that if a field is deleted, the issue remains but loses its field reference
ALTER TABLE issues
ADD CONSTRAINT issues_field_id_fkey
FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE SET NULL;

-- Add a comment explaining the nullable field_id
COMMENT ON COLUMN issues.field_id IS 'ID of field with issue (nullable for stage-level issues that are not field-specific)';
