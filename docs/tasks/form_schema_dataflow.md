# Task: form_schema & form_rules data flow validation

## Status: TODO

## Why this matters

The form_schema and form_rules tables are global (one row per form), written by all sessions and conversations. The update flow and label priority logic are critical -- if broken, user annotations get silently overwritten by LLM, or fill produces wrong results.

## Data flow (write paths)

1. **Upload PDF** -> `FormService.upload_pdf()` -> `FormSchemaService.ensure_schema()` seeds baseline fields (field_name, field_type, bbox, page). label_source = "pdf_extract".

2. **Annotate mode** -> `AnnotationService.create()` -> `FormSchemaService.upsert_from_annotation()` updates label. Annotation labels **always win** over map labels. Sets is_confirmed=True.

3. **Annotate delete** -> `AnnotationService.delete()` -> `FormSchemaService.remove_annotation()` reverts to map fallback or pdf_extract fallback.

4. **Map mode** -> `MapService.run()` -> `FormSchemaService.upsert_from_map()` bulk updates semantic_key, label, confidence, form_name. Only overwrites label if priority allows.

5. **Understand (Rules)** -> `UnderstandService.understand()` -> `FormRulesService.upsert()` writes description + rulebook_text + rules. Then `FormSchemaService.link_rules()` sets the FK.

## Label priority (lower = higher priority)

| Priority | label_source | Origin |
|----------|-------------|--------|
| 0 | annotation | Manual user label |
| 1 | map_manual | Promoted from annotation via Map |
| 2 | map_auto | LLM-detected label |
| 3 | pdf_extract | AcroForm field name from PDF |

## Provenance tracking

Both tables track `conversation_id` -- the conversation entry that triggered the last update. This creates an audit trail: for any field's label, you can trace back to the exact conversation that set it.

## Read path

- `FillService._build_context()` reads from `FormSchemaService.get()` as single source of truth
- Falls back to `ContextService.build_legacy()` if no form_schema row exists yet

## TODO items

- [ ] Add unit tests for FormSchemaService priority logic (annotation survives Map run, remove_annotation falls back correctly)
- [ ] Add unit tests for FormRulesService upsert/get
- [ ] Extract services.py into `app/services/` package (currently 1400+ lines)
- [ ] Implement embedding generation for RAG similarity search (form_schema.embedding VECTOR 1536)
- [ ] Validate concurrent write safety (two Map runs, or Map + Annotate simultaneously)
- [ ] Add integration test: full flow upload -> annotate -> map -> understand -> fill
