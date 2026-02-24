-- Migration: 008_create_corrections
-- Creates corrections table for tracking user corrections to auto-filled values.

CREATE TABLE IF NOT EXISTS public.corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL,
    field_id TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    conversation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for listing corrections by document
CREATE INDEX IF NOT EXISTS idx_corrections_document_created
    ON public.corrections (document_id, created_at DESC);

-- RLS policy: service role bypass
ALTER TABLE public.corrections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role bypass for corrections"
    ON public.corrections
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
