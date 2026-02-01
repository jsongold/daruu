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
-- Migration 002: Create indexes for performance optimization
-- This migration adds indexes to improve query performance.

-- =============================================================================
-- DOCUMENTS INDEXES
-- =============================================================================

-- Index for filtering by document type
CREATE INDEX IF NOT EXISTS idx_documents_type
    ON documents(document_type);

-- Index for ordering by creation time
CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON documents(created_at DESC);

-- =============================================================================
-- JOBS INDEXES
-- =============================================================================

-- Index for filtering by status (most common query)
CREATE INDEX IF NOT EXISTS idx_jobs_status
    ON jobs(status);

-- Index for finding jobs by source document
CREATE INDEX IF NOT EXISTS idx_jobs_source_document
    ON jobs(source_document_id)
    WHERE source_document_id IS NOT NULL;

-- Index for finding jobs by target document
CREATE INDEX IF NOT EXISTS idx_jobs_target_document
    ON jobs(target_document_id);

-- Index for ordering by creation time
CREATE INDEX IF NOT EXISTS idx_jobs_created_at
    ON jobs(created_at DESC);

-- Index for finding active jobs (not done/failed)
CREATE INDEX IF NOT EXISTS idx_jobs_active
    ON jobs(status, created_at DESC)
    WHERE status NOT IN ('done', 'failed');

-- =============================================================================
-- FIELDS INDEXES
-- =============================================================================

-- Index for finding fields by job (most common query)
CREATE INDEX IF NOT EXISTS idx_fields_job
    ON fields(job_id);

-- Index for finding fields by document
CREATE INDEX IF NOT EXISTS idx_fields_document
    ON fields(document_id);

-- Composite index for job + document lookups
CREATE INDEX IF NOT EXISTS idx_fields_job_document
    ON fields(job_id, document_id);

-- Index for finding fields by page within a document
CREATE INDEX IF NOT EXISTS idx_fields_document_page
    ON fields(document_id, page);

-- Index for finding fields with low confidence
CREATE INDEX IF NOT EXISTS idx_fields_low_confidence
    ON fields(job_id, confidence)
    WHERE confidence IS NOT NULL AND confidence < 0.7;

-- =============================================================================
-- MAPPINGS INDEXES
-- =============================================================================

-- Index for finding mappings by job
CREATE INDEX IF NOT EXISTS idx_mappings_job
    ON mappings(job_id);

-- Index for finding mappings by source field
CREATE INDEX IF NOT EXISTS idx_mappings_source_field
    ON mappings(source_field_id);

-- Index for finding unconfirmed mappings
CREATE INDEX IF NOT EXISTS idx_mappings_unconfirmed
    ON mappings(job_id, is_confirmed)
    WHERE is_confirmed = FALSE;

-- =============================================================================
-- EXTRACTIONS INDEXES
-- =============================================================================

-- Index for finding extractions by job
CREATE INDEX IF NOT EXISTS idx_extractions_job
    ON extractions(job_id);

-- Index for finding extractions by field
CREATE INDEX IF NOT EXISTS idx_extractions_field
    ON extractions(field_id);

-- =============================================================================
-- EVIDENCE INDEXES
-- =============================================================================

-- Index for finding evidence by field
CREATE INDEX IF NOT EXISTS idx_evidence_field
    ON evidence(field_id);

-- Index for finding evidence by document
CREATE INDEX IF NOT EXISTS idx_evidence_document
    ON evidence(document_id);

-- Index for filtering by evidence source
CREATE INDEX IF NOT EXISTS idx_evidence_source
    ON evidence(source);

-- =============================================================================
-- ISSUES INDEXES
-- =============================================================================

-- Index for finding issues by job
CREATE INDEX IF NOT EXISTS idx_issues_job
    ON issues(job_id);

-- Index for finding issues by field
CREATE INDEX IF NOT EXISTS idx_issues_field
    ON issues(field_id);

-- Index for finding unresolved issues
CREATE INDEX IF NOT EXISTS idx_issues_unresolved
    ON issues(job_id, severity)
    WHERE resolved_at IS NULL;

-- Index for filtering by severity
CREATE INDEX IF NOT EXISTS idx_issues_severity
    ON issues(severity, job_id);

-- =============================================================================
-- ACTIVITIES INDEXES
-- =============================================================================

-- Index for finding activities by job
CREATE INDEX IF NOT EXISTS idx_activities_job
    ON activities(job_id);

-- Index for ordering activities by timestamp
CREATE INDEX IF NOT EXISTS idx_activities_timestamp
    ON activities(job_id, timestamp DESC);

-- Index for finding activities by action type
CREATE INDEX IF NOT EXISTS idx_activities_action
    ON activities(action, job_id);

-- Index for finding activities related to a field
CREATE INDEX IF NOT EXISTS idx_activities_field
    ON activities(field_id)
    WHERE field_id IS NOT NULL;

-- =============================================================================
-- JSONB INDEXES (GIN indexes for JSON queries)
-- =============================================================================

-- GIN index for document metadata searches
CREATE INDEX IF NOT EXISTS idx_documents_meta_gin
    ON documents USING GIN (meta);

-- GIN index for job cost tracking queries
CREATE INDEX IF NOT EXISTS idx_jobs_cost_gin
    ON jobs USING GIN (cost);

-- GIN index for field bbox queries
CREATE INDEX IF NOT EXISTS idx_fields_bbox_gin
    ON fields USING GIN (bbox)
    WHERE bbox IS NOT NULL;

-- GIN index for activity details queries
CREATE INDEX IF NOT EXISTS idx_activities_details_gin
    ON activities USING GIN (details);
-- Migration 003: Create Row Level Security (RLS) policies
-- This migration enables RLS and creates security policies.
--
-- NOTE: These policies are designed for a multi-tenant scenario where
-- users are authenticated via Supabase Auth. Adjust as needed for your
-- specific authentication and authorization requirements.

-- =============================================================================
-- ENABLE ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- NOTE: Use auth.uid() directly in policies (provided by Supabase)
-- No custom helper functions needed in the auth schema
-- =============================================================================

-- =============================================================================
-- SERVICE ROLE POLICIES
-- Service role key bypasses RLS, but we add explicit policies for clarity.
-- These policies allow full access when using the service role key.
-- =============================================================================

-- Documents: Service role has full access
CREATE POLICY "service_role_documents_all"
    ON documents
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Jobs: Service role has full access
CREATE POLICY "service_role_jobs_all"
    ON jobs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Fields: Service role has full access
CREATE POLICY "service_role_fields_all"
    ON fields
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Mappings: Service role has full access
CREATE POLICY "service_role_mappings_all"
    ON mappings
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Extractions: Service role has full access
CREATE POLICY "service_role_extractions_all"
    ON extractions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Evidence: Service role has full access
CREATE POLICY "service_role_evidence_all"
    ON evidence
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Issues: Service role has full access
CREATE POLICY "service_role_issues_all"
    ON issues
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Activities: Service role has full access
CREATE POLICY "service_role_activities_all"
    ON activities
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- ANON ROLE POLICIES (Limited access for unauthenticated requests)
-- In most cases, anon should not have access. Enable specific policies
-- as needed for your application.
-- =============================================================================

-- By default, anon role has no access to any tables
-- Uncomment and modify these policies if you need public read access

-- Example: Allow public read access to documents (DISABLED BY DEFAULT)
-- CREATE POLICY "anon_documents_select"
--     ON documents
--     FOR SELECT
--     TO anon
--     USING (true);

-- =============================================================================
-- AUTHENTICATED USER POLICIES
-- These policies apply to authenticated users (using JWT from Supabase Auth).
-- Adjust these policies based on your application's authorization model.
-- =============================================================================

-- For now, authenticated users have full access to their own data.
-- In a production environment, you would typically:
-- 1. Add a user_id column to track ownership
-- 2. Create policies that restrict access to owned resources
-- 3. Implement team/organization-based access control

-- Documents: Authenticated users can read all documents for now
-- (In production, add user_id column and restrict access)
CREATE POLICY "authenticated_documents_select"
    ON documents
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "authenticated_documents_insert"
    ON documents
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "authenticated_documents_update"
    ON documents
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "authenticated_documents_delete"
    ON documents
    FOR DELETE
    TO authenticated
    USING (true);

-- Jobs: Authenticated users can access all jobs for now
CREATE POLICY "authenticated_jobs_select"
    ON jobs
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "authenticated_jobs_insert"
    ON jobs
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "authenticated_jobs_update"
    ON jobs
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "authenticated_jobs_delete"
    ON jobs
    FOR DELETE
    TO authenticated
    USING (true);

-- Fields: Access based on job access
CREATE POLICY "authenticated_fields_select"
    ON fields
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "authenticated_fields_insert"
    ON fields
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "authenticated_fields_update"
    ON fields
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "authenticated_fields_delete"
    ON fields
    FOR DELETE
    TO authenticated
    USING (true);

-- Mappings: Access based on job access
CREATE POLICY "authenticated_mappings_all"
    ON mappings
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Extractions: Access based on job access
CREATE POLICY "authenticated_extractions_all"
    ON extractions
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Evidence: Access based on field access
CREATE POLICY "authenticated_evidence_all"
    ON evidence
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Issues: Access based on job access
CREATE POLICY "authenticated_issues_all"
    ON issues
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Activities: Read-only for authenticated users (system writes)
CREATE POLICY "authenticated_activities_select"
    ON activities
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "authenticated_activities_insert"
    ON activities
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- =============================================================================
-- STORAGE POLICIES (Supabase Storage RLS)
-- These are separate from table RLS and are configured in the Supabase dashboard
-- or via the storage API. Include them here as documentation.
-- =============================================================================

-- Storage bucket policies should be configured to:
--
-- documents bucket:
--   - Authenticated users can upload PDF files
--   - Authenticated users can read their own documents
--   - Service role has full access
--
-- previews bucket:
--   - Authenticated users can read preview images
--   - Service role can write preview images
--
-- crops bucket:
--   - Authenticated users can read crop images
--   - Service role can write crop images
--
-- outputs bucket:
--   - Authenticated users can read output PDFs
--   - Service role can write output PDFs

-- =============================================================================
-- NOTES FOR PRODUCTION
-- =============================================================================

-- 1. Add user_id column to documents, jobs tables:
--    ALTER TABLE documents ADD COLUMN user_id UUID REFERENCES auth.users(id);
--    ALTER TABLE jobs ADD COLUMN user_id UUID REFERENCES auth.users(id);
--
-- 2. Update policies to check ownership:
--    CREATE POLICY "users_own_documents" ON documents
--    FOR ALL TO authenticated
--    USING (user_id = auth.uid())
--    WITH CHECK (user_id = auth.uid());
--
-- 3. Consider adding organization/team support for shared access
--
-- 4. Implement audit logging for sensitive operations
