-- ============================================================================
-- Prompt Attempts Migration
-- ============================================================================
-- Creates table for storing prompt tuning attempts (full request + raw LLM
-- response) so users can browse history on the /prompting page.
-- ============================================================================

-- ============================================================================
-- Table: prompt_attempts
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.prompt_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to conversation (stored as text since conversations are in-memory)
    conversation_id TEXT NOT NULL,

    -- Link to target document
    document_id TEXT NOT NULL,

    -- Prompts sent to the LLM
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,

    -- Custom rules that were active during the attempt
    custom_rules JSONB DEFAULT '[]'::jsonb,

    -- Raw LLM response (full text)
    raw_response TEXT NOT NULL DEFAULT '',

    -- Parsed result (structured JSON if parsing succeeded)
    parsed_result JSONB,

    -- Whether the attempt succeeded
    success BOOLEAN NOT NULL DEFAULT false,

    -- Error message if the attempt failed
    error TEXT,

    -- Metadata (model name, processing_time_ms, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for listing attempts by conversation, newest first
CREATE INDEX idx_prompt_attempts_conversation_created
    ON public.prompt_attempts(conversation_id, created_at DESC);

-- Trigger for updated_at
CREATE TRIGGER update_prompt_attempts_updated_at
    BEFORE UPDATE ON public.prompt_attempts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RLS Policies
-- ============================================================================

ALTER TABLE public.prompt_attempts ENABLE ROW LEVEL SECURITY;

-- Service role can manage all prompt attempts
CREATE POLICY "Service role can manage all prompt attempts"
    ON public.prompt_attempts
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE public.prompt_attempts IS 'Prompt tuning attempts storing full request/response for history';
COMMENT ON COLUMN public.prompt_attempts.conversation_id IS 'ID of the conversation this attempt belongs to';
COMMENT ON COLUMN public.prompt_attempts.document_id IS 'ID of the target document';
COMMENT ON COLUMN public.prompt_attempts.system_prompt IS 'System prompt sent to the LLM';
COMMENT ON COLUMN public.prompt_attempts.user_prompt IS 'User prompt sent to the LLM';
COMMENT ON COLUMN public.prompt_attempts.custom_rules IS 'Custom rules active during the attempt';
COMMENT ON COLUMN public.prompt_attempts.raw_response IS 'Raw LLM response text';
COMMENT ON COLUMN public.prompt_attempts.parsed_result IS 'Parsed result JSON (filled_fields, unfilled_fields, etc.)';
COMMENT ON COLUMN public.prompt_attempts.success IS 'Whether the attempt succeeded';
COMMENT ON COLUMN public.prompt_attempts.error IS 'Error message if the attempt failed';
COMMENT ON COLUMN public.prompt_attempts.metadata IS 'Additional metadata (model, processing_time_ms, etc.)';
