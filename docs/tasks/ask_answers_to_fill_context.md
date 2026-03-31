# Task: Pass Ask answers to Fill prompt as context

## Status: TODO

## Problem

Ask mode resolves conditional questions with the user (e.g. "Are you married?" -> "Yes"). Currently, ask_answers are only used as a **binary gate** to include/exclude fields from the Fill prompt. The actual answer values never reach the Fill LLM.

### Current flow

```
ask_answers = {"Are you married?": "Yes", "How many dependents?": "3"}
```

1. `_resolve_skips(rules, ask_answers)` -- uses answers to decide which field_ids to skip (No/unanswered -> skip, Yes -> include)
2. Skipped fields are excluded from the Fill prompt
3. The answer values ("Yes", "3") are **discarded** -- Fill LLM never sees them

### What's lost

The Fill LLM cannot use ask_answers to:
- Fill checkbox/radio fields based on the answer (e.g. check "married" box)
- Fill count fields (e.g. "number of dependents: 3")
- Make context-dependent decisions (e.g. if married, fill spouse section)

### Code locations

- `FillService.fill()` -- `services.py:1378` -- passes ask_answers to `_build_context()`
- `ContextService.build()` -- `context.py:24` -- receives ask_answers but only uses for `_resolve_skips()`
- `_resolve_skips()` -- `context.py:149` -- binary skip logic
- `FillPrompt.build()` -- `prompts.py:172` -- builds user prompt from FillContext (no ask_answers)
- `FillContext` model -- `models.py:268` -- has `fields` and `user_info` but no ask_answers

## Design: same as Claude Code

Claude Code handles Q&A answers by simply putting them into the context window. No special processing -- the LLM naturally uses them in subsequent decisions.

Apply the same pattern: inject ask_answers into the FillContext so the Fill LLM sees them as part of the user's context, alongside user_info.

## Proposed fix

1. Add `ask_answers: dict[str, str]` to `FillContext` model (`models.py`)
2. Pass ask_answers through `ContextService.build()` -> `FillContext` (`context.py`)
3. In `FillPrompt.build()`, render ask_answers as part of user context (`prompts.py`):

```
input
企業名：株式会社Cafkah 申請者氏名：竹村康正...
context
Are you married?: Yes
How many dependents?: 3
form_schema
0|name|full_name
...
```

4. Update FillPrompt.SYSTEM to reference the context section:
```
## Context
Additional facts about the user's situation from prior Q&A.
Use these alongside the input to determine field values.
```

## Impact

- Checkbox/radio fields that depend on user answers will fill correctly
- Count fields derived from answers will fill correctly
- Overall fill accuracy should improve for forms with conditional logic
