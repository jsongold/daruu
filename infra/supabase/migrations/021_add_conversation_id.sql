-- Migration 021: Add NOT NULL conversation_id to forms, form_schema, form_rules
-- Every write to these tables must be traceable to a conversation entry.

-- -----------------------------------------------------------------------
-- 1. forms: add column as nullable first
-- -----------------------------------------------------------------------

ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS conversation_id UUID
    REFERENCES conversations(id) ON DELETE CASCADE;

COMMENT ON COLUMN forms.conversation_id IS 'Conversation that created this form (upload)';

-- -----------------------------------------------------------------------
-- 2. Backfill: create a system conversation for each orphan form
--    conversations requires session_id, so we also create a placeholder session
-- -----------------------------------------------------------------------

-- 2a. Create placeholder sessions for forms that have no session
INSERT INTO sessions (id, form_id, user_info, mode, history, rules, created_at, updated_at)
SELECT
    f.id,           -- reuse form id as session id
    f.id,           -- form_id
    '{"data":{}}'::jsonb,
    'preview',
    '[]'::jsonb,
    '{"items":[]}'::jsonb,
    COALESCE(f.created_at, NOW()),
    COALESCE(f.updated_at, NOW())
FROM forms f
WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.form_id = f.id)
ON CONFLICT (id) DO NOTHING;

-- 2b. Create placeholder conversations for all forms without conversation_id
INSERT INTO conversations (id, session_id, role, content, created_at)
SELECT
    gen_random_uuid(),
    COALESCE(
        (SELECT s.id FROM sessions s WHERE s.form_id = f.id LIMIT 1),
        f.id
    ),
    'system',
    'Form uploaded (backfill)',
    COALESCE(f.created_at, NOW())
FROM forms f
WHERE f.conversation_id IS NULL;

-- 2c. Set conversation_id on forms from the placeholder conversations
UPDATE forms f
SET conversation_id = c.id
FROM conversations c
WHERE c.session_id = COALESCE(
        (SELECT s.id FROM sessions s WHERE s.form_id = f.id LIMIT 1),
        f.id
    )
AND c.content = 'Form uploaded (backfill)'
AND f.conversation_id IS NULL;

-- -----------------------------------------------------------------------
-- 3. Set NOT NULL on all three tables
-- -----------------------------------------------------------------------

ALTER TABLE forms ALTER COLUMN conversation_id SET NOT NULL;

-- form_schema and form_rules: backfill any nulls, then set NOT NULL
UPDATE form_schema fs
SET conversation_id = (
    SELECT c.id FROM conversations c
    JOIN sessions s ON c.session_id = s.id
    WHERE s.form_id = fs.form_id
    ORDER BY c.created_at DESC LIMIT 1
)
WHERE fs.conversation_id IS NULL;

UPDATE form_rules fr
SET conversation_id = (
    SELECT c.id FROM conversations c
    JOIN sessions s ON c.session_id = s.id
    WHERE s.form_id = fr.form_id
    ORDER BY c.created_at DESC LIMIT 1
)
WHERE fr.conversation_id IS NULL;

ALTER TABLE form_schema ALTER COLUMN conversation_id SET NOT NULL;

ALTER TABLE form_rules ALTER COLUMN conversation_id SET NOT NULL;
