-- Migration 020: Create prompt_raw table to store full prompt text per LLM call

CREATE TABLE IF NOT EXISTS prompt_raw (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_log_id   UUID        NOT NULL REFERENCES prompt_logs(id) ON DELETE CASCADE,
    system_prompt   TEXT        NOT NULL DEFAULT '',
    user_prompt     TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE prompt_raw IS 'Full prompt text for each LLM call, linked 1:1 to prompt_logs';
COMMENT ON COLUMN prompt_raw.prompt_log_id IS 'FK to prompt_logs; cascades on delete';
COMMENT ON COLUMN prompt_raw.system_prompt IS 'Exact system prompt string sent to the LLM';
COMMENT ON COLUMN prompt_raw.user_prompt IS 'Exact user prompt string sent to the LLM';

CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_raw_prompt_log_id ON prompt_raw(prompt_log_id);
CREATE INDEX IF NOT EXISTS idx_prompt_raw_created_at ON prompt_raw(created_at);
