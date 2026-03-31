-- Migration 025: Make conversation_id NOT NULL on form_mappings and prompt_logs

-- Step 1: Delete orphan prompt_logs with NULL conversation_id (no way to reliably backfill)
DELETE FROM prompt_logs WHERE conversation_id IS NULL;

-- Step 2: Set NOT NULL on form_mappings (already has 0 NULLs)
ALTER TABLE form_mappings ALTER COLUMN conversation_id SET NOT NULL;

-- Step 3: Drop old FK on prompt_logs conversation_id (named session_id_fkey from rename)
--         and recreate with ON DELETE CASCADE
ALTER TABLE prompt_logs DROP CONSTRAINT prompt_logs_session_id_fkey;
ALTER TABLE prompt_logs
    ADD CONSTRAINT prompt_logs_conversation_id_cascade_fkey
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE;

-- Step 4: Set NOT NULL on prompt_logs
ALTER TABLE prompt_logs ALTER COLUMN conversation_id SET NOT NULL;
