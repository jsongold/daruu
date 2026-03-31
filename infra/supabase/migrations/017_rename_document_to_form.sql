-- Migration 017: Rename "document" → "form" across schema
-- The uploaded PDF is a form, not a generic document.
-- Uses DO blocks to safely skip tables that don't exist in this instance.

-- =============================================================================
-- RENAME documents TABLE → forms
-- =============================================================================

ALTER TABLE documents RENAME TO forms;

-- Rename document_type column to form_type
ALTER TABLE forms RENAME COLUMN document_type TO form_type;
-- Update the check constraint (drop old, add new)
ALTER TABLE forms DROP CONSTRAINT IF EXISTS documents_type_check;
ALTER TABLE forms ADD CONSTRAINT forms_type_check CHECK (form_type IN ('source', 'target'));

-- =============================================================================
-- RENAME document_id COLUMNS IN DEPENDENT TABLES (safe, skip if not exists)
-- =============================================================================

-- sessions
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='document_id') THEN
    ALTER TABLE sessions RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- annotation_pairs
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='annotation_pairs' AND column_name='document_id') THEN
    ALTER TABLE annotation_pairs RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- field_label_maps
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='field_label_maps' AND column_name='document_id') THEN
    ALTER TABLE field_label_maps RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- jobs
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='source_document_id') THEN
    ALTER TABLE jobs RENAME COLUMN source_document_id TO source_form_id;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='target_document_id') THEN
    ALTER TABLE jobs RENAME COLUMN target_document_id TO target_form_id;
  END IF;
END $$;

-- fields
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fields' AND column_name='document_id') THEN
    ALTER TABLE fields RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- evidence
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='evidence' AND column_name='document_id') THEN
    ALTER TABLE evidence RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- data_sources
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='data_sources' AND column_name='document_id') THEN
    ALTER TABLE data_sources RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- corrections
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='corrections' AND column_name='document_id') THEN
    ALTER TABLE corrections RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- rule_snippets
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='rule_snippets' AND column_name='document_id') THEN
    ALTER TABLE rule_snippets RENAME COLUMN document_id TO form_id;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='rule_snippets' AND column_name='source_document') THEN
    ALTER TABLE rule_snippets RENAME COLUMN source_document TO source_form;
  END IF;
END $$;

-- prompt_attempts
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='prompt_attempts' AND column_name='document_id') THEN
    ALTER TABLE prompt_attempts RENAME COLUMN document_id TO form_id;
  END IF;
END $$;

-- =============================================================================
-- RENAME INDEXES (cosmetic, IF EXISTS is supported for indexes)
-- =============================================================================

ALTER INDEX IF EXISTS idx_documents_type RENAME TO idx_forms_type;
ALTER INDEX IF EXISTS idx_documents_created_at RENAME TO idx_forms_created_at;
ALTER INDEX IF EXISTS idx_documents_meta_gin RENAME TO idx_forms_meta_gin;
ALTER INDEX IF EXISTS idx_jobs_source_document RENAME TO idx_jobs_source_form;
ALTER INDEX IF EXISTS idx_jobs_target_document RENAME TO idx_jobs_target_form;
ALTER INDEX IF EXISTS idx_fields_document RENAME TO idx_fields_form;
ALTER INDEX IF EXISTS idx_fields_job_document RENAME TO idx_fields_job_form;
ALTER INDEX IF EXISTS idx_fields_document_page RENAME TO idx_fields_form_page;
ALTER INDEX IF EXISTS idx_evidence_document RENAME TO idx_evidence_form;
ALTER INDEX IF EXISTS idx_data_sources_document_id RENAME TO idx_data_sources_form_id;
ALTER INDEX IF EXISTS idx_corrections_document_created RENAME TO idx_corrections_form_created;
ALTER INDEX IF EXISTS idx_rule_snippets_document_id RENAME TO idx_rule_snippets_form_id;
ALTER INDEX IF EXISTS idx_annotation_pairs_document_id RENAME TO idx_annotation_pairs_form_id;
ALTER INDEX IF EXISTS idx_annotation_pairs_composite RENAME TO idx_annotation_pairs_composite_form;
ALTER INDEX IF EXISTS idx_field_label_maps_document_id RENAME TO idx_field_label_maps_form_id;
