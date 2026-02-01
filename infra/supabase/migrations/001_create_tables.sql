-- Migration 001: Create core tables for daru-pdf
-- This migration creates the primary tables for document processing workflow.

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- DOCUMENTS TABLE
-- Stores document metadata for source and target PDFs
-- =============================================================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ref TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN ('source', 'target')),

    -- Metadata (stored as JSONB for flexibility)
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT documents_ref_not_empty CHECK (ref != '')
);

COMMENT ON TABLE documents IS 'Document metadata for source and target PDFs';
COMMENT ON COLUMN documents.id IS 'Unique document identifier (UUID)';
COMMENT ON COLUMN documents.ref IS 'Storage reference/path to the PDF file';
COMMENT ON COLUMN documents.document_type IS 'Type: source or target';
COMMENT ON COLUMN documents.meta IS 'Document metadata: page_count, file_size, mime_type, filename, has_password, has_acroform';

-- =============================================================================
-- JOBS TABLE
-- Stores job records for document processing workflows
-- =============================================================================

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode TEXT NOT NULL CHECK (mode IN ('transfer', 'scratch')),
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'running', 'blocked', 'awaiting_input', 'done', 'failed')),

    -- Document references
    source_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    target_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Processing state
    progress FLOAT NOT NULL DEFAULT 0.0 CHECK (progress >= 0.0 AND progress <= 1.0),
    current_step TEXT,
    current_stage TEXT,
    iteration_count INTEGER NOT NULL DEFAULT 0 CHECK (iteration_count >= 0),

    -- Next available actions (stored as JSON array)
    next_actions JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Cost tracking (stored as JSONB for flexibility)
    cost JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Configuration overrides
    rules JSONB,
    thresholds JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE jobs IS 'Job records for document processing workflows';
COMMENT ON COLUMN jobs.mode IS 'Processing mode: transfer (source to target) or scratch (fill from empty)';
COMMENT ON COLUMN jobs.status IS 'Current job status: created, running, blocked, awaiting_input, done, failed';
COMMENT ON COLUMN jobs.progress IS 'Job progress from 0.0 to 1.0';
COMMENT ON COLUMN jobs.cost IS 'Cost tracking summary: LLM tokens, OCR pages, storage bytes';

-- =============================================================================
-- FIELDS TABLE
-- Stores form fields detected/created for documents
-- =============================================================================

CREATE TABLE IF NOT EXISTS fields (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Field properties
    name TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text' CHECK (field_type IN ('text', 'number', 'date', 'checkbox', 'radio', 'signature', 'image', 'unknown')),
    value TEXT,
    confidence FLOAT CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),

    -- Location
    bbox JSONB,
    page INTEGER NOT NULL CHECK (page >= 1),

    -- Flags
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_editable BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fields_name_not_empty CHECK (name != '')
);

COMMENT ON TABLE fields IS 'Form fields detected or created for documents';
COMMENT ON COLUMN fields.field_type IS 'Field type: text, number, date, checkbox, radio, signature, image, unknown';
COMMENT ON COLUMN fields.bbox IS 'Bounding box: {x, y, width, height, page}';
COMMENT ON COLUMN fields.confidence IS 'Confidence score for extracted value (0.0-1.0)';

-- =============================================================================
-- MAPPINGS TABLE
-- Stores mappings between source and target fields
-- =============================================================================

CREATE TABLE IF NOT EXISTS mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source_field_id UUID NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    target_field_id UUID NOT NULL REFERENCES fields(id) ON DELETE CASCADE,

    -- Mapping properties
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one mapping per target field per job
    CONSTRAINT mappings_unique_target UNIQUE (job_id, target_field_id)
);

COMMENT ON TABLE mappings IS 'Mappings between source and target fields';
COMMENT ON COLUMN mappings.confidence IS 'Confidence score for this mapping (0.0-1.0)';
COMMENT ON COLUMN mappings.is_confirmed IS 'Whether mapping was confirmed by user';

-- =============================================================================
-- EXTRACTIONS TABLE
-- Stores extracted values for fields
-- =============================================================================

CREATE TABLE IF NOT EXISTS extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    field_id UUID NOT NULL REFERENCES fields(id) ON DELETE CASCADE,

    -- Extraction properties
    value TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE extractions IS 'Extracted values for fields';
COMMENT ON COLUMN extractions.evidence_ids IS 'Array of evidence IDs supporting this extraction';

-- =============================================================================
-- EVIDENCE TABLE
-- Stores evidence supporting field extractions
-- =============================================================================

CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    field_id UUID NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Evidence properties
    source TEXT NOT NULL CHECK (source IN ('ocr', 'llm', 'user', 'acroform', 'rule')),
    bbox JSONB,
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    text TEXT,

    -- Additional context
    rationale TEXT,
    page INTEGER CHECK (page IS NULL OR page >= 1),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE evidence IS 'Evidence supporting field extractions';
COMMENT ON COLUMN evidence.source IS 'Evidence source: ocr, llm, user, acroform, rule';
COMMENT ON COLUMN evidence.rationale IS 'LLM rationale or explanation for the extraction';

-- =============================================================================
-- ISSUES TABLE
-- Stores validation issues and problems with fields
-- =============================================================================

CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    field_id UUID NOT NULL REFERENCES fields(id) ON DELETE CASCADE,

    -- Issue properties
    issue_type TEXT NOT NULL CHECK (issue_type IN ('low_confidence', 'missing_value', 'validation_error', 'mapping_ambiguous', 'format_mismatch', 'layout_issue')),
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'high', 'critical', 'error')),
    message TEXT NOT NULL,
    suggested_action TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT issues_message_not_empty CHECK (message != '')
);

COMMENT ON TABLE issues IS 'Validation issues and problems with fields';
COMMENT ON COLUMN issues.issue_type IS 'Type: low_confidence, missing_value, validation_error, mapping_ambiguous, format_mismatch, layout_issue';
COMMENT ON COLUMN issues.severity IS 'Severity: info, warning, high, critical, error';

-- =============================================================================
-- ACTIVITIES TABLE
-- Stores activity timeline for jobs
-- =============================================================================

CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Activity properties
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    field_id UUID REFERENCES fields(id) ON DELETE SET NULL,

    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE activities IS 'Activity timeline for jobs';
COMMENT ON COLUMN activities.action IS 'Activity action type (e.g., job_created, field_extracted, etc.)';
COMMENT ON COLUMN activities.details IS 'Additional details about the activity';

-- =============================================================================
-- TRIGGER: Update updated_at timestamp
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at column
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_fields_updated_at
    BEFORE UPDATE ON fields
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
