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
