# Task: Improve fill accuracy from ~10% to 80%+

## Status: TODO

## Problem (confirmed from prompt_raw data)

The fill accuracy on Japanese tax forms (扶養控除等申告書) is ~10%. Only top section (name/kana/address) fills correctly.

### Evidence from prompt_raw (2026-03-31)

The form_schema sent to GPT-4.1-mini had 154 fields. Analysis:

- ~100 fields were **junk** -- decoration text matched as labels
  - `0|明・大・昭|birth_era|select` -- era selector UI, not a fillable field label
  - `10|・|separator_dot` -- a dot separator
  - `20|□|checkbox_generic` -- checkbox symbol with no meaningful label
- ~30 fields were **unlabeled** -- `Text52`, `Text72`-`Text100` with empty semantic_keys
- Only ~20 fields had **meaningful labels**

The LLM returned 6 values (some with wrong indices). It gave up on the noise.

### Root causes (ranked)

1. **MapPrompt picks decoration text as labels** (CRITICAL)
   - Spatial candidates include "明・大・昭", "・", "□" alongside real labels
   - LLM picks wrong candidates because it lacks Japanese form heuristics
   - Checkbox symbols are decoration, not labels

2. **FillPrompt system prompt is too minimal** (HIGH)
   - 6-line system prompt doesn't explain free-text parsing, cross-language matching
   - No instruction for Japanese form conventions
   - No section awareness

3. **No junk field filtering** (MEDIUM)
   - Fields with label "・" or "□" should never reach the Fill LLM

## Fix plan

### Phase 1: MapPrompt improvements
- [ ] Add Japanese form heuristics to system prompt:
  - Skip single-char decoration text (・, □, ○)
  - Skip era markers (明・大・昭・平・令) as labels -- these are UI selectors
  - Prefer multi-char descriptive text as labels
  - Checkbox fields: use the text NEXT to the checkbox as label, not the checkbox symbol
- [ ] Add negative examples: "・ is NOT a label", "□ is NOT a label"
- [ ] Add section context awareness: "Fields in section A (源泉控除対象配偶者) share a common context"
- [ ] Keep checkbox field detection -- checking boxes is a valid task for this app

### Phase 2: FillPrompt improvements
- [ ] Enrich system prompt with:
  - Free-text blob parsing instructions
  - Cross-language matching (name -> 氏名, address -> 住所)
  - Japanese form conventions (furigana, era dates, postal codes)
  - Section awareness
- [ ] Add instruction: "User input is a single text blob. Parse and match values to fields by meaning."

### Phase 3: Pre-fill filter
- [ ] Filter form_schema before sending to Fill:
  - Remove fields where label is single decoration char (・, □, ○, ×)
  - Remove fields where label is era selector pattern (明・大, 昭・平)
  - Remove fields where semantic_key contains "separator"
  - Keep checkbox fields that have meaningful labels

## User input format

User input is a free-text blob by design. Example:
```
企業名：株式会社Cafkah 企業所在地：東京都渋谷区神宮前6丁目23番4号 桑野ビル2階 法人番号：3011001150000 申請者氏名：竹村康正 申請者個人住所：東京都目黒区五本木3-25-15 ハウス五本木 11
```

The LLM must parse this and match values to Japanese form fields.

## Workflow context

Map + Annotate are paired operations:
1. Spatial candidate filtering (current code)
2. LLM labels fields from candidates (MapPrompt)
3. User manually corrects via Annotate mode
4. Fill uses the corrected form_schema
