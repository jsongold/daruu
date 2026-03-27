# AnnotationAgent — 実装設計書

## 決定事項
- **LLMカスケード**: 2段（Gemini 2.5 Flash → Claude Sonnet 4.6）
- **初期フェーズ**: Template Fingerprint先行
- **言語/スタック**: Python（既存パイプラインと統合）
- **データストア**: Supabase（既存）

---

## 1. 全体アーキテクチャ

```
PDF Upload
  │
  ▼
┌─────────────────────────────────────────────┐
│  AnnotationAgent                            │
│                                             │
│  [Phase 0] TemplateFingerprinter            │
│    AcroForm構造hash → Supabase lookup       │
│    Hit → cached mapping返却 (<1s, $0)       │
│    Miss ↓                                   │
│                                             │
│  [Phase 1] SpatialScorer                    │
│    多特徴量ロジスティック回帰                │
│    confidence > 85 → 確定                   │
│    残り ↓                                   │
│                                             │
│  [Phase 2] LLMCascade                       │
│    Level A: Gemini 2.5 Flash ($0.30/M)      │
│    Level B: Claude Sonnet 4.6 ($3/M)        │
│    confidence閾値で停止                      │
│                                             │
│  [Phase 3] HumanReviewQueue                 │
│    低confidence → UI提示                     │
│    修正 → isManual=true保存                  │
│    → SpatialScorer再学習                     │
│    → TemplateCache更新                       │
│                                             │
│  → 結果返却 + Supabase保存                   │
└─────────────────────────────────────────────┘
```

---

## 2. ディレクトリ構成

```
annotation_agent/
├── __init__.py
├── agent.py                  # AnnotationAgent メインオーケストレーター
├── config.py                 # 設定・閾値・API keys
│
├── fingerprint/
│   ├── __init__.py
│   ├── hasher.py             # TemplateFingerprinter (3-level hash)
│   └── matcher.py            # TemplateMatcher (lookup + similarity)
│
├── scorer/
│   ├── __init__.py
│   ├── features.py           # 特徴量計算 (spatial features)
│   ├── model.py              # ロジスティック回帰 scorer
│   └── calibrator.py         # 信頼度キャリブレーション
│
├── llm/
│   ├── __init__.py
│   ├── base.py               # BaseLLMProvider (Protocol)
│   ├── gemini_provider.py    # Gemini 2.5 Flash
│   ├── claude_provider.py    # Claude Sonnet 4.6
│   ├── cascade.py            # LLMCascade オーケストレーター
│   ├── prompt_builder.py     # IVB座標プロンプト構築
│   └── response_parser.py    # LLM応答パース + バリデーション
│
├── models/
│   ├── __init__.py
│   ├── annotation.py         # AnnotationPair, Label, Field dataclasses
│   ├── template.py           # TemplateFingerprint, FieldMapping
│   └── result.py             # AnnotationResult, ConfidenceReport
│
├── storage/
│   ├── __init__.py
│   ├── supabase_repo.py      # Supabase CRUD
│   └── scorer_store.py       # Scorer model blob保存/読込
│
├── learning/
│   ├── __init__.py
│   ├── active_learner.py     # 不確実性サンプリング
│   └── retrainer.py          # バッチ再学習トリガー
│
└── tests/
    ├── test_fingerprint.py
    ├── test_scorer.py
    ├── test_llm_cascade.py
    ├── test_prompt_builder.py
    └── fixtures/
        └── sample_nenmatsu.json  # テスト用アノテーションデータ
```

---

## 3. データモデル

### 3.1 Core Dataclasses

```python
# annotation_agent/models/annotation.py

@dataclass
class BBox:
    """Normalized 0-1 coordinates"""
    x: float
    y: float
    w: float
    h: float
    
    def to_ivb(self) -> tuple[int, int, int, int]:
        """Convert to Integer-Valued Binning (0-999)"""
        return (
            int(self.x * 999),
            int(self.y * 999),
            int((self.x + self.w) * 999),
            int((self.y + self.h) * 999),
        )
    
    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

@dataclass
class Label:
    id: str
    text: str
    bbox: BBox
    page: int

@dataclass
class Field:
    id: str
    field_name: str
    field_type: str          # text, checkbox, radio
    bbox: BBox
    page: int

@dataclass
class AnnotationPair:
    label: Label
    field: Field
    confidence: float        # 0.0 - 1.0
    status: str              # "confirmed", "proposed", "rejected"
    is_manual: bool
    model_used: str | None   # "spatial", "gemini-flash", "claude-sonnet", "human"
    semantic_key: str | None # "applicant_name", "address" etc.
```

### 3.2 Template Models

```python
# annotation_agent/models/template.py

@dataclass
class TemplateFingerprint:
    id: str                  # UUID
    hash_level1: str         # PDF file ID
    hash_level2: str         # AcroForm structure SHA-256
    hash_level3: str | None  # Perceptual hash (per-page concat)
    form_name: str | None    # "年末調整" etc.
    field_count: int
    page_count: int
    created_at: datetime
    
@dataclass
class TemplateFieldMapping:
    template_id: str
    field_id: str
    field_name: str
    semantic_key: str        # human-readable key
    label_text: str          # matched label text
    label_bbox: BBox
    field_bbox: BBox
    page: int
    verified: bool           # at least one isManual=true confirmation
```

---

## 4. Supabase スキーマ

```sql
-- テンプレートフィンガープリント
CREATE TABLE template_fingerprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hash_level1 TEXT,                    -- PDF file ID
    hash_level2 TEXT NOT NULL,           -- AcroForm structure hash
    hash_level3 TEXT,                    -- Perceptual hash
    form_name TEXT,
    field_count INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_template_hash2 ON template_fingerprints(hash_level2);
CREATE INDEX idx_template_hash1 ON template_fingerprints(hash_level1);

-- テンプレート別フィールドマッピング（確定済み）
CREATE TABLE template_field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES template_fingerprints(id),
    field_id TEXT NOT NULL,              -- "Text3"
    field_name TEXT NOT NULL,            -- "Text3"
    semantic_key TEXT NOT NULL,          -- "applicant_name"
    label_text TEXT,                     -- "氏名"
    label_bbox JSONB,                    -- {x, y, w, h}
    field_bbox JSONB NOT NULL,
    page INTEGER NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(template_id, field_id)
);

-- 個別アノテーションペア（学習データ）
CREATE TABLE annotation_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,           -- 元のドキュメント
    template_id UUID REFERENCES template_fingerprints(id),
    label_id TEXT,
    label_text TEXT NOT NULL,
    label_bbox JSONB NOT NULL,
    label_page INTEGER NOT NULL,
    field_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_bbox JSONB NOT NULL,
    field_page INTEGER NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    is_manual BOOLEAN DEFAULT FALSE,
    model_used TEXT,                     -- "spatial", "gemini-flash", "claude-sonnet", "human"
    semantic_key TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pairs_template ON annotation_pairs(template_id);
CREATE INDEX idx_pairs_manual ON annotation_pairs(is_manual) WHERE is_manual = TRUE;

-- スコアラーモデル保存
CREATE TABLE scorer_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES template_fingerprints(id),
    model_type TEXT NOT NULL DEFAULT 'logistic_regression',
    model_blob BYTEA NOT NULL,           -- pickle
    feature_names JSONB NOT NULL,
    accuracy REAL,
    sample_count INTEGER,
    trained_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. Phase別 実装詳細

### Phase 1: Template Fingerprint（最初に実装）

**目的**: 既知テンプレートの即時マッピング返却（70s → <1s）

#### TemplateFingerprinter

```
入力: PDF file path or bytes
出力: TemplateFingerprint + Optional[list[TemplateFieldMapping]]

処理:
1. PDF読み込み → AcroFormフィールド一覧取得
2. Level 1 Hash: PDF trailer の /ID エントリ取得
3. Level 2 Hash: フィールド構造hash
   - fields = sort(fields, key=field_name)
   - raw = "|".join(f"{f.name}:{f.type}:{round(f.bbox)}" for f in fields)
   - hash = sha256(raw.encode()).hexdigest()
4. Supabase lookup:
   - hash_level2 で完全一致検索
   - Hit → template_field_mappings からマッピング取得、即座に返却
   - Miss → 新規テンプレートとして登録、後続Phaseへ
```

#### Hash Level 2 の正規化ルール

```
- フィールド名: そのまま（"Text1", "CheckBox3"）
- フィールドタイプ: "text" | "checkbox" | "radio" | "button" | "choice"
- BBox: 各座標を小数2桁で丸め（位置の微小差異を吸収）
- 連結: "{name}:{type}:{x1:.2f},{y1:.2f},{x2:.2f},{y2:.2f}"
- ソート: field_name の辞書順
- 区切り: "|"
- ハッシュ: SHA-256

例:
"CheckBox1:checkbox:0.12,0.34,0.14,0.36|Text1:text:0.25,0.08,0.45,0.10|Text2:text:0.25,0.12,0.45,0.14"
→ sha256 → "a3f8e2..."
```

#### 依存ライブラリ

```
pypdf >= 4.0          # AcroForm読み取り（pikepdf でも可）
imagehash >= 4.3      # Level 3 perceptual hash（Phase 1では後回し可）
supabase-py >= 2.0    # Supabase client
```

#### テスト戦略

```
1. 同一PDFファイル → 同一hash_level2 であること
2. 異なるメタデータを持つ同一構造PDF → 同一hash_level2
3. フィールドが1つ異なるPDF → 異なるhash_level2
4. 登録済みテンプレート → マッピング即時返却
5. 未登録テンプレート → None返却 + 新規登録
```

---

### Phase 2: SpatialScorer（Phase 1完了後）

**目的**: LLMなしで30% → 55-70%精度に改善

#### 特徴量一覧

```
1. dx_signed      : label右端 → field左端 の水平距離（正規化）
2. dy_signed      : label下端 → field上端 の垂直距離（正規化）
3. euclidean_dist : label中心 → field中心 のユークリッド距離
4. angle_deg      : label中心 → field中心 の角度（0-360）
5. nn_rank        : このフィールドはラベルの最近傍何位か（1=最近）
6. same_page      : 同一ページか (0/1)
7. label_keyword  : ラベルテキストのキーワードカテゴリ（辞書ベース）
8. field_type     : フィールドタイプ（text=0, checkbox=1, radio=2）
9. bbox_iou       : bboxの重なり率
10. size_ratio    : label面積 / field面積
```

#### 訓練フロー

```
1. annotation_pairs WHERE is_manual=TRUE を全件取得
2. 正例: 確認済みペア (label_i, field_j) → features → label=1
3. 負例: 同一ラベルの非マッチフィールド上位3件 → label=0
4. LogisticRegression(class_weight='balanced') で訓練
5. 5-fold CV で accuracy + calibration (ECE) 評価
6. model blob を scorer_models テーブルに保存
```

---

### Phase 3: LLM Cascade（Phase 2完了後）

**目的**: SpatialScorerで未確定のフィールドをLLMで解決

#### カスケードフロー

```
未確定フィールド一覧（confidence < 85 from Phase 2）
  │
  ▼
[Gemini 2.5 Flash] ─── バッチ: ページ単位でグループ化
  │                     各ページのフィールド + 候補ラベル5-10個
  │                     IVB座標 + few-shot例付きプロンプト
  │                     confidence閾値: 70
  │
  ├── confidence >= 70 → 確定
  │
  ▼ (残り)
[Claude Sonnet 4.6] ── 個別: 困難フィールドのみ
  │                      Vision入力: ページ画像 + フィールドメタデータ
  │                      cache_control: system promptをキャッシュ
  │                      confidence閾値: 50
  │
  ├── confidence >= 50 → 確定
  │
  ▼ (残り)
[Human Review Queue] ── confidence < 50 を人間に提示
```

#### プロンプトテンプレート（IVB形式）

```
System (cacheable):
あなたはPDFフォームのフィールド識別エキスパートです。
各フィールドに対して、最も関連するテキストラベルをマッチングしてください。

座標は0-999の整数で表現されています（左上が[0,0]、右下が[999,999]）。
一般的に、ラベルはフィールドの左側または上側に配置されます。

出力はJSON配列で、各要素は:
{"field_id": "Text3", "label_text": "氏名", "semantic_key": "applicant_name", "confidence": 85}

### 確認済みマッピング例（このフォーム固有）:
- "氏名" [120,150,180,170] → Text3 [200,148,450,172] → applicant_name (confidence: 95)
- "住所" [120,200,180,220] → Text5 [200,198,650,222] → address (confidence: 92)
[... 10-30 confirmed examples ...]

User (dynamic):
以下のフィールドのラベルを特定してください:

フィールド一覧:
- Text7 [bbox: 200,280,450,302] 候補ラベル: "電話番号"[120,278,180,298], "FAX"[120,310,160,330], "携帯"[480,278,520,298]
- Text8 [bbox: 500,280,750,302] 候補ラベル: "FAX"[120,310,160,330], "携帯"[480,278,520,298]
[...]
```

#### LLMProvider Protocol

```python
class LLMProvider(Protocol):
    model_name: str
    cost_per_m_input: float
    cost_per_m_output: float
    
    async def identify_fields(
        self,
        fields: list[Field],
        candidate_labels: dict[str, list[Label]],  # field_id → candidate labels
        confirmed_examples: list[AnnotationPair],
        page_image: bytes | None = None,
    ) -> list[AnnotationPair]: ...
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float: ...
```

---

### Phase 4: Active Learning（Phase 3完了後）

#### 不確実性サンプリング

```
Human Review Queue 優先順位:
1. confidence が 40-60 の範囲（最も不確実）
2. 同一テンプレートで他ユーザーが異なる結果を出したもの
3. ラベルテキストが辞書にないもの（新出パターン）

再学習トリガー:
- isManual=true が 10件蓄積 → SpatialScorer再訓練
- 同一テンプレートのフィールド90%以上が verified → テンプレートキャッシュ確定
```

---

## 6. Agent メインフロー（擬似コード）

```python
class AnnotationAgent:
    def __init__(self, config: AgentConfig):
        self.fingerprinter = TemplateFingerprinter(config)
        self.scorer = SpatialScorer(config)
        self.cascade = LLMCascade(config)
        self.repo = SupabaseRepository(config)
    
    async def annotate(
        self,
        pdf_path: str,
        labels: list[Label],
        fields: list[Field],
        user_data: dict | None = None,
    ) -> AnnotationResult:
        
        # Phase 0: Template lookup
        fingerprint = self.fingerprinter.compute(pdf_path, fields)
        cached = await self.repo.get_template_mappings(fingerprint.hash_level2)
        
        if cached and cached.coverage >= 0.90:  # 90%以上のフィールドがマッピング済み
            return AnnotationResult(
                pairs=cached.mappings,
                source="template_cache",
                latency_ms=elapsed,
                cost_usd=0.0,
            )
        
        # Phase 1: Spatial scoring
        scored_pairs = self.scorer.score_all(labels, fields)
        confirmed = [p for p in scored_pairs if p.confidence >= 0.85]
        uncertain = [p for p in scored_pairs if p.confidence < 0.85]
        
        if not uncertain:
            return AnnotationResult(pairs=confirmed, source="spatial_scorer", ...)
        
        # Phase 2: LLM cascade (only for uncertain fields)
        uncertain_fields = [p.field for p in uncertain]
        candidate_labels = self._get_candidates(uncertain_fields, labels, top_k=10)
        confirmed_examples = [p for p in scored_pairs if p.confidence >= 0.85]
        
        llm_results = await self.cascade.identify(
            fields=uncertain_fields,
            candidate_labels=candidate_labels,
            confirmed_examples=confirmed_examples[:30],  # few-shot上限
        )
        
        all_pairs = confirmed + llm_results.confirmed
        review_queue = llm_results.uncertain
        
        # 保存
        await self.repo.save_annotation_pairs(all_pairs)
        await self.repo.update_template_mappings(fingerprint, all_pairs)
        
        return AnnotationResult(
            pairs=all_pairs,
            review_queue=review_queue,
            source="cascade",
            latency_ms=elapsed,
            cost_usd=llm_results.total_cost,
        )
```

---

## 7. 設定

```python
@dataclass
class AgentConfig:
    # Supabase
    supabase_url: str
    supabase_key: str
    
    # 閾値
    template_cache_coverage_threshold: float = 0.90
    spatial_confidence_threshold: float = 0.85
    llm_level_a_confidence_threshold: float = 0.70
    llm_level_b_confidence_threshold: float = 0.50
    
    # LLM
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"
    
    # Scorer
    scorer_min_samples: int = 30
    scorer_retrain_interval: int = 10  # 新規isManual件数
    
    # Few-shot
    max_few_shot_examples: int = 30
    max_candidate_labels: int = 10
    
    # コスト制御
    max_cost_per_document: float = 1.0  # USD
    
    # Feature flags
    enable_gemini: bool = True
    enable_claude: bool = True
    enable_vision: bool = False  # Phase 3+で有効化
```

---

## 8. 開発ロードマップ

```
Week 1: Phase 1 — Template Fingerprint
  Day 1-2: データモデル + Supabaseスキーマ作成
  Day 3-4: TemplateFingerprinter (hash_level1, hash_level2)
  Day 5:   Supabase lookup + テスト

Week 2: Phase 2 — SpatialScorer
  Day 1-2: 特徴量計算エンジン
  Day 3-4: ロジスティック回帰 + キャリブレーション
  Day 5:   テスト + 既存パイプライン統合

Week 3: Phase 3 — LLM Cascade
  Day 1:   LLMProvider Protocol + PromptBuilder (IVB)
  Day 2-3: Gemini 2.5 Flash provider
  Day 4:   Claude Sonnet 4.6 provider + cache_control
  Day 5:   Cascade orchestrator + コスト追跡

Week 4: Phase 4 — Active Learning + 最適化
  Day 1-2: Human Review Queue + 不確実性サンプリング
  Day 3:   SpatialScorer 再学習パイプライン
  Day 4:   Prompt Caching最適化 + コスト監視
  Day 5:   E2Eテスト + ドキュメント
```

---

## 9. 既存パイプラインとの統合ポイント

```
現在のパイプライン:
  DirectionalFieldEnricher → FillPlanner → LLM → 結果

変更後:
  AnnotationAgent.annotate() → field mappings
    ↓
  FillPlanner（簡略化: field mappings + user data → fill values）
    ↓
  PDF Fill

AnnotationAgentが返すのは「各フィールドが何を意味するか」のマッピング。
FillPlannerは「そのフィールドにどんな値を入れるか」だけに専念。
DirectionalFieldEnricherは段階的に廃止（AnnotationAgentが上位互換）。
```

---

## 10. Claude Code 実装指示プロンプト（Phase 1用）

```
# AnnotationAgent Phase 1: Template Fingerprint

## Context
PDF form autofill systemのフィールド識別を高速化するため、
テンプレートフィンガープリントによるキャッシュシステムを構築する。

## 要件
1. annotation_agent/ ディレクトリ構成を上記設計書に従い作成
2. pypdf を使用してAcroFormフィールド一覧を取得
3. フィールド構造からSHA-256ハッシュを計算（hash_level2）
4. Supabase にテンプレート情報を保存・検索
5. キャッシュヒット時は保存済みマッピングを即座に返却
6. 全てのデータモデルは dataclass で定義
7. async/await パターンを使用
8. pytest でテストを作成

## 技術制約
- Python 3.11+
- pypdf >= 4.0
- supabase-py >= 2.0
- 型ヒント必須
- docstring必須（日本語OK）

## NOT in scope (Phase 1)
- LLM呼び出し
- SpatialScorer
- perceptual hash (Level 3)
- Active Learning
```
