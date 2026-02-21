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
| S1 | Compiler | **FormContextBuilder** | フォーム構造+データソース+候補+ルールスニペットを収集・正規化し、`FormContext` を組み立てる | 非LLM |
| S2 | Decision Engine | **FillPlanner** | `FormContext` を受け取り、LLM 1回の推論で各フィールドの fill/skip/ask_user を計画する | **LLM 1回** |
| S3 | Executor | **FormRenderer** | `FillPlan` に従って PDF に値を描画し、検証結果付きの完成 PDF を出力する | 非LLM |
| S4 | Learning Adapter | **CorrectionTracker** | ユーザーの修正差分を収集・分類し、FormContextBuilder/FillPlanner の改善に資産化する | 非LLM（非同期） |
| S5 | （新規） | **RuleIndexer** | ルールドキュメントを事前に取り込み、フィールド⇔スニペットの対応を永続化する。FormContextBuilder が実行時に参照する | 非LLM（オフライン）or LLM（事前1回） |

### データ構造命名

| 旧名（抽象的） | 新名 | 生成元 → 消費先 | 内容 |
|---|---|---|---|
| SemanticContextBundle | **FormContext** | FormContextBuilder → FillPlanner | フォーム定義 + 候補 + 制約 + データ + ルール + 出典 |
| FormSpec | **FormFieldSpec** | FormContextBuilder 内部 | 個別フィールドの構造定義（bbox, type, label 候補 top-k, required） |
| SemanticPlan | **FillPlan** | FillPlanner → FormRenderer | 各フィールドの記入判断（action, value, confidence, rule_trace） |
| FieldDecision | **FieldFillAction** | FillPlan の要素 | 1 フィールドの判断結果（fill/skip/ask_user + 値 + 根拠） |
| render_report | **RenderReport** | FormRenderer → API/UI | 描画結果（成功/失敗/警告）+ validation_result |
| （なし） | **CorrectionRecord** | CorrectionTracker → DB | 修正差分（before/after + 分類 + FillPlan スナップショット） |
| （なし） | **RuleSnippet** | RuleIndexer → DB → FormContextBuilder → FillPlanner | ルールドキュメントから抽出した断片（セクション名+テキスト+関連フィールド） |

### To-Be データフロー

```
  オフライン（事前）                オンライン（フォーム処理時）
┌─────────────────────┐
│    RuleIndexer       │
│                      │
│ ルールDoc取込        │    非LLM                    LLM 1回                   非LLM
│ → セクション分割     │  ┌──────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
│ → フィールド紐付     │  │ FormContextBuilder   │  │    FillPlanner      │  │   FormRenderer       │
│ → RuleSnippet永続化  │  │                      │  │                     │  │                      │
│                      │  │ PDF構造検出          │  │ FormContext →       │  │ FillPlan →           │
│ ※フォーム種別登録時  │──▶│ データソース抽出      │──▶│ LLM 1回呼び出し →  │──▶│ PDF描画（AcroForm/   │
│   に1回実行          │  │ 候補生成(fuzzy/prox) │  │ FillPlan生成        │  │   Overlay）          │
│                      │  │ 正規化（決定論）     │  │                     │  │ 検証(required/format/│
└─────────────────────┘  │ DB→関連スニペット取得 │  │ fill / skip /       │  │   overflow/overlap)  │
                         │                      │  │ ask_user を判定     │  │ RenderReport 出力    │
                         │ → FormContext 出力    │  │                     │  │ → 完成PDF + 検証結果 │
                         └──────────────────────┘  └─────────────────────┘  └──────────────────────┘
                                                                                     │
                                                                          ┌──────────▼───────────┐
                                                                          │  CorrectionTracker    │
                                                                          │  （非同期・オプション）│
                                                                          └──────────────────────┘
```

**要点**: RuleIndexer はオフラインで事前にルールドキュメントを処理し、`RuleSnippet` を DB に永続化する。FormContextBuilder は実行時に DB から関連スニペットを引くだけ（検索コスト ≈ 0）。引いたスニペットは `FormContext.rule_snippets` として FillPlanner（LLM）に渡す。LLM はこのスニペットを読んで fill/skip の判断根拠とする。

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

3. **ルールドキュメントの取り込みパイプライン**
   - 現状：`VisionAutofillRequest.rules` は `list[str]`（ユーザーが手入力した短文）、MappingService の `UserRule` はパターンマッチのみ
   - 課題：実際の記入要領・法令ガイドライン等は数十〜数百ページの自然言語ドキュメントである。これを丸ごと LLM に渡すとトークン超過になるが、どのセクションがどのフィールドに関連するかの切り出し（チャンキング＋検索）の仕組みが存在しない
   - 必要：ルールドキュメントを事前に取り込み、フィールド/フォームに関連する箇所だけを `FormContext` に載せるための検索・抽出パイプライン（後述: セクション 5.4）

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
2. **ルールドキュメント**: 元ドキュメントの形式（PDF? Word? HTML?）、分量（ページ数）、更新頻度、1フォームあたり参照すべきドキュメント数が未確定
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
  ├── rule_snippets: [{                # ルールドキュメントから検索・抽出した断片
  │     snippet_id,
  │     source_doc: "記入要領2025.pdf",
  │     section: "第3章 所得控除",
  │     text: "...該当する自然言語テキスト...",
  │     relevant_field_ids: [field_3, field_7],
  │     relevance_score
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

- FormContextBuilder がルールドキュメントインデックスから関連スニペットを検索し、`rule_snippets` として `FormContext` に載せる（詳細はセクション 5.4）
- 1回の FillPlanner 呼び出しに載せるスニペット数を上限付きで制御（例: 最大 5 スニペット、合計 1,500 tokens 以内）
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

### 5.4 ルールドキュメントの取り込み設計：RuleIndexer

#### 前提と設計判断

ルールドキュメント（記入要領、法令ガイドライン等）は数十〜数百ページの自然言語テキストである。ここで扱うルールは**LLM の判断が必要な記述**（「該当する場合に記入」「特別の事情がある場合」等）であり、決定論で処理できるものではない。

したがって、**関連するルールテキストは FillPlanner（LLM）に渡す必要がある**。問題は「どうやって関連箇所を特定し、トークン予算内に収めるか」であり、これを**オフラインの事前処理で解決する**のが RuleIndexer の役割。

#### 設計方針

```
RuleIndexer の責務 = 「何を LLM に渡すべきか」を事前に決めて永続化する

実行時の FormContextBuilder は DB から引くだけ → 検索コスト ≈ 0、LLM 呼び出し = 0
```

#### RuleIndexer の処理フロー

```
入力: ルールドキュメント（PDF/HTML等）+ フォーム定義（フィールド一覧）
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 1: ドキュメント → セクション分割        │
│  テキスト抽出 → 見出し/目次構造を解析         │
│  → 段落〜小セクション単位のチャンクに分割     │
└──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 2: チャンク ⇔ フィールド紐付            │
│  各チャンクが、どのフィールドの記入判断に      │
│  関連するかを特定する                         │
│                                              │
│  方式は段階的に進化させる（後述）              │
└──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────┐
│  Step 3: RuleSnippet として DB に永続化        │
│  { snippet_id, source_doc, section,           │
│    text, field_ids[], form_type_id }          │
└──────────────────────────────────────────────┘
```

#### 実行タイミング

| タイミング | 内容 |
|---|---|
| **フォーム種別の初回登録時** | フォーム定義 + ルールドキュメントを入力して RuleIndexer を実行 |
| **ルールドキュメント更新時** | 差分または全体を再インデックス |
| **ユーザーのフォーム記入時（オンライン）** | RuleIndexer は動かない。FormContextBuilder が DB から `field_id` で関連スニペットを引くだけ |

#### Step 2（チャンク⇔フィールド紐付）の方式選択肢

紐付の精度がシステム全体の判断品質に直結するため、ここが最大の難所。

**方式 A: キーワード + セクション構造ベース（非LLM）**

```
チャンクの見出し/本文のキーワード ↔ フィールドラベルを照合
例: 見出し「医療費控除」→ フィールド「医療費控除額」「医療費の明細」に紐付
```

- 実装コスト: 低
- 精度: フィールド名とルールの見出しが近い場合は十分。乖離があると漏れる
- LLM: 不要

**方式 B: Embedding 類似度（非LLM）**

```
チャンク Embedding ↔ フィールドラベル Embedding のコサイン類似度で紐付
```

- 実装コスト: 中（Embedding インフラが必要）
- 精度: 表記揺れには強いが、意味的な関連（「扶養控除」と「16歳以上の親族」）は捉えにくい
- LLM: 不要（Embedding API は使用）

**方式 C: LLM による事前マッピング（オフライン LLM）**

```
フォームの全フィールド一覧 + ルールドキュメント全文
  → LLM に「各チャンクがどのフィールドに関連するか」を判定させる
  → 結果を DB に保存
```

- 実装コスト: 低（プロンプトを書くだけ）
- 精度: 最も高い。LLM がルールの意味を理解して紐付できる
- LLM: オフラインで 1回（or ドキュメントが長い場合はチャンク単位で数回）
- リアルタイム処理への影響: なし（事前に済んでいるため）

#### 何が難しいか

| 課題 | 詳細 |
|---|---|
| **紐付の精度** | フィールド名が「控除額」のように曖昧な場合、どのルールセクションが対応するか特定しにくい |
| **粒度の選択** | 章単位では粗すぎ、文単位では文脈が失われる。段落〜小セクション単位が妥当だが、ドキュメントの構造が不均一 |
| **トークン予算** | 1フィールドに関連するルールが複数ある場合、全てを載せると肥大する |
| **更新追従** | 法改正等でドキュメントが更新された場合、再インデックスが必要 |

#### 現時点での推奨

**方式 C（LLM による事前マッピング）を推奨する。**

理由:
- オフライン処理のため、LLM 呼び出しコストがリアルタイムの UX に影響しない
- 紐付精度が最も高く、方式 A/B で発生する「漏れ」のリスクを回避できる
- 実装コストが低い（プロンプト+DB保存のみで、Embedding インフラ不要）
- フォーム種別数は限定的（数十種類程度）と想定されるため、事前処理の総コストは小さい

方式 A はフォールバック/補助として併用可能（LLM 事前マッピングが未実行のフォームに対して）。

#### RuleSnippet のデータモデル

```python
class RuleSnippet(BaseModel):
    snippet_id: str
    form_type_id: str         # フォーム種別（確定申告書A、住民税申告書等）
    source_doc: str           # "記入要領2025.pdf"
    section: str              # "第3章 所得控除 > 3.2 医療費控除"
    text: str                 # セクションの自然言語テキスト（~300 tokens 以内）
    field_ids: list[str]      # このスニペットが関連するフィールド群
    indexed_at: datetime      # インデックス作成日時（更新追従用）
    indexer_method: str       # "llm_mapping" | "keyword" | "embedding"
```

#### DB テーブル（参考）

```sql
CREATE TABLE rule_snippets (
    snippet_id     UUID PRIMARY KEY,
    form_type_id   TEXT NOT NULL,
    source_doc     TEXT NOT NULL,
    section        TEXT NOT NULL,
    text           TEXT NOT NULL,
    field_ids      TEXT[] NOT NULL,       -- 関連フィールドID配列
    indexer_method TEXT NOT NULL DEFAULT 'llm_mapping',
    indexed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rule_snippets_form_type ON rule_snippets(form_type_id);
CREATE INDEX idx_rule_snippets_field_ids ON rule_snippets USING GIN(field_ids);
```

#### FormContextBuilder での利用

```python
# FormContextBuilder.build() 内
snippets = rule_snippet_repo.find_by_form_type_and_fields(
    form_type_id=form_type_id,
    field_ids=[f.field_id for f in form_fields],
    max_snippets=10,
    max_total_tokens=1500,
)
form_context.rule_snippets = snippets
# → FillPlanner に渡す FormContext に含まれ、LLM がルールを読んで判断する
```

#### LLM に渡す必要がある理由

RuleIndexer で事前に紐付を永続化しても、**スニペットのテキスト自体は FillPlanner に渡す必要がある**。理由:

1. **fill/skip の判断にルール文面が必要**: 「該当する場合に記入」という記述に対し、ユーザーのデータが「該当する」かどうかは LLM が判断する
2. **紐付だけでは判断できない**: 「field_42 には所得控除のルールが関連する」という情報だけでは、LLM は何を根拠に判断すべきかわからない
3. **rule_trace の生成**: FillPlan の `FieldFillAction.rule_trace` に「どのルール文面を根拠としたか」を記録するには、LLM がルール文面を見ている必要がある

RuleIndexer の価値は「渡さなくて済むようにする」ではなく、**「数百ページの中から渡すべき数段落を事前に絞り込んでおく」**こと。

---

## 6. 移行計画（段階的リファクタリング）

> 前提：各 Phase で「動く状態」を維持する。フィーチャーフラグを活用し、旧パスへのロールバックを常に可能にする。

### Phase 0: 計測の追加（1〜2週間）

**目的**: 現行システムの実態を定量把握する

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/agents/llm_wrapper.py` | 既存の `CostTracker` にレイテンシ計測を追加 |
| `app/infrastructure/observability/` | Prometheus メトリクスに LLM 呼び出し回数/モデル/エージェント別のヒストグラム追加 |
| `app/orchestrator/orchestrator.py` | ステージ所要時間の計測 |

#### 収集する指標

- LLM 呼び出し回数（エージェント別、フォーム別）
- LLM レイテンシ（P50, P95, P99）
- トークン数（input/output、エージェント別）
- コスト（モデル × トークン）
- エラー分類（timeout, rate_limit, parse_error, validation_error）

#### 受け入れ基準

- Prometheus/Grafana でダッシュボード閲覧可能
- 10回以上の実フォーム処理でベースライン数値を収集

#### リスクと対策

低リスク。`CostTracker` が既にあるため追加実装は軽微。

---

### Phase 1: FormContextBuilder の導入（2〜3週間）

**目的**: 既存の決定論ロジックを `FormContextBuilder` に集約し、`FormContext` を生成する

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/services/form_context/` (新規) | `FormContextBuilder` クラス、`FormContext` / `FormFieldSpec` モデル定義 |
| `app/services/structure_labelling/service.py` | proximity fallback ロジックを FormContextBuilder に移動（共通ユーティリティ化） |
| `app/services/mapping/service.py` | `_find_candidates`, `_apply_user_rules`, `_apply_template_history` を FormContextBuilder に委譲 |
| `app/services/extract/service.py` | `_try_native_extraction`, `_try_ocr_extraction` を FormContextBuilder に委譲 |
| `app/services/vision_autofill/service.py` | `_extract_from_sources`, `_rule_based_autofill` を FormContextBuilder に委譲 |
| `app/agents/extract/value_extraction_agent.py` | 決定論正規化（日付/電話/郵便番号/全角半角）を FormContextBuilder のユーティリティに抽出 |

#### 実装ステップ

1. `FormContext` / `FormFieldSpec` Pydantic モデル定義
2. `FormContextBuilder.build()` メソッド実装（既存ロジックの呼び出し集約）
3. 既存パイプラインの Ingest → Structure → (FormContextBuilder 呼び出し) → 以降のフローに差し込み
4. VisionAutofillService から FormContextBuilder を利用するように接続

#### 受け入れ基準

- 既存の全テストが Pass（回帰なし）
- FormContextBuilder の出力を JSON 出力して手動で構造を確認可能
- VisionAutofillService が FormContextBuilder 経由でデータを取得しても同等の結果

#### リスクと対策

中リスク。既存のサービス間インターフェースに触るが、既存フローは維持するためロールバック可能。FormContextBuilder はアダプターパターンで差し込み、旧パスも残す。

---

### Phase 2: FillPlan の導入（2〜3週間）

**目的**: `FillPlan` データ構造を定義し、FillPlanner のプロトタイプを VisionAutofillService ベースで構築する

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/services/fill_planner/` (新規) | `FillPlanner` クラス、`FillPlan` / `FieldFillAction` モデル定義 |
| `app/services/fill_planner/prompt_builder.py` (新規) | `FormContext` → プロンプト変換ロジック |
| `app/services/vision_autofill/service.py` | `_llm_autofill` を FillPlanner 呼び出しに置き換え |
| `app/services/vision_autofill/prompts.py` | FillPlanner 用プロンプトに拡張 |

#### 実装ステップ

1. `FillPlan` / `FieldFillAction` Pydantic モデル定義
2. `FillPlanner.plan()` 実装（FormContext → プロンプト構築 → LLM 1回 → FillPlan パース）
3. VisionAutofillService の `_llm_autofill` を FillPlanner 経由に書き換え
4. A/B テスト: 旧プロンプト vs 新 FillPlan プロンプトで精度比較

#### 受け入れ基準

- `FillPlan` 出力で fill/skip/ask_user が正しく判定される（テストマトリクス上で旧実装と同等以上）
- `rule_trace` が少なくとも 1 つのルールケースで正しく追跡される
- VisionAutofill のエンドポイントが FillPlan 経由で動作する

#### リスクと対策

中リスク。プロンプト変更は精度に直結するため、A/B テストとプロンプトチューニング期間が必要。旧 `_llm_autofill` は feature flag で残す。

---

### Phase 3: 1回 LLM への統合（3〜4週間）

**目的**: パイプライン v1 の多点 LLM 呼び出し（FieldLabelling, Mapping, Extract）を FillPlanner の 1回呼び出しに統合する

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/orchestrator/pipeline_executor.py` | ステージ構成を Build → Plan → Render に変更 |
| `app/orchestrator/decision_engine.py` | ステージ遷移ロジックを簡素化 |
| `app/services/fill_planner/planner.py` | FieldLabelling + Mapping + Extract の統合プロンプト |
| `app/agents/structure_labelling/field_labelling_agent.py` | LLM 呼び出し部分を非推奨化（FormContextBuilder の候補生成に置換） |
| `app/agents/mapping/mapping_agent.py` | LLM 呼び出し部分を非推奨化 |
| `app/agents/extract/value_extraction_agent.py` | LLM 呼び出し部分を非推奨化 |
| `app/services/fill/service.py` | `FillPlan` を入力として受け取る FormRenderer ラッパー追加 |

#### 実装ステップ

1. FillPlanner のプロンプトを拡張（label linking + mapping + value selection を統合）
2. FormRenderer ラッパー実装（FillPlan → FillRequest 変換 + 検証 + RenderReport 生成）
3. 新パイプライン（Build → Plan → Render）をフィーチャーフラグで並走
4. 旧パイプラインとの精度比較（テストマトリクス全項目）
5. 合格後に旧パイプラインを非推奨化

#### 受け入れ基準

- LLM 呼び出し回数がフォーム単位で原則 1回（ask_user 時を除く）
- 精度: 旧パイプラインと同等（fill 率 ±5% 以内、confidence 平均 ±0.05 以内）
- レイテンシ: 旧パイプラインの 50% 以下（LLM 待ち時間の大幅削減）
- コスト: 旧パイプラインの 30% 以下

#### リスクと対策

**高リスク**。これが最大の変更点。

- **ロールバック**: フィーチャーフラグで旧パイプラインに即時切り戻し可能にする
- **精度劣化リスク**: テストマトリクスで段階的に検証。まず単純なフォーム（5 フィールド以下）から、徐々に複雑なフォーム（50+ フィールド）へ
- **トークン上限リスク**: 100+ フィールドのフォームでは FormContext 圧縮でも上限超過の可能性。その場合はページ/セクション単位で分割し、2〜3回の呼び出しを許容するフォールバック設計を用意

---

### Phase 4: CorrectionTracker の分離（2週間、オプション）

**目的**: ユーザー修正差分を収集・分類し、FormContextBuilder / FillPlanner の改善に活用する基盤を構築する

#### 変更対象

| ファイル | 変更内容 |
|---|---|
| `app/services/correction_tracker/` (新規) | `CorrectionTracker` クラス、`CorrectionRecord` モデル |
| `app/repositories/correction_repository.py` (新規) | 修正差分の永続化 |
| `app/routes/edits.py` (既存) | 修正確定時に CorrectionTracker へ差分を送信 |
| `infra/supabase/migrations/` (新規) | corrections テーブル |

#### 実装ステップ

1. `CorrectionRecord` モデル定義（field_id, before_value, after_value, correction_type, fill_plan_snapshot）
2. 修正確定時のフック実装（非同期、リアルタイム必須ではない）
3. 差分の分類ロジック（LLM 判断ミス / ルール不足 / データ不足 / ユーザー好み）
4. 集計ダッシュボード（どのフィールドタイプで修正が多いか等）

#### 受け入れ基準

- ユーザー修正が corrections テーブルに保存される
- 分類結果が閲覧可能
- Phase 0 のメトリクスと合わせて改善ポイントが可視化される

#### リスクと対策

低リスク。既存フローへの影響は最小（フック追加のみ）。

---

### 移行タイムライン概要

```
Week 1-2:   Phase 0 - 計測追加
Week 3-5:   Phase 1 - FormContextBuilder 導入
Week 6-8:   Phase 2 - FillPlan / FillPlanner プロトタイプ
Week 9-12:  Phase 3 - 1回 LLM 統合 + A/B テスト + 精度チューニング
Week 13-14: Phase 4 - CorrectionTracker（オプション）
```

---

## 7. 追加の確認事項（不足情報リスト）

以下を Yes/No で確認できると、設計の精度が上がります。

### アーキテクチャ全般

1. パイプライン v1（Orchestrator 8 ステージ）は現在も本番で使用されているか？（VisionAutofill v2 に移行済みか？）
2. MCP Server（Claude Desktop 連携）は To-Be アーキテクチャでも維持するか？
3. Celery タスクキュー（`infrastructure/celery/`）は現在使用されているか？

### データ・ルール

4. 「ルールドキュメント」（記入要領等）の具体的な形式は？（PDF? Word? HTML?）分量はどの程度か？（10ページ程度? 100ページ超?）1フォームあたり何ドキュメントを参照するか？
5. ルールドキュメントはどの頻度で更新されるか？（年次改訂? 不定期?）
6. 過去申告書データはどの形式で提供されるか？（PDF? CSV? JSON? DB?）
7. フォーム間の値参照（例：確定申告書 → 住民税申告書への転記）は対応スコープに含まれるか？
8. `DataSource` のタイプとして、現在どのようなものが使用されているか？（PDF, CSV, 手入力等）

### LLM・精度

9. 現在の LLM モデルは gpt-4o-mini か gpt-5-mini か？（`config.py` に `gpt-5-mini` の記載あり）
10. VisionAutofill の 1回 LLM アプローチで、精度に不満がある具体的なケースはあるか？
11. FieldLabelling（label⇔box リンク）の精度問題は発生しているか？
12. FillPlanner の LLM 応答フォーマットとして、JSON Schema (Structured Output) を使う想定か、自由テキスト JSON か？

### 運用

13. 現在の典型的なフォームのフィールド数はいくつか？（10以下 / 10-50 / 50-100 / 100+）
14. 1 フォーム処理の許容レイテンシはどの程度か？（5秒以内 / 15秒以内 / 30秒以内）
15. CorrectionTracker で蓄積した修正差分を、自動的に FormContextBuilder のルールに反映する自動化は必要か？それとも手動レビュー前提か？
16. テスト環境で使用可能なサンプルフォーム（PDF + 正解データ）は何件あるか？

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
| （新規） | **RuleIndexer** | サービス | ルールDoc を事前処理し、フィールド⇔スニペット対応を永続化する |
| （新規） | **RuleSnippet** | データ | ルールDoc から抽出した1断片（セクション+テキスト+関連フィールド） |

## 付録B: 推奨する着手順序

**Phase 1（FormContextBuilder 導入）が最もリスクが低く効果が高い**ため、最優先で着手することを推奨する。

VisionAutofillService は既にフォーム単位 1回 LLM の原型を持っているため、これをベースに Phase 2 の FillPlanner を構築するのが自然な進化パスである。

Phase 3 の「1回 LLM 統合」は最大のリスクだが、Phase 0〜2 で収集したメトリクスとテストマトリクスにより、データドリブンな判断が可能になる。
