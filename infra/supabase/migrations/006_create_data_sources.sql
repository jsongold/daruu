-- ============================================================================
-- Data Sources Migration
-- ============================================================================
-- Creates tables for storing data sources used by the agent for auto-filling
-- form fields. Data sources can be PDFs, images, text files, or CSV files.
-- ============================================================================

-- ============================================================================
-- Table: data_sources
-- ============================================================================
-- Stores metadata and content for data sources uploaded by users
-- These are used by the AI agent to extract information for filling forms

CREATE TABLE IF NOT EXISTS public.data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to conversation (stored as text since conversations are in-memory)
    conversation_id TEXT NOT NULL,

    -- Data source type
    type TEXT NOT NULL CHECK (type IN ('pdf', 'image', 'text', 'csv')),

    -- Display name (original filename or user-provided)
    name TEXT NOT NULL,

    -- For file-based sources, link to documents table
    document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,

    -- For text/csv sources, store content directly
    text_content TEXT,

    -- Preview of content (first 500 chars for display)
    content_preview TEXT,

    -- Cached extraction results from AI processing
    extracted_data JSONB DEFAULT '{}'::jsonb,

    -- File metadata
    file_size_bytes INTEGER,
    mime_type TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT data_sources_name_not_empty CHECK (name != ''),
    CONSTRAINT data_sources_content_check CHECK (
        -- Either document_id or text_content must be set (but not both)
        (document_id IS NOT NULL AND text_content IS NULL) OR
        (document_id IS NULL AND text_content IS NOT NULL) OR
        (document_id IS NULL AND text_content IS NULL AND type IN ('pdf', 'image'))
    )
);

-- Indexes for efficient queries
CREATE INDEX idx_data_sources_conversation_id ON public.data_sources(conversation_id);
CREATE INDEX idx_data_sources_type ON public.data_sources(type);
CREATE INDEX idx_data_sources_document_id ON public.data_sources(document_id);
CREATE INDEX idx_data_sources_created_at ON public.data_sources(created_at DESC);

-- Trigger for updated_at
CREATE TRIGGER update_data_sources_updated_at
    BEFORE UPDATE ON public.data_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RLS Policies
-- ============================================================================

-- Enable RLS
ALTER TABLE public.data_sources ENABLE ROW LEVEL SECURITY;

-- For now, allow all operations (will add user-based policies when auth is integrated)
-- Service role can manage all data sources
CREATE POLICY "Service role can manage all data sources"
    ON public.data_sources
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE public.data_sources IS 'Data sources (PDF, images, text, CSV) used for AI form filling';
COMMENT ON COLUMN public.data_sources.conversation_id IS 'ID of the conversation this data source belongs to';
COMMENT ON COLUMN public.data_sources.type IS 'Type of data source: pdf, image, text, csv';
COMMENT ON COLUMN public.data_sources.name IS 'Display name (usually original filename)';
COMMENT ON COLUMN public.data_sources.document_id IS 'Reference to documents table for file-based sources';
COMMENT ON COLUMN public.data_sources.text_content IS 'Direct text content for text/csv sources';
COMMENT ON COLUMN public.data_sources.content_preview IS 'First 500 characters for preview display';
COMMENT ON COLUMN public.data_sources.extracted_data IS 'Cached AI extraction results in JSONB format';
