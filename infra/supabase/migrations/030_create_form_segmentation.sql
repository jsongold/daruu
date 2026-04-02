CREATE TABLE form_segmentation (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  form_id    UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
  method     TEXT NOT NULL DEFAULT 'fitz',
  segments   JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(form_id, method)
);

CREATE TRIGGER update_form_segmentation_updated_at
  BEFORE UPDATE ON form_segmentation
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE form_segmentation ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON form_segmentation FOR ALL USING (true);
