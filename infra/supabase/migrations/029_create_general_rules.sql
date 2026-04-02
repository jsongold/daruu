-- Migration 029: Create general_rules table
-- Stores reusable rules scoped by country and category.
-- 'GLOBAL' means "applies to all" (no NULLs).

CREATE TABLE IF NOT EXISTS general_rules (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country    TEXT NOT NULL DEFAULT 'GLOBAL',
    category   TEXT NOT NULL DEFAULT 'GLOBAL',
    rules      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT general_rules_unique_scope UNIQUE (country, category)
);

COMMENT ON TABLE general_rules IS 'Reusable rules scoped by country and/or category';
COMMENT ON COLUMN general_rules.country IS 'ISO country code or GLOBAL for all';
COMMENT ON COLUMN general_rules.category IS 'Form category (tax, immigration, ...) or GLOBAL for all';
COMMENT ON COLUMN general_rules.rules IS 'JSONB array of RuleItem objects (same structure as form_rules.rules)';

CREATE INDEX IF NOT EXISTS idx_general_rules_country ON general_rules(country);

CREATE OR REPLACE TRIGGER general_rules_updated_at
    BEFORE UPDATE ON general_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
