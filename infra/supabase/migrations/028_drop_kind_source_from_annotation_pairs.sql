-- Remove fill rows and drop kind/source columns from form_annotation_pairs.
-- This table is now annotation-only; fill corrections are no longer tracked here.

BEGIN;

-- Delete all fill rows (they had bbox=null and are not needed)
DELETE FROM form_annotation_pairs WHERE kind = 'fill';

-- Drop kind column (was 'annotation'|'fill', now always annotation)
ALTER TABLE form_annotation_pairs DROP COLUMN kind;

-- Drop source column (was null for annotations, 'user_edit'|'user_delete' for fills)
ALTER TABLE form_annotation_pairs DROP COLUMN source;

COMMIT;
