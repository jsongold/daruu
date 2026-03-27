# Context Engineering: As-Is / To-Be

## Architecture

| Aspect | As-Is | To-Be |
|--------|-------|-------|
| Context owner | FillService (scattered) | ContextService (single responsibility) |
| Entry point | `build_fill_prompt(ctx, annotations, maps, msg)` in prompts.py | `ContextService.build(session_id, user_message?)` in context.py |
| Callers | FillService.fill() and ask() each build context independently | Both delegate to `ContextService.build()` |
| Output | Raw string concatenation of JSON sections | `FillContext` model (structured, serializable) |

## Field Data

| Aspect | As-Is | To-Be |
|--------|-------|-------|
| Structure | Flat list of all fields | Grouped by page > section (y-coordinate proximity ~5%) |
| Field object | `{field_id, name, type, label?, semantic_key?}` | `{field_id, name, type, label, semantic_key, confidence, confirmed, current_value, nearby_text}` |
| label source | FieldLabelMap.label_text (if exists) | Same, merged directly into field |
| semantic_key source | FieldLabelMap.semantic_key (if exists) | Same, merged directly into field |
| confidence | Dropped | Included (0-100 int from Map) |
| confirmed flag | Not present (annotations in separate section) | `true` if annotation exists for this field |
| current_value | Dropped (`f.value` not sent) | Included -- LLM sees existing/prefilled values |
| nearby_text | Not present | TextBlocks within ~3% distance, not already used as label. Cap 5 items. Captures hints like "(昭和・平成・令和)", "年月日" |
| section_hint | Not present | First label text in the section group (e.g. "申告者情報") |

## Annotations

| Aspect | As-Is | To-Be |
|--------|-------|-------|
| Format | Separate section: `[{label, field_id, field_name}]` | Merged into field object as `confirmed: true` + label/semantic_key |
| Redundancy | Label appears in both field list and annotation list | Single source of truth per field |

## Filtering (C)

| Aspect | As-Is | To-Be |
|--------|-------|-------|
| Signature fields | Sent to LLM | Excluded |
| No-match fields | Sent (confidence=0, no annotation) | Excluded |
| Already-filled fields | Not distinguished | Moved to `already_filled` section (read-only context, not re-filled) |
| Token impact | All fields = noise | ~20-30% fewer fields sent |

## Additional Context (A)

| Aspect | As-Is | To-Be |
|--------|-------|-------|
| Conversation history | Not sent (`ctx.history` ignored) | `ctx.history[-6:]` included as `history` array |
| User info | `{key: value}` flat dict | Same (no change needed) |
| Rules | `[string]` list | Same (no change needed) |
| User message | Appended as raw text | Same (no change needed) |

## Context JSON Shape

| As-Is | To-Be |
|-------|-------|
| `"Form fields:\n" + JSON` | `"pages": [{page, sections: [{section_hint, fields: [...]}]}]` |
| `"User information:\n" + JSON` | `"user_info": {key: value}` |
| `"Manual annotations:\n" + JSON` | (merged into fields) |
| `"Rules:\n" + JSON` | `"rules": [string]` |
| (not present) | `"history": [{role, content}]` |
| (not present) | `"already_filled": [{field_id, label, value}]` |

## Token Budget (50 fields estimate)

| Component | As-Is | To-Be |
|-----------|-------|-------|
| System prompt | ~60 | ~400 |
| Field list | ~1,500 | ~1,200 (filtered) |
| User info | ~200 | ~200 |
| Annotations section | ~300 | 0 (merged) |
| History | 0 | ~300 |
| nearby_text | 0 | ~200 |
| already_filled | 0 | ~100 |
| **Total** | **~2,060** | **~2,400** |

+15% tokens, but higher information density, lower noise.

## Files

| File | As-Is | To-Be |
|------|-------|-------|
| `app/context.py` | Does not exist | New: `ContextService` + `FillContext` model |
| `app/prompts.py` | `build_fill_prompt()` assembles raw strings | Simplified: receives `FillContext`, serializes to JSON |
| `app/services.py` | FillService.fill() and ask() each do context assembly | Delegates to `ContextService.build()` |
| `app/models.py` | No enriched field models | Add: `EnrichedField`, `FieldSection`, `PageContext`, `FillContext` |
