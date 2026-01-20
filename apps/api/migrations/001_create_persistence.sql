create extension if not exists pgcrypto;

create table if not exists templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null check (status in ('draft', 'final')),
  schema_json jsonb not null,
  pdf_fingerprint text,
  pdf_path text,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists template_revisions (
  id uuid primary key default gen_random_uuid(),
  template_id uuid not null references templates(id) on delete cascade,
  from_version integer not null,
  to_version integer not null,
  before_schema_json jsonb not null,
  after_schema_json jsonb not null,
  updated_by text,
  created_at timestamptz not null default now()
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  template_id uuid not null references templates(id) on delete cascade,
  input_values_json jsonb,
  output_pdf_path text not null,
  created_at timestamptz not null default now()
);
