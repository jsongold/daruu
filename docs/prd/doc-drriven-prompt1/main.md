# PRD: Specialized Prompt Generation for Field Identification

## Status: Draft
## Branch: `doc-driven-prompt-1`

---

## 1. Problem Statement

PDF フォーム自動入力システムにおいて、AcroFormフィールドのラベル特定（FIELD_IDENTIFICATION）にLLM呼び出しで70秒以上かかっている。これはユーザー体験として許容できない。

### 現状のパイプライン

```
FIELD_IDENTIFICATION (LLM, 70秒)
  → autofill_quick (LLM, 5秒)
  → detailed_turn (LLM, 6秒)
合計: 81秒
```

### ボトルネックの原因

- AcroFormのfield_idは "Text1", "Text2" 等の無意味な連番
- 189フィールド全てのラベルを1回のLLM呼び出しで特定
- 出力トークン数 ~9,500 が律速（GPT-4o-mini ~100 tokens/sec → ~95秒）
- 出力を削ると精度が低下（null出力がChain-of-Thoughtとして機能）

### アプローチの選択

**StructuralResolver（Python-onlyの事前解決）は不要。** 専用プロンプト生成LLMが全189フィールドを一括で特定するため、Python側で事前にfield_idセマンティクスやテーブル構造を解析しても:
- LLMが同じ情報を再特定する（重複作業）
- Python解決とLLM解決が矛盾する場合にどちらを優先するか曖昧
- `DirectionalFieldEnricher` の `nearby_labels` が同じ空間コンテキストをより信頼性高く提供する

**本PRDの焦点**: `DirectionalFieldEnricher` で各フィールドの空間コンテキスト（nearby_labels）を提供し、**専用プロンプト生成**（LLMによるフォーム特化型 system prompt の動的生成）で全フィールドを一括特定する。

---

## 2. Goal

| Metric | 現状 | 目標 |
|---|---|---|
| ユーザーへの最初の応答 | 81秒 | **3-5秒** |
| フィールドラベル特定の精度 | baseline | baseline以上 |
| 対応フォーム種別 | 汎用 | **汎用（維持）** |
| 2回目以降の同一フォーム処理 | 81秒 | **3-5秒** |

---

## 3. Non-Goals

- 既存の `AUTOFILL_SYSTEM_PROMPT` / `DETAILED_MODE_SYSTEM_PROMPT` の変更
- `FillPlanner.plan()` / `plan_turn()` のコアロジック変更
- PDF書き込み処理（`FormRenderer`）の変更
- UIの変更
- Python-only のフィールド事前解決（StructuralResolver）— LLMが全件処理するため不要

---

## 4. Architecture Overview

### 4.1 2段階パイプライン: 空間コンテキスト + 専用プロンプト生成

```
PDF到着
 │
 ▼
Step 1: DirectionalFieldEnricher.enrich()           [Python, <0.01秒]
 │  方向別nearby_labels生成（左/上/右のテキスト）
 │  → 各フィールドに LabelCandidate を付与
 │
 ├─→ [async] generate_questions(FormContext)         [LLM, 3秒] → ユーザーへ即表示
 │
 └─→ [async] generate_prompt(FormContext)            [LLM, 10-30秒] 裏側で実行
      │  全フィールド + nearby_labels + PDFテキスト
      │  → LLMが専用プロンプトを生成（全field_id → ラベル マッピング）
      │  → バリデーション（全field_id含むか検証）
      │
      ▼
 ユーザー回答到着
 │
 ├─ 専用プロンプト完了済み？
 │   ├─ Yes → fill(specialized_prompt, user_data)   [LLM, 3-5秒]
 │   └─ No  → fill_with_nearby(FormContext, user_data) [LLM, 5秒] 暫定
 │             → 専用プロンプト完了後に差分補正
 │
 ▼
AutofillPipelineResult
```

### 4.2 StructuralResolver を使わない理由

| 比較軸 | StructuralResolver (Python) | PromptGenerator (LLM) |
|---|---|---|
| field_idセマンティクス | `employee_name` → "Employee Name" | 同じことを自然にやる |
| テーブル構造 | `find_tables()` → ヘッダー抽出 | nearby_labelsから推論可能 |
| フリーレイアウト | 対応不可 | nearby_labelsから推論可能 |
| 記入ルール理解 | 不可 | PDFテキストから抽出・理解 |
| エラーリスク | テーブル検出失敗でゴミラベル | LLMが文脈で判断 |
| 結果の一貫性 | LLM結果と矛盾する可能性 | 単一ソースで一貫 |

**結論**: `DirectionalFieldEnricher` が提供する `nearby_labels`（空間コンテキスト）を LLM に渡せば十分。Pythonでの事前解決は複雑さを増すだけで、LLMの仕事と重複する。

### 4.3 2モード

| | Quick Mode | Precise Mode |
|---|---|---|
| 最初の応答 | 3秒 | 3秒 |
| 裏側処理 | なし | generate_prompt実行 |
| マッピング | nearby_labelsベース（汎用プロンプト） | 専用プロンプトベース |
| 精度 | ★★★☆ | ★★★★★ |
| 用途 | 速度優先 | 精度優先 |

### 4.4 類似フォーム活用（蓄積効果）

```
蓄積済み専用プロンプト群
 │
 ▼
新フォーム到着 → embedding類似度検索
 │
 ├─ Hit → 類似プロンプトをfew-shotとして generate_prompt に渡す
 │        → 速度UP + 精度UP
 │
 └─ Miss → 通常の generate_prompt → 結果を蓄積に追加
```

---

## 5. Data Flow & Interfaces

### 5.1 既存データモデル（変更なし）

```python
# app/domain/models/form_context.py

class FormFieldSpec(BaseModel):
    field_id: str                          # "Text1"
    label: str                             # フロントエンドから渡されるラベル or field_id
    field_type: str                        # "text" | "checkbox" | "number"
    page: int | None
    x: float | None                        # PDF points
    y: float | None
    width: float | None
    height: float | None
    label_candidates: tuple[LabelCandidate, ...]  # DirectionalFieldEnricher結果

class FormContext(BaseModel):
    document_id: str
    conversation_id: str
    fields: tuple[FormFieldSpec, ...]
    data_sources: tuple[DataSourceEntry, ...]
    mapping_candidates: tuple[MappingCandidate, ...]
    rules: tuple[str, ...]
```

### 5.2 新規データモデル

```python
# app/services/prompt_generator/models.py (NEW)

@dataclass(frozen=True)
class PromptGenerationResult:
    specialized_prompt: str              # 生成されたフォーム特化型system prompt
    field_mapping: dict[str, str]        # field_id → identified_label（全件）
    generation_time_ms: int
    model_used: str
    validation_passed: bool              # 全field_idが含まれているか
    missing_field_ids: tuple[str, ...]   # バリデーションで欠落していたID

@dataclass(frozen=True)
class PromptCacheEntry:
    form_hash: str                       # フィールド構造のハッシュ
    specialized_prompt: str
    field_count: int
    created_at: str                      # ISO 8601
    form_title: str | None
```

### 5.3 関数インターフェース

```python
# ── 専用プロンプト生成（LLM, 10-30秒） ──
# app/services/prompt_generator/generator.py (NEW)

class PromptGenerator:
    def __init__(self, llm_client: LiteLLMClient, document_service: DocumentService) -> None: ...

    async def generate(
        self,
        document_id: str,
        context: FormContext,
        similar_prompts: list[str] | None = None,
    ) -> PromptGenerationResult: ...

# ── プロンプト蓄積・検索 ──
# app/services/prompt_generator/store.py (NEW)

class PromptStore:
    def store(self, form_hash: str, prompt: str, form_title: str | None = None) -> None: ...
    def find_similar(self, form_hash: str, top_k: int = 2) -> list[str] | None: ...
    def compute_form_hash(self, fields: tuple[FormFieldSpec, ...]) -> str: ...
```

---

## 6. Module Design

### 6.1 `DirectionalFieldEnricher` — 空間コンテキスト提供 (実装済み)

**既存モジュール**: `app/services/form_context/enricher.py`

`compute_directional_labels()` が各フィールドに対して方向別に近接テキストを検出:
- **左**: block_right_edge <= field_left, Y-center差 < 15pt, 距離 < 50pt
- **上**: block_bottom_edge <= field_top, X-center差 < 80pt, 距離 < 50pt
- **右**: block_left_edge >= field_right, Y-center差 < 15pt, 距離 < 50pt

結果は `LabelCandidate` として `FormFieldSpec.label_candidates` に付与される。

この `nearby_labels` が `PromptGenerator` への主要入力となる。

### 6.2 `prompt_generator/generator.py` — 専用プロンプト生成 (NEW)

**責務**: `FormContext`（nearby_labels付き）からフォーム特化型の system prompt を生成する。

**内部処理**:

1. コンテキスト構築（Python）
   - `FormContext.fields` から全フィールド + nearby_labels を整形
   - PDFテキスト（`DocumentService.extract_text_blocks()`）から記入ルール部分を抽出
   - フォームタイトル検出（ページ上部の最大テキストブロック）

2. LLM呼び出し（メタプロンプト）
   - 入力: 全フィールドの nearby_labels + PDFテキスト + 類似プロンプト（あれば）
   - 出力: そのまま system prompt として使えるテキスト
   - クライアント: `LiteLLMClient` (`app.services.llm.get_llm_client()`)
   - temperature: 0.2（安定性重視）
   - max_tokens: 4000

3. バリデーション（Python）
   - 生成プロンプト内に全 field_id が含まれるか検証
   - 欠落フィールドがあれば末尾に補足追加

**メタプロンプトが生成するプロンプトに含めるべき内容**:

| Section | 内容 | 例 |
|---|---|---|
| フォーム識別 | 種類と目的 | 「令和7年分 給与所得者の扶養控除等（異動）申告書」 |
| フィールドマッピング表 | 全field_id → セマンティックラベル | `Text7: 氏名 (漢字)` |
| セクション構造 | グループ化 | `=== A: 源泉控除対象配偶者 ===` |
| 入力形式仕様 | 桁数、フォーマット | `Text8: 個人番号 (12桁数字, ハイフンなし)` |
| 記入ルール | 条件分岐、計算式 | `IF 配偶者なし → セクションA全て空欄` |
| 質問テンプレート | always_ask / conditional_ask | `"配偶者はいますか？" (single_choice)` |
| 出力指示 | FillPlan の JSON 形式 | `{"actions": [...]}` |

### 6.3 `prompt_generator/meta_prompt.py` — メタプロンプト定義 (NEW)

**責務**: `PromptGenerator` が LLM に渡すメタプロンプト（system prompt + user prompt テンプレート）。

```python
PROMPT_GENERATION_SYSTEM_PROMPT: str  # メタプロンプトのsystem部分
def build_prompt_generation_user_prompt(
    context: FormContext,
    text_blocks: list[dict],
    similar_prompts: list[str] | None = None,
) -> str
```

LLMへの入力に含めるフィールド情報:
```
Field: Text7
  nearby_labels (left): "氏名"
  nearby_labels (above): "（フリガナ）"
  bbox: page=1, x=150, y=200, w=200, h=20
  type: text
```

LLMはこの空間コンテキストから `Text7 → 氏名（漢字）` を推論する。

### 6.4 既存モジュールの拡張 — `FillPlanner` ラップ

**責務**: 専用プロンプト（または既存の汎用プロンプト）+ ユーザーデータから FillPlan を生成する。

**変更箇所**: `app/services/fill_planner/planner.py`

- `FillPlanner.__init__` に `specialized_prompt: str | None = None` を追加
- `_prepare_prompt_inputs()` で `specialized_prompt` がある場合、`AUTOFILL_SYSTEM_PROMPT` の代わりに使用
- 既存の `plan()` / `plan_turn()` ロジックは変更しない

### 6.5 `AutofillPipelineService` の拡張 — 非同期オーケストレーション

**変更箇所**: `app/services/autofill_pipeline/service.py`

**`__init__` 拡張**:
```python
def __init__(
    self,
    context_builder: FormContextBuilderProtocol,
    fill_planner: FillPlannerProtocol,
    form_renderer: FormRendererProtocol,
    rule_analyzer: RuleAnalyzerProtocol,
    correction_tracker: CorrectionTrackerProtocol,
    prompt_generator: PromptGenerator | None = None,    # NEW
    prompt_store: PromptStore | None = None,             # NEW
) -> None: ...
```

**注意**: `structural_resolver` パラメータは削除する。StructuralResolver は本ブランチでは使用しない。

**`autofill()` (quick mode)**:
- `DirectionalFieldEnricher` → `FormContextBuilder` → `FillPlanner`（汎用プロンプト）
- 専用プロンプト生成なし、nearby_labels ベースでマッピング

**`autofill_turn()` (detailed/precise mode) — 拡張**:
```python
# 初回ターン（context未キャッシュ時）:
# Step 1: FormContextBuilder.build() (DirectionalFieldEnricher含む)
# Step 1.5: 専用プロンプト生成を非同期で開始 (NEW)
if self._prompt_generator and not cached_context:
    prompt_task = asyncio.create_task(
        self._prompt_generator.generate(document_id, context)
    )

# ユーザー回答到着時:
# 専用プロンプトが完了していれば FillPlanner に渡す
if prompt_task and prompt_task.done():
    specialized_prompt = prompt_task.result().specialized_prompt
    self._fill_planner._specialized_prompt = specialized_prompt
```

### 6.6 `prompt_generator/store.py` — プロンプト蓄積・検索 (NEW)

**責務**: 生成済み専用プロンプトの保存と類似検索。

**フォームHash生成**:
- フィールド数 + フィールド種別分布
- 完全一致 → キャッシュ Hit（専用プロンプトをそのまま再利用）
- 類似一致 → few-shot として `PromptGenerator.generate()` に渡す

**ストレージ**: 初期実装はファイルシステム（JSON）。将来的に DB 移行可能。

### 6.7 `past_data.py` — 過去データ活用 (Future)

**責務**: 記入済みPDFからフィールドマッピングとユーザーデータを抽出。

**内部処理**:
- 記入済みPDFから AcroForm フィールドの値を抽出
- field_id → 値のペアから、値の内容でセマンティクスを推論
  - `Text1 = "株式会社Cafkah"` → label = "会社名"
  - `Text7 = "竹村康正"` → label = "氏名"
- `FormFieldSpec.label` を補完

---

## 7. File Structure

```
apps/api/app/services/
  form_context/
    __init__.py                    # DirectionalFieldEnricher export
    enricher.py                    # DirectionalFieldEnricher (実装済み)
    builder.py                     # FormContextBuilder (既存)
  prompt_generator/                # NEW
    __init__.py
    models.py                      # PromptGenerationResult, PromptCacheEntry
    generator.py                   # PromptGenerator
    meta_prompt.py                 # メタプロンプト定義
    store.py                       # PromptStore
  autofill_pipeline/
    service.py                     # AutofillPipelineService (拡張)
    models.py                      # AutofillPipelineResult (既存)
    step_log.py                    # PipelineStepLog (既存)
  fill_planner/
    planner.py                     # FillPlanner (拡張: specialized_prompt対応)
  vision_autofill/
    prompts.py                     # 既存プロンプト (変更なし)
  document_service.py              # DocumentService (既存)
  llm/
    client.py                      # LiteLLMClient (既存、変更なし)

apps/api/app/routes/
  autofill_pipeline.py             # Route wiring (拡張)

apps/api/tests/
  test_label_enrichment.py         # DirectionalFieldEnricher tests (実装済み)
  test_prompt_generator.py         # NEW
  test_prompt_store.py             # NEW
```

**削除対象（本ブランチ）**:
- `apps/api/app/services/form_context/structural_resolver.py`
- `apps/api/tests/test_structural_resolver.py`
- `enricher.py` の `apply_resolved_labels()` 関数
- `service.py` の `structural_resolver` パラメータと Step 0 ロジック

---

## 8. Implementation Order

| Phase | Module | 依存 | 状態 |
|---|---|---|---|
| **1** | `DirectionalFieldEnricher` | なし | **完了** |
| **2** | StructuralResolver 削除 | なし | 未着手 |
| **3** | `prompt_generator/models.py` | なし | 未着手 |
| **4** | `prompt_generator/meta_prompt.py` | models | 未着手 |
| **5** | `prompt_generator/generator.py` | models, meta_prompt, LiteLLMClient | 未着手 |
| **6** | `prompt_generator/store.py` | models | 未着手 |
| **7** | `FillPlanner` 拡張 (specialized_prompt) | generator | 未着手 |
| **8** | `AutofillPipelineService` 拡張 (async prompt) | generator, store | 未着手 |
| **9** | Route wiring + テスト | 全module | 未着手 |

### 各 Phase の完了条件

- **Phase 2 完了**: StructuralResolver 関連コード削除、既存テスト全パス。
- **Phase 5 完了**: テスト PDF（日本税務フォーム）で `PromptGenerationResult` 生成が成功。生成プロンプトに全 field_id が含まれる。プロンプトがフォームの言語で記述される。
- **Phase 7 完了**: `FillPlanner` が `specialized_prompt` を使って `plan()` / `plan_turn()` を実行でき、通常モードと同等以上の精度。
- **Phase 8 完了**: Quick/Precise モード両方で最初の質問表示が5秒以内。Precise モードで裏側の prompt 生成が動作。

---

## 9. Testing Strategy

### 9.1 Unit Tests

**prompt_generator/generator.py**:
- 生成プロンプトに全 field_id が含まれること
- フォームの言語で記述されること（日本語フォーム → 日本語プロンプト）
- 記入ルールが抽出されていること
- `nearby_labels` が正しくコンテキストとして含まれること

**prompt_generator/store.py**:
- `compute_form_hash()` が同一フォームで同じハッシュを返すこと
- `store()` + `find_similar()` のラウンドトリップ
- 未登録フォームで `None` を返すこと

**FillPlanner (specialized_prompt)**:
- `specialized_prompt` 設定時に `AUTOFILL_SYSTEM_PROMPT` の代わりに使用されること
- `specialized_prompt` 未設定時に既存動作を維持すること

### 9.2 Integration Tests

| テストケース | 期待結果 |
|---|---|
| 日本税務フォーム (テーブル構造あり) | nearby_labels 付与、専用プロンプト生成成功 |
| フリーレイアウト PDF | nearby_labels から LLM が推論、専用プロンプト生成成功 |
| Quick mode | 5秒以内に質問表示、nearby_labels ベースでマッピング |
| Precise mode（ユーザー回答が遅い） | 裏側で専用プロンプト完了、高精度マッピング |
| Precise mode（ユーザー回答が速い） | 暫定マッピング → 差分補正が動作 |

### 9.3 Performance Benchmarks

各ステップの処理時間を `StopWatch` + `PipelineStepLog` で計測:

```python
step_logs.append(PipelineStepLog(
    step_name="prompt_generate",
    status="success",
    duration_ms=sw.laps["prompt_generate"],
    summary=f"validated={result.validation_passed}",
    details={...},
))
```

目標:
```
context_build:       < 3秒
prompt_generate:     < 30秒 (async, 非ブロッキング)
fill_plan:           < 5秒
total_user_facing:   < 5秒（最初の応答まで）
```

---

## 10. Migration Plan

### Phase A: 並行稼働

既存の `AUTOFILL_SYSTEM_PROMPT` は削除せず、`mode` パラメータで切り替え:

```python
# AutofillRequestDTO.mode:
# "quick"   → 既存フロー (DirectionalFieldEnricher + 汎用プロンプト)
# "precise" → 専用プロンプト生成フロー
```

### Phase B: 精度検証

同一PDFに対して quick/precise 両方を実行し、結果を比較:
- `field_labels` の一致率
- autofill の精度（`filled_fields` の正確性）
- 処理時間の比較（`step_logs` で計測）

### Phase C: 移行完了

精度が同等以上であることを確認後、`FIELD_IDENTIFICATION_SYSTEM_PROMPT` 関連コードを削除。

---

## 11. Dependencies

```
PyMuPDF (fitz)      # PDF解析（既存）
litellm             # LLM呼び出し via LiteLLMClient（既存）
instructor          # 構造化出力（既存）
asyncio             # 非同期処理（標準ライブラリ）
```

追加依存なし。

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 専用プロンプトの品質がばらつく | マッピング精度低下 | バリデーション + few-shot 蓄積で品質向上。Quick mode フォールバック。 |
| `generate_prompt` が 30秒以上かかる | ユーザー回答前に完了しない | 暫定マッピング → 差分補正パターンで対応。ユーザー体感には影響なし。 |
| nearby_labels が不十分（テキストが遠い） | LLMの推論精度低下 | `_DIR_MAX_DISTANCE` を調整可能。将来的に Vision LLM 導入で補完。 |
| メタプロンプトのメンテナンス | プロンプト変更が波及 | `meta_prompt.py` に集約、バージョン管理。 |
| 蓄積データの肥大化 | 検索速度低下 | 初期はファイル。100件超で DB 移行を検討。 |

---

## 13. Existing Code Reference

### 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `apps/api/app/services/autofill_pipeline/service.py` | `structural_resolver` 削除、`prompt_generator` / `prompt_store` 追加、async prompt 生成 |
| `apps/api/app/services/fill_planner/planner.py` | `specialized_prompt` パラメータ追加 |
| `apps/api/app/routes/autofill_pipeline.py` | StructuralResolver wiring 削除、`PromptGenerator` / `PromptStore` wiring 追加 |
| `apps/api/app/services/form_context/__init__.py` | StructuralResolver export 削除（もしあれば） |
| `apps/api/app/services/form_context/enricher.py` | `apply_resolved_labels()` 削除、StructuralResolver TYPE_CHECKING import 削除 |

### 削除対象ファイル

| ファイル | 理由 |
|---|---|
| `apps/api/app/services/form_context/structural_resolver.py` | LLMが全件処理するため不要 |
| `apps/api/tests/test_structural_resolver.py` | 上記に対応するテスト |

### 新規作成ファイル

| ファイル | 内容 |
|---|---|
| `apps/api/app/services/prompt_generator/__init__.py` | パッケージ export |
| `apps/api/app/services/prompt_generator/models.py` | `PromptGenerationResult`, `PromptCacheEntry` |
| `apps/api/app/services/prompt_generator/generator.py` | `PromptGenerator` クラス |
| `apps/api/app/services/prompt_generator/meta_prompt.py` | メタプロンプト定義 |
| `apps/api/app/services/prompt_generator/store.py` | `PromptStore` クラス |
| `apps/api/tests/test_prompt_generator.py` | PromptGenerator テスト |
| `apps/api/tests/test_prompt_store.py` | PromptStore テスト |

### 既存クラスの利用

| クラス | パス | 利用箇所 |
|---|---|---|
| `LiteLLMClient` | `app.services.llm.client` | `PromptGenerator` で LLM 呼び出し |
| `DocumentService` | `app.services.document_service` | テキストブロック取得 |
| `FormContext` | `app.domain.models.form_context` | フィールド + nearby_labels + データソース |
| `LabelCandidate` | `app.domain.models.form_context` | DirectionalFieldEnricher の nearby_labels |
| `StopWatch` | `app.infrastructure.observability.stopwatch` | 処理時間計測 |
| `PipelineStepLog` | `app.services.autofill_pipeline.step_log` | ステップログ |

---

## 14. Future Considerations

- **Vision Level 2の導入**: `generate_prompt` が nearby_labels の少ないフィールドに対して Vision LLM でページ画像を分析するバリエーション。フリーレイアウトフォームの精度が不足する場合に導入。
- **Embedding-based prompt search**: 蓄積が100件を超えた場合、フォームタイトルやフィールド構造の embedding で類似検索を高速化。
- **プロンプトの自動改善**: fill 結果のフィードバック（ユーザーの修正）を使って、専用プロンプトを自動的に改善するループ。`CorrectionTracker` のデータを活用。
- **バッチ処理最適化**: 同一フォーム種別の大量処理時、`PromptStore` のキャッシュ Hit で1件あたり3-5秒を実現。
