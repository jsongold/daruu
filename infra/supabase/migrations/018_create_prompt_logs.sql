-- Migration 018: Create prompt_logs table to record LLM API calls

CREATE TABLE IF NOT EXISTS prompt_logs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    conversation_id     UUID        REFERENCES conversations(id) ON DELETE SET NULL,
    type                TEXT        NOT NULL,
    prompt_template     TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    system_chars        INTEGER     NOT NULL DEFAULT 0,
    user_chars          INTEGER     NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE prompt_logs IS 'Records each LLM API call: which prompt template was used, for which session/conversation';
COMMENT ON COLUMN prompt_logs.type IS 'Mode that triggered the call: map | understand | fill | mapping_fallback';
COMMENT ON COLUMN prompt_logs.prompt_template IS 'Prompt class name: MapPrompt | RulesPrompt | FillPrompt | inline';
COMMENT ON COLUMN prompt_logs.model IS 'LLM model identifier (e.g. gpt-4o)';
COMMENT ON COLUMN prompt_logs.system_chars IS 'Character length of the system prompt sent to the LLM';
COMMENT ON COLUMN prompt_logs.user_chars IS 'Character length of the user prompt sent to the LLM';

CREATE INDEX IF NOT EXISTS idx_prompt_logs_session_id      ON prompt_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_conversation_id ON prompt_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_prompt_logs_created_at      ON prompt_logs(created_at);
