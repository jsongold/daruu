-- Rename sessions -> conversations and conversations -> messages
-- Order matters to avoid name collisions.

-- Step 1: Rename conversations -> messages (free up the name)
ALTER TABLE conversations RENAME TO messages;
ALTER TABLE messages RENAME COLUMN session_id TO conversation_id;

-- Step 2: Rename sessions -> conversations
ALTER TABLE sessions RENAME TO conversations;

-- Step 3: Rename session_id FK columns on related tables
-- prompt_logs has both session_id and conversation_id, so rename conversation_id first
ALTER TABLE prompt_logs RENAME COLUMN conversation_id TO message_id;
ALTER TABLE prompt_logs RENAME COLUMN session_id TO conversation_id;

ALTER TABLE form_mappings RENAME COLUMN session_id TO conversation_id;

-- Step 4: Rename conversation_id on form_rules, form_schema, and forms (these pointed to old conversations = new messages)
ALTER TABLE form_rules RENAME COLUMN conversation_id TO message_id;
ALTER TABLE form_schema RENAME COLUMN conversation_id TO message_id;
ALTER TABLE forms RENAME COLUMN conversation_id TO message_id;

-- Step 5: Drop NOT NULL on message_id columns (code does not always set these)
ALTER TABLE forms ALTER COLUMN message_id DROP NOT NULL;
ALTER TABLE form_schema ALTER COLUMN message_id DROP NOT NULL;
ALTER TABLE form_rules ALTER COLUMN message_id DROP NOT NULL;
