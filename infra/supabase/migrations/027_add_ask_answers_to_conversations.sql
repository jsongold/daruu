ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS ask_answers JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN conversations.ask_answers IS 'Persisted conditional question answers: {"<question_text>": "<answer>"}';
