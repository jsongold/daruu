-- Drop unused tables (all have 0 rows and no live code references)
-- Order: children first due to FK constraints

-- Children of fields/jobs
DROP TABLE IF EXISTS extractions CASCADE;
DROP TABLE IF EXISTS mappings CASCADE;
DROP TABLE IF EXISTS evidence CASCADE;
DROP TABLE IF EXISTS issues CASCADE;
DROP TABLE IF EXISTS activities CASCADE;

-- Parents in the old job-based workflow
DROP TABLE IF EXISTS fields CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;

-- MCP tables (never launched)
DROP TABLE IF EXISTS mcp_forms CASCADE;
DROP TABLE IF EXISTS mcp_source_docs CASCADE;
DROP TABLE IF EXISTS mcp_sessions CASCADE;

-- Other unused
DROP TABLE IF EXISTS entitlements CASCADE;
DROP TABLE IF EXISTS prompt_attempts CASCADE;
DROP TABLE IF EXISTS corrections CASCADE;
DROP TABLE IF EXISTS rule_cache CASCADE;
