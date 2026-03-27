-- Add 'rules' to the allowed mode values for sessions
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_mode_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_mode_check
  CHECK (mode IN ('preview', 'edit', 'annotate', 'map', 'fill', 'ask', 'rules'));
