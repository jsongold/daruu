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
