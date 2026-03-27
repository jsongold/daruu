-- Migration 015: Create conversations table for UI activity log

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    content     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE conversations IS 'Per-session activity log entries (Map, Fill, Understand, Ask, user messages)';
COMMENT ON COLUMN conversations.role IS 'user | agent | system';
COMMENT ON COLUMN conversations.content IS 'Human-readable activity text shown in ChatWindow';

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at  ON conversations(session_id, created_at);
