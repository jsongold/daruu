-- Migration 016: Add form_values to sessions table

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS form_values JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN sessions.form_values IS 'Persisted fill results: {"<field_id>": "<value>"}';
