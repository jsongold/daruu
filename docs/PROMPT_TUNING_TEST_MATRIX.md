# Prompt Tuning Test Matrix

Test plan for systematically evaluating vision autofill prompt configurations
using the `/prompting` page. One target PDF, 10 system prompts, 10 custom
rules, 10 data sources.

---

## Target PDF

**Form:** Japanese residence tax declaration (住民税申告書)

Chosen because it contains a representative mix of field types:

| # | Field ID | Label | Type | Section |
|---|----------|-------|------|---------|
| 1 | shimei | 氏名 (Full Name) | text | Applicant |
| 2 | furigana | フリガナ (Phonetic Name) | text | Applicant |
| 3 | seinengappi | 生年月日 (Date of Birth) | date | Applicant |
| 4 | jusho | 住所 (Address) | text | Applicant |
| 5 | denwa | 電話番号 (Phone) | text | Contact |
| 6 | email | メールアドレス (Email) | text | Contact |
| 7 | kinmusaki | 勤務先名称 (Employer Name) | text | Employment |
| 8 | shokushu | 職種 (Occupation) | text | Employment |
| 9 | nenshu | 給与収入 (Annual Salary) | number | Income |
| 10 | fuyosu | 扶養人数 (Dependents) | number | Household |
| 11 | haigusha | 配偶者の有無 (Spouse) | checkbox | Household |
| 12 | teishutsu_bi | 提出日 (Filing Date) | date | Admin |

---

## 10 System Prompts

Each system prompt is a full replacement of the default `AUTOFILL_SYSTEM_PROMPT`.

### SP-1: Default (Baseline)

The current default prompt, unchanged. All other prompts are compared against
this baseline.

```
You are a form-filling assistant. Your task is to extract information from
provided data sources and match it to form fields.
[... rest of current default ...]
```

**Hypothesis:** Establishes baseline accuracy. Expected weak on Japanese
forms, date formats, and cross-language matching.

---

### SP-2: Japanese-Aware

```
You are a form-filling assistant specializing in Japanese government and
business forms. Field labels and source data may be in Japanese, English,
or mixed.

Key conventions:
- Japanese names are family-name first: 姓 (family) → 名 (given)
- フリガナ is the katakana phonetic reading of a name
- Dates may appear in Wareki (令和/平成) or Western (YYYY-MM-DD) format
- Addresses follow Japanese order: prefecture → city → district → block

Return valid JSON with filled_fields, unfilled_fields, and warnings.
[... confidence rules same as default ...]
```

**Hypothesis:** Significant improvement on fields 1-4 (name, furigana, DOB,
address) by encoding Japanese conventions.

---

### SP-3: Section-Aware Grouping

```
You are a form-filling assistant. The form has multiple sections.
Fields within the same section are related — prefer matching data to fields
within the correct section context.

Sections:
- "Applicant" fields are personal identity (name, DOB, address)
- "Contact" fields are communication channels (phone, email)
- "Employment" fields are about the applicant's workplace
- "Income" fields are numeric financial values
- "Household" fields are about family composition

Do NOT cross-contaminate: an employer name should never fill a personal
name field, even if the label looks similar.

Return valid JSON with filled_fields, unfilled_fields, and warnings.
[... confidence rules same as default ...]
```

**Hypothesis:** Prevents cross-contamination between sections. Addresses the
flat-list problem described in TO_IMPROVE_ACCURACY.md.

---

### SP-4: Few-Shot with Examples

```
You are a form-filling assistant. Here are examples of correct matches:

Example 1:
  Source: "氏名: 田中太郎, 住所: 東京都新宿区西新宿1-1-1"
  Field "氏名" → "田中太郎" (confidence: 0.95)
  Field "住所" → "東京都新宿区西新宿1-1-1" (confidence: 0.95)

Example 2:
  Source: "Name: Taro Tanaka, DOB: 1990-01-15"
  Field "氏名" → "Taro Tanaka" (confidence: 0.90, cross-language match)
  Field "生年月日" → "1990-01-15" (confidence: 0.90)

Example 3:
  Source: "年収: 5,000,000円"
  Field "給与収入" → "5000000" (confidence: 0.85, removed formatting)

Now match the actual data to the actual fields.
Return valid JSON with filled_fields, unfilled_fields, and warnings.
```

**Hypothesis:** Few-shot examples teach the model the expected mapping
behavior, especially for cross-language and format normalization.

---

### SP-5: Strict Confidence Gating

```
You are a form-filling assistant. Be conservative with your matches.

STRICT RULES:
- Only fill a field if you are highly confident (>= 0.8)
- If the source data is ambiguous, add to unfilled_fields with a warning
- Never guess or infer values not explicitly present in the data
- If two fields could match the same value, fill neither and warn
- For numeric fields, only fill if the value is unambiguously numeric

Return valid JSON with filled_fields, unfilled_fields, and warnings.
```

**Hypothesis:** Fewer filled fields, but higher accuracy on those that are
filled. Useful when false positives are worse than missing values.

---

### SP-6: Aggressive Fill (Low Threshold)

```
You are a form-filling assistant. Fill as many fields as possible.

AGGRESSIVE RULES:
- Fill fields even with moderate confidence (>= 0.3)
- Use inference and context clues when exact matches aren't available
- If a source has a name but no furigana, attempt to generate the reading
- If a date is ambiguous, pick the most likely interpretation
- For checkbox fields, infer from context (e.g., "married" → spouse = true)

Always report your actual confidence honestly in the response.
Return valid JSON with filled_fields, unfilled_fields, and warnings.
```

**Hypothesis:** Higher fill rate, lower precision. Useful when the user
plans to review and correct all values manually.

---

### SP-7: Structured Output Focus

```
You are a form-filling assistant. Your primary goal is producing
perfectly structured JSON output.

CRITICAL — follow these formatting rules exactly:
- field_id must match the provided field list exactly (case-sensitive)
- confidence must be a float between 0.0 and 1.0 (not a percentage)
- value must always be a string, even for numbers ("5000000" not 5000000)
- source must reference the exact source_name from the data
- For date fields, always use YYYY-MM-DD format
- For checkbox fields, use "true" or "false" (lowercase string)
- For number fields, digits only, no commas or currency symbols

Return valid JSON: { filled_fields: [...], unfilled_fields: [...], warnings: [...] }
```

**Hypothesis:** Reduces parsing errors and format inconsistencies in the
response. May not affect match accuracy but improves reliability.

---

### SP-8: Chain-of-Thought Reasoning

```
You are a form-filling assistant. Think step by step:

1. First, list all fields that need filling and their types.
2. For each data source, summarize what information is available.
3. For each field, consider all possible source values that could match.
4. Choose the best match based on semantic similarity, section context,
   and data type compatibility.
5. Assign a confidence score based on match quality.
6. Check for conflicts — if two fields would get the same value, resolve.

After reasoning, return valid JSON with:
{ filled_fields: [...], unfilled_fields: [...], warnings: [...] }
```

**Hypothesis:** Step-by-step reasoning improves match quality for ambiguous
fields. May increase latency and token cost but improve accuracy.

---

### SP-9: Bilingual Field Mapping Table

```
You are a form-filling assistant. Use this field mapping reference:

| Japanese Label | English Equivalent | Data Type |
|---|---|---|
| 氏名 | Full Name | text |
| フリガナ | Phonetic Name (Katakana) | text |
| 生年月日 | Date of Birth | date |
| 住所 | Address | text |
| 電話番号 | Phone Number | text |
| メールアドレス | Email Address | text |
| 勤務先名称 | Employer / Company Name | text |
| 職種 | Occupation / Job Title | text |
| 給与収入 | Annual Salary / Income | number |
| 扶養人数 | Number of Dependents | number |
| 配偶者の有無 | Has Spouse (Y/N) | checkbox |
| 提出日 | Filing / Submission Date | date |

Match source data to form fields using both Japanese and English labels.
Return valid JSON with filled_fields, unfilled_fields, and warnings.
```

**Hypothesis:** Explicit bilingual table gives the model a lookup reference,
improving cross-language matching without requiring it to "know" Japanese.

---

### SP-10: Persona + Domain Expert

```
You are an experienced Japanese tax accountant (税理士) who helps
clients fill out residence tax declarations (住民税申告書).

You know that:
- 提出日 should be the current date in Japanese format
- 給与収入 is gross annual salary, reported as integer yen
- 扶養人数 counts dependents who qualify under tax law (income < 1.03M yen)
- 配偶者の有無 means whether the taxpayer has a spouse
- Field labels on government forms may use formal kanji
  (e.g., 生年月日 not 誕生日)

Fill the form using professional judgment. When data is ambiguous,
apply the interpretation most common in Japanese tax filings.
Return valid JSON with filled_fields, unfilled_fields, and warnings.
```

**Hypothesis:** Domain-expert persona encodes real-world knowledge about
the specific form type, improving both accuracy and appropriate formatting.

---

## 10 Custom Rules

Rules are passed as the `rules` parameter and appended to the user prompt.
Multiple rules can be combined in a single run.

| ID | Rule | Tests |
|----|------|-------|
| R-1 | `Use MM/DD/YYYY format for all date fields` | Date format override |
| R-2 | `Use 令和 (Reiwa) era format for dates, e.g., 令和7年2月5日` | Japanese era date handling |
| R-3 | `Leave 提出日 (Filing Date) empty — it will be filled by the office` | Field-specific skip rule |
| R-4 | `For 給与収入, use integer yen with no commas (e.g., 5000000)` | Numeric formatting |
| R-5 | `Convert all katakana フリガナ to full-width characters` | Character width normalization |
| R-6 | `If address contains apartment/room info, include it in 住所` | Field content scope |
| R-7 | `For 配偶者の有無, use "有" for yes and "無" for no instead of true/false` | Checkbox value override |
| R-8 | `Prefer the most recent data source when multiple sources conflict` | Conflict resolution priority |
| R-9 | `Do not fill any field with confidence below 0.7` | Confidence floor override |
| R-10 | `Add a warning for every field where the source language differs from the label language` | Cross-language tracking |

---

## 10 Data Sources

Each data source represents a different type of user-provided input.
Data sources should be uploaded individually or in combinations to test
interaction effects.

### DS-1: Japanese Driver's License (PDF scan)

```
Type: pdf
Content: Scanned image of Japanese driver's license
Fields available:
  - 氏名: 山田花子
  - 生年月日: 平成2年3月15日 (1990-03-15)
  - 住所: 神奈川県横浜市中区山下町1-2-3
  - 有効期限: 令和9年3月15日
```

**Tests:** Name extraction, Wareki date parsing, address extraction.

---

### DS-2: English Resume (PDF)

```
Type: pdf
Content: Digital PDF resume in English
Fields available:
  - Name: Hanako Yamada
  - Email: hanako.yamada@example.com
  - Phone: +81-45-123-4567
  - Current Employer: Yokohama Tech Corp.
  - Job Title: Software Engineer
  - Annual Salary: JPY 6,500,000
```

**Tests:** Cross-language name matching (English name → Japanese field),
employer/occupation extraction, salary format handling.

---

### DS-3: CSV Employee Record

```
Type: csv
Content:
  name,furigana,dob,address,phone,email,company,occupation,salary
  山田花子,ヤマダハナコ,1990-03-15,神奈川県横浜市中区山下町1-2-3,045-123-4567,hanako@example.com,横浜テック株式会社,エンジニア,6500000
```

**Tests:** Structured data extraction, furigana availability, all fields
present. Highest expected fill rate.

---

### DS-4: Free-Form Text Note

```
Type: text
Content:
  山田花子さんの情報メモ
  生年月日は平成2年3月15日
  携帯番号 090-9876-5432
  扶養家族は2人（子供2名）
  配偶者あり
```

**Tests:** Unstructured Japanese text parsing, dependent count, spouse
status inference from natural language.

---

### DS-5: My Number Card Photo (Image)

```
Type: image (JPEG)
Content: Photo of Japanese My Number (Individual Number) card
Fields available:
  - 氏名: 山田花子
  - 生年月日: 平成2年3月15日
  - 住所: 神奈川県横浜市中区山下町1-2-3
  - 性別: 女
```

**Tests:** Image source handling, OCR quality dependency. Note: currently
the system extracts text before sending, so this tests the extraction
pipeline as much as the prompt.

---

### DS-6: Employer Certificate (PDF with tables)

```
Type: pdf
Content: Certificate of employment (在職証明書) with tabular layout
Fields available:
  - 氏名: 山田花子
  - 勤務先: 横浜テック株式会社
  - 所属部署: 開発部
  - 役職: シニアエンジニア
  - 入社日: 2015-04-01
  - 給与: 月額541,666円 (annual: 6,500,000)
```

**Tests:** Table extraction, monthly-to-annual salary conversion,
employer name from a formal document.

---

### DS-7: Partial Data (Name + Address Only)

```
Type: text
Content:
  氏名: 山田花子
  住所: 神奈川県横浜市中区山下町1-2-3
```

**Tests:** Minimal data source. Only 2 of 12 fields should be filled.
Verifies the system correctly reports unfilled fields and doesn't
hallucinate values for missing data.

---

### DS-8: Conflicting Sources (Two Names)

```
Type: text
Content:
  Source A claims: 氏名 = 山田花子
  Source B claims: 氏名 = 山田はな子

  Source A claims: 電話番号 = 045-123-4567
  Source B claims: 電話番号 = 090-9876-5432
```

**Tests:** Conflict resolution behavior. Should the system pick one, skip
both, or warn? Tests interaction with R-8 (most recent source wins).

---

### DS-9: English-Only Data

```
Type: text
Content:
  Full Name: Hanako Yamada
  Date of Birth: March 15, 1990
  Address: 1-2-3 Yamashita-cho, Naka-ku, Yokohama, Kanagawa
  Phone: +81-45-123-4567
  Email: hanako.yamada@example.com
  Employer: Yokohama Tech Corp.
  Job Title: Software Engineer
  Annual Income: 6,500,000 JPY
  Dependents: 2
  Marital Status: Married
```

**Tests:** Pure cross-language matching. All data in English, all field
labels in Japanese. This is the hardest matching scenario.

---

### DS-10: Noisy / Low Quality Data

```
Type: text
Content:
  やまだ はなこ (yamada hanako)
  横浜に住んでます
  電話は045から始まる番号です
  会社員です、年収は600万くらい
  子供2人います
```

**Tests:** Vague, conversational Japanese. Tests whether the model can
extract usable values from imprecise natural language. Expected lower
confidence scores across the board.

---

## Test Execution Matrix

Run each combination and record: fields filled, fields correct,
confidence scores, warnings generated.

### Priority Runs (30 combinations)

Start with these high-signal combinations:

| Run | System Prompt | Rules | Data Sources | Focus |
|-----|---------------|-------|--------------|-------|
| 1 | SP-1 (Default) | none | DS-3 (CSV) | Baseline with best data |
| 2 | SP-1 (Default) | none | DS-9 (English) | Baseline cross-language |
| 3 | SP-1 (Default) | none | DS-10 (Noisy) | Baseline worst case |
| 4 | SP-2 (JP-Aware) | none | DS-1 (License) | JP prompt + JP source |
| 5 | SP-2 (JP-Aware) | none | DS-9 (English) | JP prompt + EN source |
| 6 | SP-2 (JP-Aware) | R-2 | DS-4 (Text) | JP prompt + Reiwa dates |
| 7 | SP-3 (Sections) | none | DS-3 (CSV) | Section grouping + full data |
| 8 | SP-3 (Sections) | none | DS-8 (Conflict) | Section grouping + conflicts |
| 9 | SP-4 (Few-Shot) | none | DS-9 (English) | Examples + cross-language |
| 10 | SP-4 (Few-Shot) | none | DS-10 (Noisy) | Examples + noisy data |
| 11 | SP-5 (Strict) | R-9 | DS-7 (Partial) | Conservative + minimal data |
| 12 | SP-6 (Aggressive) | none | DS-10 (Noisy) | Max fill on worst data |
| 13 | SP-6 (Aggressive) | none | DS-7 (Partial) | Max fill on minimal data |
| 14 | SP-7 (Structured) | R-1 | DS-3 (CSV) | Format compliance |
| 15 | SP-7 (Structured) | R-4 | DS-6 (Employer) | Number formatting |
| 16 | SP-8 (CoT) | none | DS-9 (English) | Reasoning + cross-language |
| 17 | SP-8 (CoT) | none | DS-8 (Conflict) | Reasoning + conflicts |
| 18 | SP-9 (Bilingual) | none | DS-9 (English) | Mapping table + EN data |
| 19 | SP-9 (Bilingual) | none | DS-1 (License) | Mapping table + JP source |
| 20 | SP-10 (Expert) | R-2, R-7 | DS-4 (Text) | Domain expert + JP rules |
| 21 | SP-10 (Expert) | R-3 | DS-3 (CSV) | Expert + skip rule |
| 22 | SP-2 (JP-Aware) | R-5, R-7 | DS-3 (CSV) | JP prompt + format rules |
| 23 | SP-4 (Few-Shot) | R-8 | DS-8 (Conflict) | Examples + conflict rule |
| 24 | SP-1 (Default) | none | DS-1 + DS-4 | Multi-source baseline |
| 25 | SP-2 (JP-Aware) | none | DS-1 + DS-2 | Multi-source JP+EN |
| 26 | SP-3 (Sections) | none | DS-2 + DS-6 | Multi-source employment |
| 27 | SP-10 (Expert) | R-2, R-4, R-7 | DS-3 (CSV) | Best prompt + all format rules |
| 28 | SP-10 (Expert) | R-2, R-4, R-7 | DS-10 (Noisy) | Best prompt on worst data |
| 29 | SP-8 (CoT) | R-9, R-10 | DS-9 (English) | Reasoning + strict + tracking |
| 30 | SP-4 (Few-Shot) | R-5, R-7 | DS-1 + DS-4 | Examples + JP rules + multi |

---

## Scoring

For each run, record:

| Metric | Definition |
|--------|-----------|
| **Fill Rate** | filled_fields.length / 12 |
| **Accuracy** | correctly_filled / filled_fields.length |
| **F1 Score** | harmonic mean of fill rate and accuracy |
| **Avg Confidence** | mean confidence across filled fields |
| **Confidence Calibration** | correlation between confidence and correctness |
| **False Positives** | fields filled with wrong values |
| **Warnings Quality** | were warnings actionable and correct? (1-5 scale) |
| **Latency** | processing_time_ms from response |

### Ground Truth

The correct values for Yamada Hanako across all fields:

| Field | Correct Value | Acceptable Variants |
|-------|--------------|---------------------|
| 氏名 | 山田花子 | Hanako Yamada, Yamada Hanako |
| フリガナ | ヤマダハナコ | ヤマダ ハナコ |
| 生年月日 | 1990-03-15 | H2.3.15, 平成2年3月15日, March 15 1990 |
| 住所 | 神奈川県横浜市中区山下町1-2-3 | Romanized variant |
| 電話番号 | 045-123-4567 | +81-45-123-4567, 0451234567 |
| メールアドレス | hanako.yamada@example.com | hanako@example.com |
| 勤務先名称 | 横浜テック株式会社 | Yokohama Tech Corp. |
| 職種 | エンジニア | Software Engineer, シニアエンジニア |
| 給与収入 | 6500000 | 6,500,000 |
| 扶養人数 | 2 | |
| 配偶者の有無 | true | 有, yes, married |
| 提出日 | (today's date) | any reasonable date format |

---

## Expected Insights

After running the matrix, answer:

1. **Which system prompt produces the best F1 across data source types?**
2. **Do custom rules improve accuracy or just formatting?**
3. **Which data source type gives the highest baseline accuracy?**
4. **Does cross-language matching improve more from SP-2, SP-4, or SP-9?**
5. **Is chain-of-thought (SP-8) worth the latency cost?**
6. **Does the domain expert persona (SP-10) outperform generic prompts?**
7. **What is the minimum data source quality for > 80% accuracy?**
8. **Which rule combinations are most impactful?**
9. **Do multi-source runs outperform single-source?**
10. **What is the best overall configuration (prompt + rules + source type)?**
