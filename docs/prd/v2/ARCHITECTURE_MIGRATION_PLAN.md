# Document Auto-Fill システム：As-Is → To-Be アーキテクチャ分析レポート

> **作成日**: 2026-02-13
> **更新日**: 2026-02-13（命名改善: Compiler→FormContextBuilder, Decision Engine→FillPlanner, Executor→FormRenderer, Learning Adapter→CorrectionTracker）
> **目的**: 既存の Document Auto-Fill 実装を、提案する新アーキテクチャ（FormContextBuilder → 1回LLM → FormRenderer）と比較し、過不足・リスク・移行計画を具体化する

---

## 目次

1. [現行アーキテクチャの要約（As-Is）](#1-現行アーキテクチャの要約as-is)
2. [To-Be アーキテクチャ概要と命名方針](#to-be-アーキテクチャ概要と命名方針)
3. [新アーキテクチャとのマッピング（As-Is → To-Be 対応表）](#3-新アーキテクチャとのマッピングas-is--to-be-対応表)
4. [ギャップ分析（過不足の洗い出し）](#4-ギャップ分析過不足の洗い出し)
5. [LLM呼び出し削減の設計案](#5-llm呼び出し削減の設計案to-beの具体案)
6. [移行計画（段階的リファクタリング）](#6-移行計画段階的リファクタリング)
7. [追加の確認事項（不足情報リスト）](#7-追加の確認事項不足情報リスト)

---

## 1. 現行アーキテクチャの要約（As-Is）

### 1.1 コンポーネント/モジュール一覧

| コンポーネント | 役割 | 入力 | 出力 | レイヤー |
|---|---|---|---|---|
| **Orchestrator** | パイプライン全体制御、ステージ遷移、リトライ判定 | `job_id`, `RunMode` | 更新された `JobContext` | 制御 |
| **DecisionEngine** | 次アクション決定（終了/リトライ/ブロック判定） | `JobContext`, `StageResult` | `NextAction` | 制御（純決定論） |
| **PipelineExecutor** | 個別ステージの実行と JobContext 更新 | `job_id`, `PipelineStage` | `(JobContext, StageResult)` | 制御 |
| **StructureLabellingService** | 文書構造検出（box/label/table 検出 → LLM リンク） | PDF画像、テキストブロック | `StructureLabellingResult`（fields, evidence） | サービス |
| **FieldLabellingAgent** | ラベル⇔入力ボックスの意味的リンク | labels, boxes, spatial context | `LinkedField[]`, `StructureEvidence[]` | エージェント（**LLM**） |
| **MappingService** | ソース→ターゲットフィールド対応付け | `MappingRequest` | `MappingResult`（mappings, questions） | サービス |
| **MappingAgent** | 曖昧マッピングの LLM 解決、バッチ推論 | source_field, candidates, targets | `MappingItem`, `BatchMappingOutput` | エージェント（**LLM**） |
| **ExtractService** | ソース文書からの値抽出（native PDF → OCR → LLM） | `ExtractRequest` | `ExtractResult`（extractions, errors） | サービス |
| **ValueExtractionAgent** | 候補解決、正規化、衝突検出、質問生成 | field, candidates, context | `ValueCandidate`, 正規化値, conflict | エージェント（**LLM**） |
| **FillService** | PDF 記入（AcroForm 直接 or テキストオーバーレイ） | `FillRequest` | `FillResult`（filled PDF, issues） | サービス（非LLM） |
| **VisionAutofillService** | データソース→フォームフィールド一括マッチ | `VisionAutofillRequest` | `VisionAutofillResponse` | サービス（**LLM 1回**） |
| **MCP Server** | Claude Desktop 連携（フォーム登録、値設定、PDF 出力） | MCP tool calls | フォームメタデータ、PDF | 外部インターフェース |
| **DataSourceRepository** | データソース永続化・取得 | conversation_id | `DataSource[]` | インフラ |
| **TextExtractionService** | データソースからのテキスト抽出 | `DataSource` | extracted_fields, raw_text | サービス（非LLM） |

### 1.2 データフロー

#### パイプライン v1（マルチステップ）

```
PDF Upload
  → Ingest（PyMuPDF: ページ画像生成、AcroForm フィールド検出）
  → Structure Detection（box/label/table 候補の決定論抽出）
  → FieldLabelling（★LLM: ページ単位で label⇔box 意味リンク）
  → Mapping（RapidFuzz → ★LLM: 曖昧フィールド単位で意味マッチ）
  → Extract（Native PDF/OCR → ★LLM: 曖昧候補の解決・正規化・衝突検出）
  → Adjust（オーバーフロー/レイアウト調整、非LLM）
  → Fill（AcroForm/Overlay 描画、非LLM）
  → Review（品質検査、issue 生成、非LLM）
```

#### VisionAutofill v2（単一 LLM 呼び出し）

```
フォームフィールド定義 + データソース
  → TextExtractionService（非LLM: PDF/CSV テキスト抽出）
  → プロンプト構築（フィールド JSON + 抽出データ + ルール）
  → ★LLM 1回呼び出し（フォーム全体一括マッチ）
  → JSON 解析 → FilledField[]
```

### 1.3 LLM 呼び出し点の詳細

| # | コンポーネント | 呼び出し粒度 | 回数/フォーム | 入力内容 | 用途 |
|---|---|---|---|---|---|
| 1 | **FieldLabellingAgent** | **ページ単位** | N pages | labels+boxes 位置情報、spatial clusters、言語検出 | ラベル⇔ボックスの意味リンク |
| 2 | **MappingAgent.resolve_mapping** | **フィールド単位** | M 曖昧フィールド | source_field, candidates, targets | 曖昧マッピング解決 |
| 3 | **MappingAgent.generate_question** | **フィールド単位** | Q 未解決フィールド | source_field, candidates | フォローアップ質問生成 |
| 4 | **MappingAgent.infer_mappings_batch** | **バッチ** | 1回（LLM_ONLY 時） | 全 source/target fields | バッチマッピング推論 |
| 5 | **ValueExtractionAgent.resolve_candidates** | **フィールド単位** | K 曖昧フィールド | field, candidates, context | 候補選択 |
| 6 | **ValueExtractionAgent.normalize_value** | **フィールド単位** | L 要正規化フィールド | field, value, format | 値正規化 |
| 7 | **ValueExtractionAgent.detect_conflicts** | **フィールド単位** | P 衝突候補 | field, candidates | 衝突検出 |
| 8 | **ValueExtractionAgent.generate_question** | **フィールド単位** | R 不明フィールド | field, reason, candidates | 質問生成 |
| 9 | **VisionAutofillService** | **フォーム単位** | **1回** | fields JSON + data sources text + rules | データソース→フィールド全体マッチ |

#### 最悪ケースの見積もり（10ページ、50フィールド、30%曖昧）

- FieldLabelling: 10回
- Mapping: 15回（resolve） + 5回（question）
- Extract: 15回（resolve） + 15回（normalize） + 5回（conflict） + 5回（question）
- **合計: 約70回の LLM 呼び出し**

VisionAutofill v2 は既に **1回** で完結している。

### 1.4 決定論ロジックの現状

| 処理 | 決定論？ | 実装場所 | 備考 |
|---|---|---|---|
| PDF 構造解析（box/label 検出） | ○ | StructureLabellingService | PyMuPDF + OpenCV |
| ラベル⇔ボックスリンク | △（LLM メイン + proximity fallback） | FieldLabellingAgent | proximity fallback は決定論 |
| 文字列マッチング | ○ | MappingService._find_candidates | RapidFuzz |
| ユーザールール適用 | ○ | MappingService._apply_user_rules | パターンマッチ |
| テンプレート履歴適用 | ○ | MappingService._apply_template_history | DB 参照 |
| Native PDF テキスト抽出 | ○ | ExtractService._try_native_extraction | PyMuPDF |
| OCR | ○（外部依存） | ExtractService._try_ocr_extraction | - |
| PDF 記入（AcroForm/Overlay） | ○ | FillService | PyMuPDF + ReportLab |
| レイアウト検証（overlap 検出） | ○ | FillService._check_overlaps | 幾何計算 |
| DecisionEngine（次アクション判定） | ○ | DecisionEngine | ルールベース分岐 |
| ルールベース autofill（VisionAutofill fallback） | ○ | VisionAutofillService._rule_based_autofill | 文字列正規化+部分一致 |

---

## 2. To-Be アーキテクチャ概要と命名方針

### 命名ガイドライン

- **動詞/動作** を含め、そのサービスが「何をするか」を名前だけで読み取れるようにする
- **ドメイン語彙**（Form, Fill, Field, Render）を使い、汎用語（Compiler, Executor, Engine）を避ける
- **データ構造名**はサービスの出力と対応させ、誰が生成し誰が消費するかが一目でわかるようにする

### サービス命名

| # | 旧名（抽象的） | 新名 | 責務（1文） | LLM |
|---|---|---|---|---|
| S1 | Compiler | **FormContextBuilder** | フォーム構造+データソース+候補を収集・正規化し、RuleAnalyzer の出力と merge して `FormContext` を組み立てる | 非LLM |
| S2 | Decision Engine | **FillPlanner** | `FormContext` を受け取り、LLM 1回の推論で各フィールドの fill/skip/ask_user を計画する | **LLM 1回** |
| S3 | Executor | **FormRenderer** | `FillPlan` に従って PDF に値を描画し、検証結果付きの完成 PDF を出力する | 非LLM |
| S4 | Learning Adapter | **CorrectionTracker** | ユーザーの修正差分を収集・分類し、FormContextBuilder/FillPlanner の改善に資産化する | 非LLM（非同期） |
| S5 | （新規） | **RuleAnalyzer** | ルールドキュメントを LLM で読解し、関連スニペットを抽出・**永続化**する。2回目以降は DB 参照でスキップ。FormContextBuilder と並行実行 | **LLM**（初回のみ） |

### データ構造命名

| 旧名（抽象的） | 新名 | 生成元 → 消費先 | 内容 |
|---|---|---|---|
| SemanticContextBundle | **FormContext** | FormContextBuilder → FillPlanner | フォーム定義 + 候補 + 制約 + データ + ルール + 出典 |
| FormSpec | **FormFieldSpec** | FormContextBuilder 内部 | 個別フィールドの構造定義（bbox, type, label 候補 top-k, required） |
| SemanticPlan | **FillPlan** | FillPlanner → FormRenderer | 各フィールドの記入判断（action, value, confidence, rule_trace） |
| FieldDecision | **FieldFillAction** | FillPlan の要素 | 1 フィールドの判断結果（fill/skip/ask_user + 値 + 根拠） |
| render_report | **RenderReport** | FormRenderer → API/UI | 描画結果（成功/失敗/警告）+ validation_result |
| （なし） | **CorrectionRecord** | CorrectionTracker → DB | 修正差分（before/after + 分類 + FillPlan スナップショット） |
| （なし） | **RuleSnippet** | RuleAnalyzer → **DB（永続化）** → FormContext → FillPlanner | ルールドキュメントから LLM が抽出・永続化した断片（セクション名+テキスト+関連フィールド+判断理由）。2回目以降は DB 参照 |

### To-Be データフロー

```
  オンライン（フォーム処理時） ── 並行実行フェーズ + 統合フェーズ

  ユーザー入力: 申告書PDF + ルールDoc(不定) + データソース
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
  ┌──────────────────────┐   ┌──────────────────────────┐
  │ FormContextBuilder   │   │   RuleAnalyzer             │
  │ （非LLM）            │   │   （LLM or DB参照）        │
  │                      │   │                            │
  │ PDF構造検出          │   │ doc_hash で DB 検索        │
  │ データソース抽出      │   │ ├─ HIT → DB から取得      │
  │ 候補生成(fuzzy/prox) │   │ └─ MISS → LLM で解析      │
  │ 正規化（決定論）     │   │          → DB に永続化     │
  │                      │   │ → RuleSnippet[] 生成       │
  │ → PartialContext     │   │                            │
  └──────────┬───────────┘   └────────────┬───────────────┘
             │                           │
             └─────────────┬─────────────┘
                           ▼
                  ┌─────────────────┐
                  │  FormContext     │
                  │  統合（merge）   │
                  │  PartialContext  │
                  │  + RuleSnippet[] │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────────┐       ┌──────────────────────┐
                  │    FillPlanner      │       │   FormRenderer       │
                  │    （LLM 1回）      │       │   （非LLM）          │
                  │                     │       │                      │
                  │ FormContext →       │       │ FillPlan →           │
                  │ LLM 1回呼び出し →  │──────▶│ PDF描画（AcroForm/   │
                  │ FillPlan生成        │       │   Overlay）          │
                  │                     │       │ 検証(required/format/│
                  │ fill / skip /       │       │   overflow/overlap)  │
                  │ ask_user を判定     │       │ RenderReport 出力    │
                  └─────────────────────┘       │ → 完成PDF + 検証結果 │
                                                └──────────┬───────────┘
                                                           │
                                                ┌──────────▼───────────┐
                                                │  CorrectionTracker    │
                                                │  （非同期・オプション）│
                                                └──────────────────────┘
```

**要点**:
- **RuleAnalyzer** はオンラインで FormContextBuilder と**並行実行**される。ドキュメントの種類は不定（ボラタイル）であり、事前登録ステップは不要。
- **初回**: LLM でルールドキュメントを解析し、`RuleSnippet[]` を生成 → **DB に永続化**する。
- **2回目以降**: 同一ドキュメント（`doc_hash` 一致）の場合は DB から取得し、**LLM 呼び出しをスキップ**する。
- 両サービスの出力を **merge** して `FormContext` を構築し、FillPlanner に渡す。
- LLM 呼び出し: 初回は **2回**（RuleAnalyzer + FillPlanner、並行実行）、2回目以降は **1回**（FillPlanner のみ）。

---

## 3. 新アーキテクチャとのマッピング（As-Is → To-Be 対応表）

| 既存モジュール | To-Be サービス | 現状の責務 | To-Be での責務 | 差分 | 方針 |
|---|---|---|---|---|---|
| **StructureLabellingService**（構造検出部分） | **FormContextBuilder** | box/label/table 候補の決定論抽出 | `FormFieldSpec` 生成（フィールドID, bbox, type, required, label 候補） | `FormFieldSpec` 構造体が未定義 | FormContextBuilder の中核として移動 |
| **FieldLabellingAgent**（LLM リンク） | **FillPlanner** | ページ単位 LLM で label⇔box リンク | FillPlanner の推論項目の一部として統合 | ページ単位呼び出し → フォーム単位に統合 | 空間 context 付き label 候補を FormContextBuilder が生成し、最終リンクは FillPlanner に委譲 |
| **FieldLabellingAgent**（proximity fallback） | **FormContextBuilder** | LLM 不可時の近接マッチ | FormContextBuilder の label 候補スコアリング（top-k 候補生成） | 既にある決定論ロジックを流用可能 | FormContextBuilder に統合、候補を 3-7 個に制限 |
| **MappingService**（全体） | **FormContextBuilder** + **FillPlanner** | fuzzy match → LLM 解決 | fuzzy match 部分は FormContextBuilder、最終決定は FillPlanner | 責務分割が必要 | `_find_candidates`, `_apply_user_rules`, `_apply_template_history` を FormContextBuilder に、`resolve_mapping` を FillPlanner に |
| **MappingAgent** | **FillPlanner** | 曖昧マッピングの LLM 解決 | `FillPlan` の一部として一括判定 | フィールド単位 → フォーム単位統合 | FillPlanner のプロンプトにマッピング JSON 候補を含める |
| **ExtractService**（native/OCR 部分） | **FormContextBuilder** | テキスト抽出、候補生成 | 正規化済み入力データ生成 | 出典 (provenance) 情報の構造化が必要 | FormContextBuilder に移動、候補に source/evidence を付与 |
| **ValueExtractionAgent** | **FillPlanner** | 候補解決、正規化、衝突検出 | 一括推論の一部（正規化の一部は決定論化可能） | フィールド単位 → フォーム単位統合。日付/電話の正規化は決定論化すべき | 正規化ルールを FormContextBuilder（regex/変換表）に、意味判断のみ FillPlanner に |
| **FillService** | **FormRenderer** | AcroForm/Overlay PDF 記入 | `FillPlan` 入力 → PDF 出力 | ほぼそのまま利用可能 | FormRenderer の中核 |
| **FillService._check_overlaps** | **FormRenderer** | オーバーラップ検出 | `RenderReport.validation_result` の一部 | 検証ロジック強化の余地あり（required/format） | FormRenderer 内の検証サブモジュールに |
| **VisionAutofillService** | **FillPlanner（類似）** | フォーム全体 1回 LLM 呼び出し | FillPlanner の原型 | `FillPlan` 構造体なし、ルール適用が弱い | FillPlanner のプロトタイプとして拡張 |
| **VisionAutofillService._rule_based_autofill** | **FormContextBuilder** | LLM 不可時の文字列マッチ fallback | FormContextBuilder の候補スコアリングロジック | 機能は重複（MappingService と類似） | FormContextBuilder に統合 |
| **TextExtractionService** | **FormContextBuilder** | データソースからテキスト抽出 | 入力データの正規化・構造化 | 出典情報付与が必要 | FormContextBuilder に統合 |
| **DecisionEngine（Orchestrator 内）** | **Orchestrator（維持）** | パイプラインの次ステップ判定 | FormContextBuilder → FillPlanner → FormRenderer の制御 | ステージ構成が 3+1 に簡素化 | ステージ定義をリファクタ |
| **DataSourceRepository** | **FormContextBuilder（入力）** | データソース永続化・取得 | FormContextBuilder 入力のデータソース取得 | 変更不要 | そのまま利用 |
| **PromptAttemptRepository** | **CorrectionTracker** | プロンプト試行履歴の保存 | ユーザー修正差分の蓄積・分析 | 修正差分（diff）の構造化が未実装 | CorrectionTracker の基盤として拡張 |
| **MCP Server** | **外部 IF（維持）** | Claude Desktop 連携 | FormContextBuilder/FillPlanner/FormRenderer へのプロキシ | 内部呼び出し先の変更 | API 層のみリファクタ |
| **Orchestrator** | **Orchestrator（簡素化）** | 8 ステージのパイプライン制御 | 3 ステージ（Build → Plan → Render）制御 | ステージ数削減 | 段階的にステージを統合 |

---

## 4. ギャップ分析（過不足の洗い出し）

### 4.1 Missing（必要だが存在しない）

1. **`FormContext` のデータ構造**
   - 現状：各サービスが独自の入出力モデルを持ち、統一的な中間表現がない
   - 必要：`FormFieldSpec`（フィールド定義+bbox+type+required+label 候補 top-k） + 制約 + ルールテキスト + 正規化済み入力データ + 出典/provenance を統合した単一構造体

2. **`FillPlan` のデータ構造**
   - 現状：`VisionAutofillResponse` の `FilledField` が最も近いが、`canonical_key`, `fill|skip|ask_user` 判定, `formatter`, `rule_trace` が欠落
   - 必要：各フィールドの判断結果を `FieldFillAction` として構造化した中間表現

3. **ルールドキュメントの読解パイプライン（RuleAnalyzer）**
   - 現状：`VisionAutofillRequest.rules` は `list[str]`（ユーザーが手入力した短文）、MappingService の `UserRule` はパターンマッチのみ
   - 課題：実際の記入要領・法令ガイドライン等は数十〜数百ページの自然言語ドキュメントであり、種類も不定（ボラタイル）。丸ごと LLM に渡すとトークン超過になるが、関連セクションの切り出しの仕組みが存在しない
   - 必要：リクエスト毎にルールドキュメントを LLM で読解し、関連スニペットだけを `FormContext` に載せる並行実行サービス（後述: セクション 5.4 RuleAnalyzer）

4. **出典/Provenance の統一追跡**
   - 現状：`Evidence` モデルは存在するが、FormContextBuilder から最終 PDF までの一貫した追跡チェーンがない
   - 必要：各値がどのデータソース → どの抽出方法 → どの候補 → どの判断根拠で確定したかの完全な記録

5. **検証の体系化（FormRenderer 側）**
   - 現状：`FillService._check_overlaps` のみ（幾何的重複チェック）
   - 不足：required フィールド未入力検証、format 検証（日付形式、数値範囲）、overflow 検証（テキスト長 vs ボックスサイズ）

6. **`RenderReport` の出力**
   - 現状：`FillResult` に `issues[]` はあるが、フィールドごとの描画成否レポートが構造化されていない
   - 必要：各フィールドの描画結果（成功/失敗/警告/スキップ）+ 理由

7. **CorrectionTracker（ユーザー修正差分の資産化）**
   - 現状：`PromptAttemptRepository` がプロンプト試行を保存しているが、ユーザーの修正差分（before/after diff）の収集・分類・フィードバックループは未実装
   - `FieldEdit` モデルと `EditRepository` は存在するが、学習用の分類（LLM 判断ミス/ルール不足/データ不足等）が欠落

### 4.2 Excess（存在するが新設計では不要/縮小）

1. **フィールド単位の LLM エージェント呼び出し**
   - `ValueExtractionAgent.resolve_candidates` / `normalize_value` / `detect_conflicts` / `generate_question` の 4 メソッド × フィールド数 → 全廃
   - `MappingAgent.resolve_mapping` / `generate_question` のフィールド単位呼び出し → 全廃

2. **ページ単位の FieldLabelling LLM 呼び出し**
   - `FieldLabellingAgent._call_llm` のページ単位呼び出し → FillPlanner に統合

3. **複数の処理戦略（LOCAL_ONLY / LLM_ONLY / HYBRID / LLM_WITH_LOCAL_FALLBACK）**
   - To-Be では「FormContextBuilder（非LLM）→ FillPlanner（LLM 1回）→ FormRenderer（非LLM）」の固定フローとなるため、既存の 4 戦略分岐は不要になる
   - ただし段階的移行期間中は HYBRID 戦略を維持

### 4.3 Ambiguous（境界が曖昧で分割が必要）

1. **MappingService の責務分割**
   - 文字列マッチング（`_find_candidates`）は FormContextBuilder → 候補生成
   - LLM 解決（`resolve_mapping`）は FillPlanner → 最終判定
   - ユーザールール/テンプレート履歴は FormContextBuilder → 制約情報として
   - **判断ポイント**: `confidence_threshold` による自動確定は FormContextBuilder で行うか FillPlanner で行うか

2. **値正規化の切り分け**
   - 決定論化可能：日付変換（和暦→西暦）、全角→半角、電話番号フォーマット、郵便番号フォーマット → **FormContextBuilder**
   - LLM 必要：曖昧な表記（「令和」の曖昧表記、住所の略記展開等） → **FillPlanner**
   - 現状の `ValueExtractionAgent.normalize_value` は全て LLM に委ねている

3. **FieldLabelling の空間解析 vs 意味解析**
   - 近接スコアリング、方向計算、クラスタリングは全て決定論 → **FormContextBuilder** で候補生成
   - 意味的リンク判定（「この「氏名」ラベルはこのボックスの名前フィールドである」）→ **FillPlanner**
   - **判断ポイント**: 高信頼度（confidence > 0.9）の proximity リンクを FormContextBuilder で確定して FillPlanner に渡さないか

4. **VisionAutofillService vs パイプライン v1 の統合**
   - 現在 2 つの独立フローが並存しているが、To-Be ではどちらをベースにするか
   - VisionAutofill はフォーム 1回 LLM で To-Be に近いが、構造解析（FieldLabelling 相当）を行っていない

### 4.4 Unknown（仕様不確定/判断保留）

1. **OCR の位置づけ**: FormContextBuilder の内部処理か、別サービスか
2. **ルールドキュメント**: 元ドキュメントの形式（PDF? Word? HTML?）、分量（ページ数）、1リクエストあたりの添付ドキュメント数の上限が未確定。種類は不定（ボラタイル）であることは確定
3. **フォーム間依存**: 複数フォーム間の値参照が必要なケース（例：確定申告書の値を住民税申告書に転記）の対応方針
4. **バッチ処理**: 複数フォームを同時処理する場合の `FormContext` 共有範囲

---

## 5. LLM 呼び出し削減の設計案（To-Be の具体案）

### 5.1 現行 LLM 呼び出し点の統合設計

| 現行呼び出し | FormContextBuilder で前処理 | FillPlanner で一括推論 | FormRenderer で後処理 |
|---|---|---|---|
| **FieldLabelling**（ページ単位） | label 候補 top-5 を box ごとに計算（proximity+direction+semantic スコア付き）。高信頼リンク（score>0.9）は pre-linked として確定 | 未確定の label⇔box リンクを判定。`FormFieldSpec` 内の空間 context 付き候補から最適リンクを選択 | なし |
| **Mapping.resolve_mapping**（フィールド単位） | RapidFuzz 候補 top-5 + ユーザールール + テンプレート履歴 → 候補リスト生成 | source → target の最終マッピングを一括判定 | なし |
| **Mapping.infer_batch**（バッチ） | 同上 | 統合（上記と同一呼び出し内） | なし |
| **Extract.resolve_candidates**（フィールド単位） | Native PDF + OCR の候補を出典付きで列挙 | 各フィールドの最適候補選択を一括判定 | なし |
| **Extract.normalize_value**（フィールド単位） | 決定論正規化（和暦→西暦、全角半角、電話、郵便番号）を FormContextBuilder で実行 | 決定論で処理不可な曖昧正規化のみ FillPlanner が判定 | formatter 適用 |
| **Extract.detect_conflicts**（フィールド単位） | 候補値の文字列比較で明らかな重複排除 | 意味的衝突の検出を一括判定 | なし |
| **質問生成（Extract/Mapping）** | なし | `ask_user` 判定時に理由と選択肢を生成 | なし |
| **VisionAutofill**（フォーム 1回） | データソーステキスト抽出 + フィールド候補マッチング | **これが FillPlanner の原型** | JSON 解析 → FilledField |

### 5.2 FillPlanner への統合プロンプト設計

FillPlanner は以下を **1回の呼び出し** で判定する：

```
入力: FormContext
  ├── form_fields: [{                      # FormFieldSpec の配列
  │     field_id, bbox, type,
  │     label_candidates: [{text, score, direction}],
  │     required, format_constraint
  │   }]
  ├── data_sources: [{
  │     source_id, source_name,
  │     extracted_kv: {key: value},
  │     raw_text_snippet
  │   }]
  ├── mapping_candidates: [{
  │     source_key, target_field_id,
  │     similarity_score, match_reason
  │   }]
  ├── rule_snippets: [{                # RuleAnalyzer（並行実行）が LLM で抽出した断片
  │     source_doc: "記入要領2025.pdf",
  │     section: "第3章 所得控除",
  │     text: "...該当する自然言語テキスト...",
  │     field_ids: [field_3, field_7],
  │     relevance_reason: "医療費控除の記入条件を定義"
  │   }]
  ├── user_rules: ["ユーザーが手入力した短文ルール"]
  └── provenance_context: {
        source_document_type,
        past_submissions[]
      }

出力: FillPlan
  └── actions: [{                          # FieldFillAction の配列
        field_id,
        canonical_key,          // 正規化されたフィールド名
        action: fill|skip|ask_user,
        value,                  // fill 時のみ
        source,                 // 値の出典
        formatter,              // 適用するフォーマッタ（date_jp, currency, etc.）
        confidence,
        rule_trace: [rule_id],  // 適用されたルール
        reasoning               // 判断根拠（短文）
      }]
```

### 5.3 FormContext 圧縮戦略

トークン肥大を防ぐ具体策：

#### 5.3.1 フィールドクラスタリング

- ページ/セクション単位でグループ化し、セクションヘッダは 1回だけ記載
- 同一 type のフィールドは compact 表現（例：`dates: [field_3, field_7, field_12]`）

#### 5.3.2 候補キーの絞り込み（3〜7件制限）

- label 候補: FormContextBuilder が proximity+semantic スコアで top-3 に絞り込み
- mapping 候補: RapidFuzz score > 0.4 の top-5 に制限
- 抽出値候補: confidence > 0.3 の top-3 に制限
- **高信頼候補（score > 0.9）は pre-decided として候補から除外** し、FillPlanner への入力量を削減

#### 5.3.3 ルールドキュメント断片の制御

- **RuleAnalyzer**（並行実行サービス）がルールドキュメントを LLM で読解し、関連 `RuleSnippet[]` を抽出（詳細はセクション 5.4）
- 抽出された `rule_snippets` は FormContext に merge する際、上限付きで制御（例: 最大 5 スニペット、合計 1,500 tokens 以内）。relevance スコアで優先度付き truncation
- ユーザーが手入力した短文ルール（`user_rules`）はそのまま全量を載せる（通常は数行のため影響小）

#### 5.3.4 データソースの圧縮

- raw_text は FormContextBuilder が KV 抽出済みなら送らない（extracted_kv のみ）
- 未抽出の場合のみ raw_text の先頭 500 文字をスニペットとして送付
- フィールドに無関係なデータソースキーは除外（関連スコアでフィルタ）

#### 5.3.5 目標トークン量

`FormContext` 全体で **4,000〜8,000 tokens**（50 フィールドの場合）：

| 項目 | 見積もり |
|---|---|
| FormFieldSpec 配列 | ~100 tokens/field × 50 = 5,000 tokens |
| DataSources KV | ~500 tokens |
| Rule snippets（ルールドキュメント断片） | ~300 tokens/snippet × 5 = 1,500 tokens |
| User rules（手入力ルール） | ~100 tokens |
| Mapping candidates | ~50 tokens/field × 20 ambiguous = 1,000 tokens |

### 5.4 ルールドキュメントの取り込み設計：RuleAnalyzer

#### 前提と設計判断

ルールドキュメント（記入要領、法令ガイドライン、社内マニュアル等）は数十〜数百ページの自然言語テキストである。ここで扱うルールは**LLM の判断が必要な記述**（「該当する場合に記入」「特別の事情がある場合」等）であり、決定論で処理できるものではない。

さらに、**ドキュメントの種類は不定（ボラタイル）**である。ユーザーがリクエスト毎に異なるルールドキュメントを添付する可能性があるため、事前に固定のインデックスを構築する方式は適合しない。

ただし、**同じドキュメントが繰り返し使われるケースは多い**（例: 同じ記入要領で複数の申告書を処理する）。このため、初回の LLM 解析結果を**永続化**し、2回目以降は DB 参照で LLM をスキップする。

#### 設計方針

```
RuleAnalyzer の責務:
  1. 初回: ルールドキュメントを LLM で読解 → RuleSnippet[] を生成・DB に永続化
  2. 2回目以降: doc_hash で DB を検索 → HIT なら LLM スキップ、DB から取得
  3. FormContextBuilder と並行実行し、両者の出力を merge して FormContext を構築

→ 事前登録ステップは不要。初回利用時に自然に蓄積される。
```

#### RuleAnalyzer の処理フロー

```
入力: ルールドキュメント（PDF/HTML等）+ フィールド一覧（FormContextBuilder から共有 or 初期解析済み）
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 0: DB 検索（doc_hash + field_list_hash）│
│  ├─ HIT  → Step 3 へ直行（LLM スキップ）     │
│  └─ MISS → Step 1 へ進む                     │
└──────────────────────────────────────────────┘
                │ (MISS)
                ▼
┌──────────────────────────────────────────────┐
│  Step 1: ドキュメント → チャンク分割（非LLM） │
│  テキスト抽出 → 見出し/目次構造を解析         │
│  → 段落〜小セクション単位のチャンクに分割     │
│  ※ここは決定論。PyMuPDF / BeautifulSoup 等   │
└──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 2: LLM によるチャンク⇔フィールド紐付   │
│                                              │
│  プロンプト:                                  │
│    「以下のフォームフィールド一覧と             │
│     ルールテキストのチャンクを見て、           │
│     各チャンクがどのフィールドの記入判断に     │
│     関連するかを判定せよ。                     │
│     関連しないチャンクは除外せよ。」           │
│                                              │
│  ※ドキュメントが長い場合はバッチ分割          │
│  （チャンク群を N 個ずつ LLM に渡す）         │
└──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 2.5: DB に永続化                        │
│  doc_hash + field_list_hash をキーに          │
│  RuleSnippet[] を保存                         │
│  → 同一ドキュメントの次回処理時に再利用       │
└──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 3: RuleSnippet[] を返却                 │
│  { source_doc, section, text,                │
│    field_ids[], relevance_reason }            │
│  → FormContext に merge                       │
└──────────────────────────────────────────────┘
```

#### 実行タイミングとライフサイクル

| タイミング | 内容 |
|---|---|
| **フォーム処理リクエスト受信時** | FormContextBuilder の起動と**同時に** RuleAnalyzer を起動 |
| **RuleAnalyzer 内部（初回）** | `doc_hash` で DB 検索 → MISS → LLM 解析 → **DB に永続化** → `RuleSnippet[]` 返却 |
| **RuleAnalyzer 内部（2回目以降）** | `doc_hash` で DB 検索 → **HIT → LLM スキップ** → DB から `RuleSnippet[]` 取得・返却 |
| **FormContextBuilder 完了前** | RuleAnalyzer の完了を await。両者の結果を merge して FormContext を構築 |
| **ルールDoc が添付されていない場合** | RuleAnalyzer はスキップ。`FormContext.rule_snippets = []` |

#### 並行実行の実装パターン

```python
import asyncio
import hashlib

class RuleAnalyzer:
    async def analyze(
        self, rule_docs: list[bytes], field_hints: list[str]
    ) -> list[RuleSnippet]:
        doc_hash = self._compute_hash(rule_docs)
        field_hash = self._compute_hash(field_hints)

        # Step 0: DB 検索 — 2回目以降はここで返る
        cached = await self.snippet_repo.find_by_hash(doc_hash, field_hash)
        if cached:
            return cached

        # Step 1: チャンク分割（非LLM）
        chunks = self.chunker.split(rule_docs)

        # Step 2: LLM によるフィールド紐付
        snippets = await self.llm_linker.link(chunks, field_hints)

        # Step 2.5: DB に永続化
        await self.snippet_repo.save(doc_hash, field_hash, snippets)

        return snippets

async def build_form_context_with_rules(
    pdf: bytes,
    data_sources: list[DataSource],
    rule_docs: list[bytes] | None,
    field_hints: list[str],
) -> FormContext:
    context_task = asyncio.create_task(
        form_context_builder.build(pdf, data_sources)
    )

    if rule_docs:
        # RuleAnalyzer 内部で DB HIT なら LLM スキップ
        rule_task = asyncio.create_task(
            rule_analyzer.analyze(rule_docs, field_hints)
        )
        partial_context, rule_snippets = await asyncio.gather(
            context_task, rule_task
        )
    else:
        partial_context = await context_task
        rule_snippets = []

    partial_context.rule_snippets = rule_snippets
    return partial_context
```

#### トークン予算とバッチ戦略

ルールドキュメントが長大な場合、1回の LLM 呼び出しに収まらない。以下の戦略で対応する。

| 戦略 | 内容 |
|---|---|
| **チャンク単位のバッチ** | チャンクを N 個（例: 20個、各 ~300 tokens）ずつ LLM に渡す。並列に複数バッチを実行可能 |
| **事前フィルタリング（非LLM）** | チャンクの見出し/キーワードでフィールドラベルと簡易照合し、明らかに無関係なチャンクを除外してから LLM に渡す |
| **トークン上限制御** | 最終的に FormContext に含める `rule_snippets` の合計トークン数に上限を設定（例: 2000 tokens）。confidence/relevance スコアで優先度付き truncation |

#### 何が難しいか

| 課題 | 詳細 |
|---|---|
| **初回レイテンシ** | 初回は LLM 呼び出しのため FormContextBuilder より遅くなる可能性がある。2回目以降は DB 参照のみ（~数ms） |
| **ドキュメントの多様性** | PDF の構造（見出しの有無、表形式、スキャン画像）が不均一。チャンク分割の品質がドキュメント依存 |
| **紐付の精度** | フィールド名が「控除額」のように曖昧な場合、どのチャンクが対応するか LLM も誤る可能性がある |
| **永続化の鮮度管理** | ドキュメントが微修正された場合、hash が変わり再解析が走る。大規模修正時のコスト増を許容するか、差分更新を実装するか |
| **長大ドキュメント** | 数百ページのドキュメントはバッチ分割が必須。バッチ間の文脈断絶で紐付精度が落ちるリスク |

#### コスト/レイテンシ最適化

DB 永続化が最大の最適化であり、同一ドキュメントの再利用時は LLM コスト = 0 になる。追加の最適化:

| 最適化 | 効果 | トレードオフ |
|---|---|---|
| **DB 永続化（コア設計）** | 2回目以降は LLM コスト 0、レイテンシ ~数ms | DB ストレージコスト（軽微）。hash 管理が必要 |
| **事前フィルタリング（非LLM）** | 初回の LLM に渡すチャンク数を 30-50% 削減 | フィルタリング精度が低いと必要なチャンクを落とす |
| **軽量モデル使用** | 初回の RuleAnalyzer には GPT-4o-mini 等のコスト効率良いモデルを使用 | 精度が落ちる可能性。FillPlanner とモデルを分ける複雑性 |
| **バッチ並列実行** | 初回レイテンシ削減（N バッチを並列に LLM 呼び出し） | API rate limit に注意。コストは変わらない |

#### RuleSnippet のデータモデル

```python
class RuleSnippet(BaseModel):
    snippet_id: str           # UUID（DB 永続化用）
    doc_hash: str             # ドキュメントのコンテンツハッシュ
    field_list_hash: str      # 紐付対象フィールド一覧のハッシュ
    source_doc: str           # "記入要領2025.pdf"
    section: str              # "第3章 所得控除 > 3.2 医療費控除"
    text: str                 # セクションの自然言語テキスト（~300 tokens 以内）
    field_ids: list[str]      # このスニペットが関連するフィールド群
    relevance_reason: str     # LLM が判定した関連理由（"医療費控除の記入条件を定義"）
    analyzed_at: datetime     # 解析日時
```

#### DB 永続化テーブル

```sql
CREATE TABLE rule_snippets (
    snippet_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_hash        TEXT NOT NULL,            -- ドキュメントコンテンツの SHA-256
    field_list_hash TEXT NOT NULL,            -- フィールド一覧の SHA-256
    source_doc      TEXT NOT NULL,            -- ファイル名
    section         TEXT NOT NULL,            -- セクション見出し
    text            TEXT NOT NULL,            -- スニペット本文
    field_ids       TEXT[] NOT NULL,          -- 関連フィールドID配列
    relevance_reason TEXT NOT NULL,           -- LLM が判定した関連理由
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2回目以降の高速検索用
CREATE UNIQUE INDEX idx_rule_snippets_hash
    ON rule_snippets(doc_hash, field_list_hash, section);
CREATE INDEX idx_rule_snippets_doc_hash
    ON rule_snippets(doc_hash);
```

#### 永続化の振る舞い

| シナリオ | 動作 | LLM 呼び出し |
|---|---|---|
| **同一ドキュメント + 同一フィールド一覧** | DB から即座に返却 | 0回 |
| **同一ドキュメント + フィールド一覧が異なる** | 再解析（フィールドとの紐付が変わるため） | 1回 |
| **ドキュメントが微修正された（hash 変更）** | 再解析 + 新規永続化 | 1回 |
| **ドキュメント未添付** | RuleAnalyzer スキップ | 0回 |

> **注**: `doc_hash` はドキュメントのバイナリコンテンツから SHA-256 で生成。ファイル名変更のみでは hash は変わらない。

#### LLM に渡す必要がある理由（FillPlanner 側）

RuleAnalyzer が抽出・永続化した `RuleSnippet[]` のテキスト自体は FillPlanner に渡す必要がある。理由:

1. **fill/skip の判断にルール文面が必要**: 「該当する場合に記入」という記述に対し、ユーザーのデータが「該当する」かどうかは FillPlanner の LLM が判断する
2. **紐付だけでは判断できない**: 「field_42 には所得控除のルールが関連する」という情報だけでは、FillPlanner は何を根拠に判断すべきかわからない
3. **rule_trace の生成**: `FieldFillAction.rule_trace` に「どのルール文面を根拠としたか」を記録するには、LLM がルール文面を見ている必要がある

RuleAnalyzer の価値は「LLM にルールを渡さなくて済むようにする」ではなく、**「数百ページの中から FillPlanner に渡すべき数段落を絞り込み、永続化して再利用する」**こと。

---

### 5.5 ルールドキュメントのセマンティック検索設計

#### 課題

ルールドキュメントには**テキストだけでなく図表・フローチャート・スキャン画像**が含まれる場合がある。テキストベースのチャンク分割（5.4 Step 1）だけでは、画像内の情報を取りこぼす。フィールドとルールの紐付にはセマンティック（意味的）な検索が必要。

#### 既存資産

本リポジトリには以下のインフラが**既に存在**する:

| コンポーネント | ファイル | 状態 |
|---|---|---|
| `EmbeddingGateway` (Protocol) | `app/application/ports/embedding_gateway.py` | 定義済 |
| `OpenAIEmbeddingGateway` | `app/infrastructure/gateways/embedding.py` | 実装済（`text-embedding-3-small`） |
| `embed_image` / `embed_text` / `embed_document_page` | 同上 | インタフェース済（画像は未本格実装） |
| `VectorDBGateway` (Protocol) | `app/application/ports/vector_db_gateway.py` | 定義済 |
| `InMemoryVectorDB` | `app/infrastructure/gateways/vector_db.py` | テスト用実装済 |
| Supabase (PostgreSQL) | `app/infrastructure/supabase/` | 本番稼働中 |

→ **pgvector + 既存 Gateway の拡張**が最も低コストで導入可能。

#### 方式比較

| # | 方式 | 概要 | 画像対応 | 精度 | インフラ追加 | コスト/リクエスト | 永続化との相性 |
|---|---|---|---|---|---|---|---|
| **A** | **テキスト Embedding + pgvector** | チャンクをテキスト埋め込み → pgvector で類似検索 | ✗ テキストのみ | 中 | **なし**（既存 Gateway + Supabase pgvector） | Embedding API のみ（安価） | ◎ ベクトルも DB に永続化 |
| **B** | **Vision LLM でページ単位読解** | ページ画像を GPT-4o 等に直接渡して要約/紐付 | ◎ 画像も理解 | 高 | なし（既存 LLM クライアント） | 高い（Vision API 単価） | ○ 結果を永続化すればOK |
| **C** | **マルチモーダル Embedding + pgvector** | ページ画像を CLIP/Cohere multimodal 等で埋め込み → pgvector で類似検索 | △ レイアウト理解は弱い | 中〜低 | Embedding モデル変更 | Embedding API のみ | ◎ ベクトルも DB に永続化 |
| **D** | **ColPali / ColQwen（Late Interaction）** | ドキュメント画像を OCR なしで直接エンコード → retrieval | ◎ ドキュメント特化 | 高 | 専用モデルのホスティング or API | 推論コスト中 | ○ インデックスを永続化 |
| **E** | **ハイブリッド: A + B（推奨）** | テキスト Embedding で粗い検索（Stage 1）→ Vision LLM で精査（Stage 2） | ◎ | 高 | **なし** | Stage 1 安価 + Stage 2 は絞り込み後のみ | ◎ 両段階とも永続化可能 |

#### 各方式の詳細

**方式 A: テキスト Embedding + pgvector**

```
チャンク(テキスト) → OpenAI text-embedding-3-small → vector(1536dim)
                                                        ↓
フィールドラベル → OpenAI text-embedding-3-small → vector(1536dim)
                                                        ↓
                            pgvector: cosine similarity → Top-K チャンク
```

- **利点**: 既存の `EmbeddingGateway` + `VectorDBGateway` をそのまま使える。Supabase は pgvector をネイティブサポート
- **欠点**: 画像内の情報（図表、フローチャート）を完全に無視する
- **適用**: テキスト主体のルールドキュメントであれば十分

**方式 B: Vision LLM ページ単位読解**

```
ページ画像 → GPT-4o (Vision) → 「このページのルール要約 + 関連フィールド判定」
                                  ↓
                            RuleSnippet[] → DB 永続化
```

- **利点**: 画像・図表・複雑なレイアウトも完全に理解。最も精度が高い
- **欠点**: ページ数 × Vision API 単価。100ページのドキュメントだと初回コストが高い
- **適用**: 画像が多いドキュメント、精度最優先の場合

**方式 D: ColPali / ColQwen**

```
ドキュメントページ画像 → ColPali encoder → patch embeddings
                                              ↓
クエリ(フィールドラベル) → ColPali encoder → query embeddings
                                              ↓
                         Late Interaction score → Top-K ページ
```

- **利点**: OCR 不要でドキュメント画像から直接 retrieval。学術的に最高精度
- **欠点**: モデルのホスティングが必要（HuggingFace / vLLM 等）。pgvector では使えない（Late Interaction のため専用インデックスが必要）
- **適用**: ドキュメント検索が大量に発生し、専用インフラを持てる場合

**方式 E: ハイブリッド（推奨）**

```
Stage 1: 粗い検索（安価・高速）
  チャンク(テキスト+OCR) → text-embedding-3-small → pgvector
  フィールドラベル → text-embedding-3-small → pgvector
  → Top-K チャンク/ページを取得（例: 上位 20 件）

Stage 2: 精査（高精度・Vision LLM）
  Top-K ページ画像 → GPT-4o (Vision)
  → 「このページはフィールド X,Y に関連するか？」
  → RuleSnippet[] 生成 → DB 永続化
```

- **利点**:
  - Stage 1 で大半のページを除外（100ページ → 20ページ）→ Vision API コストを 80% 削減
  - Stage 2 で画像・図表も理解 → 精度を保証
  - 既存インフラ（pgvector + OpenAI）だけで実現可能
  - **永続化と完全に両立**: Stage 1 のベクトルも Stage 2 の結果も DB に保存
- **欠点**: 2段階のため実装が少し複雑

#### 推奨: 方式 E（ハイブリッド）

**理由**:

1. **既存インフラ活用**: `EmbeddingGateway`（OpenAI text-embedding-3-small）と `VectorDBGateway`（pgvector 対応予定）が既にある。新規インフラ不要
2. **画像対応**: Stage 2 の Vision LLM でドキュメント内の図表・フローチャートも理解できる
3. **コスト制御**: Stage 1 のテキスト Embedding で大幅にフィルタリングし、高コストの Vision LLM は絞り込み後のページにのみ適用
4. **永続化との相性**: 初回のベクトル + RuleSnippet を DB に永続化。2回目以降は LLM/Embedding ともにスキップ
5. **段階的導入**: Stage 1 だけで MVP を構築し、画像対応が必要になったら Stage 2 を追加できる

#### pgvector の設計（Stage 1）

```sql
-- Supabase で pgvector を有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- ルールチャンクの Embedding テーブル
CREATE TABLE rule_chunk_embeddings (
    chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_hash        TEXT NOT NULL,
    chunk_index     INT NOT NULL,
    section         TEXT NOT NULL,
    text            TEXT NOT NULL,
    page_number     INT,
    embedding       vector(1536) NOT NULL,   -- text-embedding-3-small
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW インデックス（検索高速化）
CREATE INDEX idx_rule_chunk_embedding_hnsw
    ON rule_chunk_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_rule_chunk_doc_hash
    ON rule_chunk_embeddings(doc_hash);
```

#### RuleAnalyzer 処理フロー（方式 E 適用後）

```
入力: ルールドキュメント + フィールド一覧
                │
                ▼
┌──────────────────────────────────────────────────┐
│  Step 0: DB 検索（doc_hash + field_list_hash）    │
│  ├─ RuleSnippet HIT → 直行返却                   │
│  └─ MISS → Step 1 へ                             │
└──────────────────────────────────────────────────┘
                │ (MISS)
                ▼
┌──────────────────────────────────────────────────┐
│  Step 1: チャンク分割 + Embedding（非LLM部分）    │
│  テキスト抽出 + OCR（画像ページ）                 │
│  → チャンク分割                                   │
│  → 各チャンクを text-embedding-3-small で埋め込み │
│  → pgvector に保存（doc_hash でグループ化）       │
└──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────┐
│  Stage 1: セマンティック検索（Embedding + pgvector）│
│  フィールドラベルを Embed → pgvector で Top-K 取得 │
│  → 候補チャンク/ページを 100→20 に絞り込み       │
└──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────┐
│  Stage 2: Vision LLM で精査                       │
│  Top-K ページの画像を GPT-4o に渡す               │
│  → 「このページはどのフィールドに関連するか？」   │
│  → RuleSnippet[] 生成                             │
│  ※テキストのみのチャンクは Stage 1 の結果で十分な │
│   場合、Stage 2 をスキップ可能（コスト最適化）    │
└──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────┐
│  Step 2.5: DB に永続化                            │
│  RuleSnippet[] + Embedding ベクトルを保存         │
│  → 同一ドキュメントの次回処理時に全段階スキップ   │
└──────────────────────────────────────────────────┘
```

#### 段階的導入の提案

| フェーズ | 内容 | 画像対応 |
|---|---|---|
| **MVP** | テキスト Embedding + pgvector のみ（方式 A）。画像ページは OCR でテキスト化 | △（OCR 依存） |
| **v1** | Stage 1（pgvector）+ Stage 2（Vision LLM）のハイブリッド（方式 E） | ◎ |
| **v2（将来）** | ColPali/ColQwen での高速 retrieval を Stage 1 に導入（方式 D + B） | ◎（OCR不要） |

> **ColPali/ColQwen について**: 現時点では専用インフラのホスティングコストとメンテナンス負荷が高い。ドキュメント検索のリクエスト量が増え、pgvector + Vision LLM のコスト/レイテンシが問題になった段階で検討する。Hugging Face Inference Endpoints 等の SaaS を使えば導入障壁は下がる。

---

## 6. 実装計画

> 前提：Phase 1 → Phase 2 の順で進める。Phase 3 以降は Phase 2 の結果を見て随時判断する。

### Phase 1: インターフェース定義（Protocol / データモデルのみ）

**目的**: To-Be アーキテクチャの全サービス境界とデータ構造を Protocol + Pydantic モデルとして定義する。**実装は一切含まない**。

#### 成果物

| ファイル | 内容 |
|---|---|
| `app/domain/protocols/form_context_builder.py` (新規) | `FormContextBuilderProtocol` — `build()` のシグネチャのみ |
| `app/domain/protocols/fill_planner.py` (新規) | `FillPlannerProtocol` — `plan(FormContext) → FillPlan` のシグネチャのみ |
| `app/domain/protocols/form_renderer.py` (新規) | `FormRendererProtocol` — `render(FillPlan, pdf) → RenderReport` のシグネチャのみ |
| `app/domain/protocols/rule_analyzer.py` (新規) | `RuleAnalyzerProtocol` — `analyze(docs, fields) → list[RuleSnippet]` のシグネチャのみ |
| `app/domain/protocols/correction_tracker.py` (新規) | `CorrectionTrackerProtocol` — `record(CorrectionRecord)` のシグネチャのみ |
| `app/domain/models/form_context.py` (新規) | `FormContext`, `FormFieldSpec` Pydantic モデル |
| `app/domain/models/fill_plan.py` (新規) | `FillPlan`, `FieldFillAction` Pydantic モデル |
| `app/domain/models/render_report.py` (新規) | `RenderReport` Pydantic モデル |
| `app/domain/models/rule_snippet.py` (新規) | `RuleSnippet` Pydantic モデル |
| `app/domain/models/correction_record.py` (新規) | `CorrectionRecord` Pydantic モデル |

#### 受け入れ基準

- 全 Protocol が `typing.Protocol` + `runtime_checkable` で定義されている
- 全データモデルが Pydantic v2 BaseModel で定義され、型が明確
- **既存コードへの変更はゼロ**（新規ファイル追加のみ）
- サービス間の入出力の型が一意に決まっている

#### 方針

- 既存の `EmbeddingGateway`, `VectorDBGateway` の Protocol パターンに倣う
- 実装クラスは Phase 2 で作成する。Phase 1 では「契約」だけを固める

---

### Phase 2: Web から利用可能な最小コア実装

**目的**: Phase 1 の Protocol に対する最小実装を行い、Web UI からエンドツーエンドで動作する状態にする。

#### スコープ

**やること（最小コア）:**

| コンポーネント | 実装範囲 |
|---|---|
| **FormContextBuilder** | 既存 VisionAutofillService の `_extract_from_sources` + `_rule_based_autofill` を wrap し、`FormContext` を出力する最小実装 |
| **FillPlanner** | 既存 VisionAutofillService の `_llm_autofill` を wrap し、`FillPlan` を出力する最小実装（LLM 1回、既存プロンプトベース） |
| **FormRenderer** | 既存の `FillService` を wrap し、`FillPlan` → PDF 描画 + `RenderReport` 出力 |
| **RuleAnalyzer** | stub 実装（`rule_snippets = []` を返す）。実体は Phase 3 以降 |
| **CorrectionTracker** | stub 実装。実体は Phase 3 以降 |
| **API エンドポイント** | 新アーキテクチャ経由のエンドポイント 1本。既存エンドポイントは維持（フィーチャーフラグで切替） |
| **Web UI** | 既存 UI から新エンドポイントを呼べるように接続 |

**やらないこと（Phase 3 以降）:**

- RuleAnalyzer の LLM 実装・永続化・セマンティック検索
- CorrectionTracker の実装
- 旧パイプライン（Orchestrator 8ステージ）の統合・廃止
- 多点 LLM 呼び出しの 1回化（FieldLabelling, Mapping, Extract の統合）
- A/B テスト基盤
- Prometheus メトリクス追加

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/services/form_context/builder.py` (新規) | `FormContextBuilder` — 既存ロジックの薄い wrap |
| `app/services/fill_planner/planner.py` (新規) | `FillPlanner` — 既存 VisionAutofill LLM の薄い wrap |
| `app/services/form_renderer/renderer.py` (新規) | `FormRenderer` — 既存 FillService の薄い wrap |
| `app/services/rule_analyzer/analyzer.py` (新規) | `RuleAnalyzer` — stub（空リスト返却） |
| `app/services/correction_tracker/tracker.py` (新規) | `CorrectionTracker` — stub（no-op） |
| `app/routes/` (新規 or 既存修正) | 新アーキテクチャ経由のエンドポイント追加 |
| `apps/web/src/api/` | 新エンドポイントへの接続 |

#### 受け入れ基準

- Web UI から PDF + データソースをアップロードし、新アーキテクチャ経由で記入済み PDF が返る
- 既存 VisionAutofill と同等の精度（内部的に同じロジックを呼んでいるため）
- 既存エンドポイントは引き続き動作（回帰なし）
- 全 Protocol に対して実装クラスが存在し、DI で差し替え可能

---

### Phase 3 以降: 随時判断

Phase 2 の結果と運用状況を見て、以下から優先度を決定する。

| 候補 | 概要 | 判断材料 |
|---|---|---|
| **RuleAnalyzer 実装** | LLM 読解 + 永続化 + セマンティック検索（5.4, 5.5） | ルールDoc 対応の需要度 |
| **LLM 統合（多点→1回化）** | FieldLabelling + Mapping + Extract を FillPlanner に統合 | コスト/レイテンシの実測値 |
| **CorrectionTracker 実装** | ユーザー修正差分の収集・分類 | 修正頻度の実測値 |
| **計測基盤** | Prometheus メトリクス、A/B テスト基盤 | 運用フェーズの要求 |
| **旧パイプライン廃止** | Orchestrator 8ステージの非推奨化 | 新アーキテクチャの安定度 |

---

## 7. 追加の確認事項（不足情報リスト）

以下を Yes/No で確認できると、設計の精度が上がります。

### アーキテクチャ全般

1. パイプライン v1（Orchestrator 8 ステージ）は現在も本番で使用されているか？（VisionAutofill v2 に移行済みか？）
2. MCP Server（Claude Desktop 連携）は To-Be アーキテクチャでも維持するか？
3. Celery タスクキュー（`infrastructure/celery/`）は現在使用されているか？

### データ・ルール

4. 「ルールドキュメント」（記入要領等）の具体的な形式は？（PDF? Word? HTML?）典型的な分量はどの程度か？（10ページ程度? 100ページ超?）1リクエストあたり何ドキュメントまで添付されうるか？
5. ルールドキュメントに**図表・フローチャート・スキャン画像**はどの程度含まれるか？テキスト主体ならテキスト Embedding で十分、画像が多いなら Vision LLM（方式 E）が必要（セクション 5.5 参照）
6. ルールドキュメントの添付がないリクエスト（ルールなしで記入判断する場合）はどの程度の割合か？RuleAnalyzer スキップの頻度見積もりに必要
7. 過去申告書データはどの形式で提供されるか？（PDF? CSV? JSON? DB?）
8. フォーム間の値参照（例：確定申告書 → 住民税申告書への転記）は対応スコープに含まれるか？
9. `DataSource` のタイプとして、現在どのようなものが使用されているか？（PDF, CSV, 手入力等）

### LLM・精度

10. 現在の LLM モデルは gpt-4o-mini か gpt-5-mini か？（`config.py` に `gpt-5-mini` の記載あり）
11. VisionAutofill の 1回 LLM アプローチで、精度に不満がある具体的なケースはあるか？
12. FieldLabelling（label⇔box リンク）の精度問題は発生しているか？
13. FillPlanner の LLM 応答フォーマットとして、JSON Schema (Structured Output) を使う想定か、自由テキスト JSON か？

### 運用

14. 現在の典型的なフォームのフィールド数はいくつか？（10以下 / 10-50 / 50-100 / 100+）
15. 1 フォーム処理の許容レイテンシはどの程度か？（5秒以内 / 15秒以内 / 30秒以内）
16. CorrectionTracker で蓄積した修正差分を、自動的に FormContextBuilder のルールに反映する自動化は必要か？それとも手動レビュー前提か？
17. テスト環境で使用可能なサンプルフォーム（PDF + 正解データ）は何件あるか？

---

## 付録A: 命名対照表（クイックリファレンス）

| 旧名（抽象的） | 新名（ドメイン直結） | 種別 | 一言説明 |
|---|---|---|---|
| Compiler | **FormContextBuilder** | サービス | フォーム文脈を組み立てる |
| SemanticContextBundle | **FormContext** | データ | フォーム記入に必要な全文脈 |
| FormSpec | **FormFieldSpec** | データ | 1フィールドの構造定義 |
| Decision Engine | **FillPlanner** | サービス | 記入計画を立てる（LLM 1回） |
| SemanticPlan | **FillPlan** | データ | 全フィールドの記入計画 |
| FieldDecision | **FieldFillAction** | データ | 1フィールドの記入判断 |
| Executor | **FormRenderer** | サービス | 計画に従い PDF を描画する |
| render_report | **RenderReport** | データ | 描画結果+検証結果 |
| Learning Adapter | **CorrectionTracker** | サービス | ユーザー修正を追跡・分類する |
| （なし） | **CorrectionRecord** | データ | 1件の修正差分レコード |
| （新規） | **RuleAnalyzer** | サービス | ルールDoc を LLM で読解・永続化。2回目以降は DB 参照でスキップ（FormContextBuilder と並行実行） |
| （新規） | **RuleSnippet** | データ（DB永続化） | ルールDoc から LLM が抽出・永続化した1断片（セクション+テキスト+関連フィールド+関連理由） |

## 付録B: 実装方針

**Phase 1（インターフェース定義）→ Phase 2（最小コア実装）→ Phase 3 以降（随時判断）** の 3段階で進める。

- **Phase 1** は既存コードへの変更ゼロ（新規ファイル追加のみ）のため、リスクが最も低い
- **Phase 2** は既存 VisionAutofillService を薄く wrap する戦略のため、内部ロジックの変更は最小限。Web UI からエンドツーエンドで動作することがゴール
- **Phase 3 以降** は Phase 2 の運用結果を見て優先度を決定する。事前に全てを計画しない
