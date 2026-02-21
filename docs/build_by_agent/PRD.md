# PRD: Auto Document Filling Agent System（自動ドキュメント入力エージェント）

## 概要
PDF（AcroFormあり/なし）および画像ファイル（PNG、JPEG、TIFF等）を取り込み、既存書類からの転記またはゼロからの入力を支援して、新しいPDFに正確に記入する。難所は「抽出精度」と「座標ベースの配置精度」であり、**反復（ループ）＋レビュー＋人間参加**で収束させる。

画像ファイルは自動的にPDFに変換して処理する。

## 目的（Goals）
- **転記（copy/transfer）**: 旧書類→新書類へ自動転記し、不足/不確実のみ質問する
- **スクラッチ（scratch）**: 新書類のみから必要項目を質問し、記入する
- **検証可能**: どの値がどこから来たか（Evidence）と編集履歴（Activity）を残す
- **両対応**: AcroFormはフィールド入力、非AcroFormは座標オーバーレイ描画

## 非目的（Non-Goals）
- 著しく劣化したスキャンの完全自動化（OCRはベストエフォート）
- 高度な筆跡認識（手書き最適化）
- 署名/ワークフロー/コンプライアンス一式（別スコープ）

## 想定ユーザー
- 定型フォームを繰り返し記入するオペレーション担当/個人
- テンプレートやマッピングを整備する管理者

## 永続化（DB/Storage）
本システムの永続化は **Supabase** を利用する（スクラッチ実装を避ける）。

- **DB**: Supabase Postgres（テンプレ、Evidence、Activity、Jobのメタ/状態、ユーザー設定）
- **Auth**: Supabase Auth（UIログイン/セッション管理）
- **Storage**: Supabase Storage（PDF原本、画像ファイル、プレビュー画像、OCR切り出し、生成物PDF）

## 用語（最小）
- **Source Document**: 旧書類（値の抽出元）。PDFまたは画像ファイル（PNG、JPEG、TIFF等）
- **Target Document**: 新書類（記入先）。PDFまたは画像ファイル（PNG、JPEG、TIFF等）
- **Source PDF / Target PDF**: 上記の旧称（後方互換性のため維持）
- **Field（フィールド）**: テキスト/チェック/表セルなどの入力単位
- **Anchor（アンカー）**: ラベル等、フィールド位置特定の基準
- **Confidence（信頼度）**: 自動確定/質問/レビュー判定に使うスコア
- **Service Loop**: サービス間で状態を回し、品質が満たされるまで反復する仕組み

## ディレクトリ構造（推奨 / 実装ガイド）
本リポジトリはモノレポとして運用し、アプリ（API/Orchestrator/Web/Contracts）とドキュメントを分離する。

### リポジトリ（モノレポ）構造
```text
repo/
  apps/
    api/                    # Public API Gateway (FastAPI)
    orchestrator/           # Pipeline/loop control（必要なら独立）
    web/                    # Frontend (Vite/React)
    contracts/              # OpenAPI/JSON Schema/examples（契約）
  packages/
    schema/                 # 共通スキーマ（任意）
  docs/
    build_by_agent/         # PRD群（サービス別PRD含む）
    steps/                  # 開発手順/ウォークスルー
  infra/
    supabase/               # SQL/migrations/policies/seed（運用に応じて）
  Makefile
  README.md
```

### サービス内部（Clean Architectureの最小テンプレ）
各サービス（`apps/api` / `apps/orchestrator` / 各処理サービス）は、以下の分離を推奨する。

```text
app/
  domain/                   # エンティティ/ドメインルール（純粋）
  application/              # ユースケース、port（interface）
  adapters/                 # DTO変換、controller/presenter
  infrastructure/           # FastAPI, Supabase, 外部SDK, PDF/OCR/LLM等
  main.py                   # 起動点
  config.py                 # 設定
```

## サービス構成と処理ループ（最小）

### Service と Agent の区別（Clean Architecture 視点）

本システムでは、Clean Architecture の原則に基づき、以下のように区別します：

- **Service（サービス）**: 決定論的な業務処理を担うコンポーネント
  - 例: `OcrService`, `PdfWriteService`, `ValidationService`
  - 特徴: 同じ入力→同じ出力、単体テスト可能、副作用あり得る

- **Agent（エージェント）**: LLMによる推論・判断・提案を担うコンポーネント
  - 例: `FieldLabellingAgent`, `ValueExtractionAgent`, `MappingAgent`
  - 特徴: 非決定論的（LLM推論）、モック必須、副作用なしが理想

- **Orchestrator（オーケストレーター）**: UseCase層として、Service（Agent含む）を呼び出す
  - 例: `PdfAutoFillOrchestrator`
  - 特徴: サービス間の順序制御、ループ制御、状態管理

**設計原則**: Orchestrator が呼び出すものはすべて Service だが、その中で推論責務を持つものを Agent と呼ぶ。

### 主要サービス（役割）

- **Ingest Service**: PDF正規化（ページサイズ/回転/レイヤ）
- **Structure/Labelling Service**: 文書構造推定（テキスト/枠/表）
  - 内部で **FieldLabellingAgent** を使用（ラベル⇄位置の紐付け、LLM必須）
- **Mapping Service**: Source↔Targetのフィールド対応づけ（変換含む）
  - 内部で **MappingAgent** を使用（曖昧な対応の解消、LLM推論）
- **Extract Service**: 値抽出（PDFテキスト、必要時OCR）
  - 内部で **ValueExtractionAgent** を使用（曖昧さ解消・正規化・矛盾検知）
  - 内部で **OcrService** を使用（OCR処理）
- **Adjust Service**: 座標補正（アンカー相対・年次差分吸収）
- **Fill Service**: 記入（AcroForm or オーバーレイ描画）
- **Review Service**: 可視化＋失敗検知（差分/はみ出し/重なり）
- **Log/Learn Service**: Evidence/Activity記録、テンプレ/マッピングの版管理

### ループ（収束まで反復）
`Ingest → Structure/Labelling → Map → Extract → Adjust → Fill → Review`
で実行し、低信頼/未入力/レイアウト不整合があれば **質問または直接編集**を挟んで
`Map/Adjust/Fill/Review` を再実行する。

## サービス独立性（Contract-driven / 並行開発前提）
本プロジェクトは、Claude Codeの複数Agentが **サービス単位で並行開発**する。よって各サービスは、
他サービスの内部実装に依存せず、**契約（Contract）だけ**で接続される必要がある。

### Clean Architecture採用（必須）
各サービスの内部実装は **Clean Architecture** を採用し、リポジトリ移動・技術選定変更・並行開発に強い構造にする。

- **レイヤ（推奨構成）**
  - **Domain**: エンティティ/値オブジェクト/ドメインルール（例: Field, Evidenceの整合ルール）
  - **Application**: ユースケース（例: `LinkLabelsToBBoxes`, `GenerateMappings`, `SelectOcrCrops`）
  - **Interface Adapters**: DTO変換、Presenter、Repository interface、Gateway interface
  - **Infrastructure**: FastAPI, DB, Queue, OCR/LLM SDK, PDFライブラリ等の具体実装

- **依存関係ルール（Dependency Rule）**
  - 依存は **外側 → 内側のみ**。Domain/Applicationはインフラに依存しない。
  - 具体実装（LLM/OCR/PDF/DB/Queue）は **Port（interface）** の実装として差し替え可能にする。

- **Repository / Adapter方針**
  - 永続化（テンプレ/Activity/Evidence）は `Repository interface` を介して使用し、DB変更に耐える。
  - 外部API（LLM/OCR）は `Gateway interface` を介し、ベンダ/SDK変更に耐える。
    - LLM統合は LangChain を Port（interface）として実装し、モデルプロバイダー変更に耐える。
    - OCR統合も同様に Port として抽象化し、PaddleOCR/pytesseract/EasyOCR などを差し替え可能にする。
  - Service間通信は `Client Adapter`（生成SDK）に閉じ込め、契約変更以外で破壊しない。

- **テスト方針（最小）**
  - Application（ユースケース）はインフラなしでユニットテスト可能にする（mock port）。
  - Contract test（examples + schema）はサービス境界の回帰を防ぐため必須。

### 原則
- **共有物はContractのみ**: 共通のPythonモジュールを横断importしない（例外は型定義の自動生成のみ）
- **ステートレス優先**: サービスは「同じ入力→同じ出力」を基本とし、状態はOrchestratorまたは永続層が持つ
- **データ所有権の明確化**: 同じフィールドを複数サービスが“勝手に上書き”しない（Single writer）

### Contract（最低限の合意）
- **共通スキーマ**: `Document / Field / Mapping / Extraction / Evidence / Activity / Issue / JobContext`
- **入出力サンプル（examples）**: 実装開始前に「このJSONが入ったらこのJSONが返る」を固定する
- **互換性テスト（contract test）**: examplesを用いたスキーマ検証をCIで必須化する

### 役割分担（Single writerの例）

各サービスは以下の責務を持ち、内部でAgentを使用する場合がある：

- **Structure/Labelling Service**: `Field`（name/type/bbox/anchor）を生成・更新する唯一の主体
  - 内部の `FieldLabellingAgent` がラベル⇄位置の紐付けを実行
- **Extract Service**: `Extraction` と `Evidence(kind=native_text|ocr)` を生成する唯一の主体
  - 内部の `ValueExtractionAgent` が曖昧さ解消・正規化を実行
  - 内部の `OcrService` がOCR処理を実行
- **Mapping Service**: `Mapping` を生成・更新する唯一の主体
  - 内部の `MappingAgent` が対応づけの意思決定を実行
- **Adjust Service**: `Field.bbox` の補正案を生成（採用はOrchestratorが決定しActivityに残す）
- **Fill Service**: `filled.pdf` と描画パラメータを生成
- **Review Service**: `Issue[]` を生成
- **Log/Learn Service**: `Evidence/Activity` の永続化とテンプレ/版管理

### 実装形態（推奨）
- **各サービスは独立実装**（FastAPIでHTTP提供、またはワーカーとしてキュー実行）
  - サービス内部でAgentを使用する場合、AgentはPort（interface）として実装し差し替え可能にする
- **Orchestratorが接着**: Service（Agent含む）を順序/条件で呼び分け、JobContextを更新してループ制御する

## エージェント設計パターン選定（Google提唱パターンの適用）
参考: `https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system?hl=ja`

### 推奨: 「Sequential + Loop + Review/Critique + Human-in-the-loop」の組み合わせ
本システムは、PDFの解析→抽出→マッピング→座標補正→描画→検証→（必要なら再実行）
という **順序性の高い工程**と、**品質改善の反復**が中心です。よって以下の混合が最適です。

- **マルチエージェント・シーケンス（Sequential pattern）**
  - **狙い**: サービスを安定した直列パイプラインとして実行し、再現性を担保する。
  - **対応**: Ingest Service → Structure/Labelling Service → Mapping Service → Extract Service → Adjust Service → Fill Service → Review Service
  - 各サービス内部でAgent（FieldLabellingAgent, MappingAgent, ValueExtractionAgent等）が推論を実行

- **マルチエージェント・ループ（Loop pattern）**
  - **狙い**: 座標系・レイアウト差分・OCRゆらぎなどを反復補正し、精度を上げる。
  - **対応**: Adjust ↔ Review ↔ Confidence Scorer の反復。

- **レビューと批評（Review/Critique pattern）**
  - **狙い**: 出力を“見た目”で検証し、はみ出し・重なり・桁ズレなどの失敗を検出する。
  - **対応**: Review（オーバーレイ/差分）＋ Confidence Scorer（ルール/ML）。

- **人間参加型（Human-in-the-loop pattern）**
  - **狙い**: 低信頼・矛盾・例外ケースを、最小の質問で確実に収束させる。
  - **対応**: Question Generator（不足情報/不確実フィールドのみ質問）＋ユーザー入力
    → Map/Adjust/Fill の再実行。

### ReActは「中核」ではなく「限定領域」で使う
ReAct（Reason-Act-Observe）は、動的探索が必要な箇所には有効ですが、
本システムの中心は **構造化された確定的ワークフロー**です。
そのため、ReActは以下のような限定領域での採用が適しています。

- **質問生成**: 「何を聞けば最小回数で埋まるか」の意思決定。
- **例外時ルーティング**: AcroForm優先/非AcroFormの座標描画、OCR起動判断、
  テンプレ候補探索、フィールド競合解消など。

### ループの終了条件（無限ループ防止）
- **品質閾値**: field-level confidence が閾値以上（例: \( \ge 0.85 \)）に到達
- **最大反復回数**: 例 3〜5 回
- **ユーザー承認**: レビュー画面で「OK」
- **失敗の確定**: これ以上改善しない（改善率が閾値未満）場合は人間入力へ切替

## 要件（機能要件の最小セット）
### 入力フロー
- **転記（copy/transfer）**: Source Document（PDFまたは画像）+ Target Document（PDFまたは画像）をアップロード → 自動抽出/マッピング → 不足/低信頼だけ質問 → 記入 → レビュー
- **スクラッチ（scratch）**: Target Document（PDFまたは画像）をアップロード → 必須項目を質問 → 記入 → レビュー

**画像ファイルの処理**:
- アップロードされた画像ファイル（PNG、JPEG、TIFF等）は自動的にPDFに変換される
- 変換後のPDFは通常のPDFと同様に処理される
- 元の画像ファイルも保存され、Evidenceとして参照可能

### フィールド検出と記入方式
- **AcroFormあり**: フィールド情報（名称/種別/矩形）を取得し、直接入力
- **AcroFormなし**: ラベル/枠/表などのレイアウトから入力領域を推定し、座標オーバーレイで描画

### 精度向上（抽出・配置）
- **抽出**: PDFテキスト → 必要時OCR → 表/枠/近傍ラベルの推定（段階的）
- **配置**: アンカー（ラベル）＋相対オフセットで座標を補正（年次レイアウト差分に強い）
- **信頼度**: OCR信頼度 + ラベル一致度 + 幾何整合（枠内収まり等）を統合

### LLMフレームワーク選定（LangChain推奨）
本システムのLLM統合には **LangChain** を推奨する。
参考: `https://docs.langchain.com/oss/python/langchain/overview`

- **推奨理由**
  - **標準化されたモデルインターフェース**: OpenAI、Anthropic、Googleなど複数プロバイダーを統一APIで扱え、ロックインを回避
  - **エージェント構築の容易さ**: 10行未満でエージェントを作成可能、構造化ワークフローとの統合が容易
  - **LangGraph基盤**: 耐久実行、ストリーミング、human-in-the-loop、永続化などの高度機能を提供
  - **デバッグ支援**: LangSmithによる実行パスの可視化、状態遷移の追跡、ランタイムメトリクス取得
  - **ツール統合**: OCR結果、PDF抽出データ、座標情報などをツールとしてエージェントに提供可能

- **適用領域（Agentとして実装）**
  - **FieldLabellingAgent**（Structure/Labelling Service内）: ラベル⇄位置の紐付け（必須）
  - **MappingAgent**（Mapping Service内）: Source↔Target対応づけの意思決定支援
  - **ValueExtractionAgent**（Extract Service内）: 曖昧さ解消・正規化・矛盾検知の補助推論
  - **QuestionGenerationAgent**（Orchestrator内）: 最小質問セットの生成（ReActパターン適用）

- **実装方針**
  - Agentは各Service内部でPort（interface）として実装し、差し替え可能にする
  - LangChainの `create_agent` または LangGraphでカスタムワークフローを構築
  - OCR/PDF抽出結果を `Tool` として提供し、Agentが動的に呼び出し可能にする
  - 構造化出力（Structured Output）を活用し、`Field`、`Evidence`、`Mapping` などの型安全な結果を取得
  - ServiceはAgentを呼び出すが、Agentの実装詳細（LangChain等）に依存しない設計にする

### OCRとAgentの役割分担（システム表現）
方針: **OCRでできる範囲はOCRで確定**し、曖昧さの解消・構造化・正規化が必要な場合のみ
**Agentに付属情報（Evidence）として渡して判断させる**。

- **重要: ラベル⇄位置（アンカー/フィールド同定）はAgentが必須**
  - ラベル文字列の揺れ、複数候補、表/枠のネスト、年次レイアウト差分により、
    ルールベースだけでは誤対応が増えるため。
  - そのため `Structure/Labelling Service` 内の `FieldLabellingAgent` が常に呼び出され、
    「ラベル（意味）」「対象フィールド種別」「対象bbox/座標」「根拠（Evidence）」を確定する。

- **独自OCR（決定的コンポーネント）**
  - 入力: ページ画像 or 領域切り出し画像（Field/Anchor周辺）
  - 出力（標準化）:
    - `ocr_text`（行/単語/文字）
    - `ocr_tokens[]`（text, bbox, confidence）
    - `ocr_lines[]`（text, bbox, confidence）
    - `ocr_language` / `script`（例: ja-JP）
    - `artifacts`（必要に応じて切り出し画像への参照、前処理情報）
  - 目的: **テキスト化と座標付きEvidence生成**（LLMの入力材料を作る）

- **LLM（推論コンポーネント：OCRの代替ではなく“補助”）**
  - 入力: `Field`定義（type/bbox/anchor）、PDFテキスト抽出結果、OCRの `ocr_tokens/lines`、
    そして必要に応じて **切り出し画像の参照**（または要約特徴）
  - ツール: OCR結果取得、PDFテキスト検索、座標計算、Evidence生成などのツールをLangChainエージェントに提供
  - 出力（例）:
    - `value_candidates[]`（value, confidence, rationale, evidence_refs）
    - `normalized_value`（表記統一: 全角/半角、日付形式、住所正規化など）
    - `conflict_detected`（矛盾の検出）
    - `followup_questions[]`（不足/不確実を埋める最小質問）
  - 目的: **曖昧さの解消・形式正規化・矛盾検知・質問生成**

- **実行ルール（いつLLMを使うか）**
  - **必ず使う**: **ラベル⇄位置の紐付け**（アンカー確定、フィールド同定、表/枠の解釈）
  - **使わない**: （上記の紐付けが完了した前提で）PDFネイティブテキストで高信頼に抽出できる／AcroFormの値取得が可能
  - **使う**: OCR信頼度が低い、候補が複数ある、表/住所/氏名などの正規化が必要、
    ラベル/アンカーと値の対応が曖昧、矛盾がある

- **パイプライン（抽出の最小ループ）**
  - `Extract Service` が `native_pdf_text` を抽出
  - `if missing/low_confidence: OcrService(crop(field/anchor region)) -> evidence`
  - `if still ambiguous: ValueExtractionAgent(evidence + field_context + tools) -> candidates/normalize/questions`
  - `Confidence Scorer -> Ask (必要なら) -> Mapping/Adjust/Fill/Review Service`

### レビューと修正
- **可視化**: オーバーレイ/差分で「はみ出し・重なり・未入力」を検知して提示
- **修正**: 直接編集（値/座標）またはチャット指示で再実行
- **監査性**: Evidence（根拠）と Activity（編集履歴）を保持・エクスポート

## 受け入れ基準（MVP）
MVPの「できた」をブレなく判定するための最小セット。

### 品質（フィールド）
- **自動確定率**: 対象フィールドのうち、ユーザー質問なしで確定できた割合（例: \(\ge 60\%\)）
- **正解率（確定フィールド）**: 自動確定したフィールドの値が正しい割合（例: \(\ge 95\%\)）
- **質問回数**: 1ドキュメントあたりの質問数（例: 平均 \(\le 8\)）

### 品質（配置）
- **枠内率**: 文字描画がフィールドbbox内に収まる割合（例: \(\ge 99\%\)）
- **重なりゼロ**: 他フィールドbboxとの交差がゼロ（既定。例外は手動承認）

### 監査性
- **Evidence必須**: すべての確定値に `evidence_refs` がある（source/bbox/confidence）
- **Activity必須**: すべてのユーザー編集は before/after が記録される

### 性能（目安）
- **解析**: 1ページあたり60秒以内（ベストエフォート）

## Dynamic Decision Points（Agenticに動く判断点）
「固定パイプライン」ではなく、状況に応じて分岐・反復・質問で収束させる箇所の仕様。

### D1: ラベル⇄位置の紐付け（FieldLabellingAgent必須）
- **入力（state/evidence）**: `label_candidates[]`, `box_candidates[]`, `table_candidates[]`, 近傍関係、必要な切り出し参照
- **実装**: `Structure/Labelling Service` 内の `FieldLabellingAgent` にOCR結果、PDFテキスト、座標情報をツールとして提供
- **出力**: `fields[]`（name/type/page/bbox/anchor/confidence/evidence_refs）
- **失敗時**: 低信頼フィールドを `needs_review=true` として残し、UIで手動同定へ

### D2: Source↔Targetの対応づけ（Map）
- **入力**: source側/target側の `fields[]`、テンプレ履歴、ユーザー指示（チャットルール）
- **出力**: `mappings[]`（対応、変換、根拠）
- **分岐**: 1対多/多対1/表の行対応が不確実なら `followup_questions` を生成

### D3: どこをOCRするか（Evidence収集の最適化）
- **入力**: native抽出結果、未確定フィールド、anchor情報、ページ画像参照
- **出力**: `ocr_requests[]`（page, crop_bbox, purpose）
- **停止条件**: 追加OCRしても改善が見込めない場合は質問/手動へ

### D4: OCR結果をAgentに渡すか（補助推論）
- **入力**: `ocr_tokens/lines`、フィールド定義、候補値の競合状況
- **実装**: `Extract Service` 内の `ValueExtractionAgent` にOCR結果をツールとして提供し、必要に応じて動的に呼び出し
- **出力**: `value_candidates[]`, `normalized_value`, `conflict_detected`, `followup_questions[]`
- **原則**: Agentは「OCR代替」ではなく、曖昧さ解消・正規化・矛盾検知に限定

### D5: 次に何をするか（ループ制御）
- **入力**: `Review.issues[]`（はみ出し/重なり/未入力/矛盾）、confidence、ユーザー編集
- **出力（action）**:
  - `Adjust` 再実行（座標/折返し/フォント/サイズの再計算）
  - `Fill` 再実行（描画ルール変更）
  - `Ask`（不足/不確実を埋める最小質問）
  - `Manual`（UI直接編集へ）
- **終了条件**: 閾値到達、最大反復、ユーザー承認、改善率低下で人手へ

## Evidence / Activity（最小スキーマ）
### Evidence（根拠）
「この値はどこから来たか」を再現可能にする。

```json
{
  "evidence_id": "ev_...",
  "kind": "native_text|ocr|llm_linking|user_input",
  "document": "source|target",
  "page": 1,
  "bbox": [x0, y0, x1, y1],
  "text": "string",
  "confidence": 0.0,
  "artifact_ref": "optional://crop-image-or-object-storage-ref"
}
```

### Activity（編集履歴）
ユーザー/エージェントの変更を時系列で追えるようにする。

```json
{
  "activity_id": "ac_...",
  "actor": "user|agent",
  "timestamp": "ISO-8601",
  "action": "set_value|move_bbox|change_format|resolve_conflict",
  "field_id": "fld_...",
  "before": { "value": "old", "bbox": [0,0,0,0] },
  "after":  { "value": "new", "bbox": [0,0,0,0] },
  "reason": "free text",
  "evidence_refs": ["ev_..."]
}
```

## UI / UX仕様（Chatベース＋直接編集）
### 画面レイアウト（4ペイン）
- **上部ペイン（Document Viewer）**:
  - PDF表示（ページ切替、ズーム、回転、検索）
  - フィールドのハイライト（BBox表示、アンカー/ラベルの表示切替）
  - **直接編集**（クリック/ドラッグで位置調整、テキストの上書き、チェックボックス切替）
- **左ペイン（Field List / Field Inspector）**:
  - フィールド一覧（ページ、種類、ラベル、状態: filled/missing/low-confidence）
  - 選択フィールドの詳細（BBox、アンカー、推定値、信頼度、マッピング先/元）
  - フィルタ（missingのみ、low-confidenceのみ、ページ別、カテゴリ別）
- **ボトムペイン（Chat / Natural Language Control）**:
  - 自然言語での指示（例:「前年の住所を新様式に転記して」「不足分だけ聞いて」）
  - システムからの質問（不足情報、矛盾、低信頼の確認）
  - 実行ログ（どのサービスが何をしたかの要約）と、再実行/取り消し
- **右ペイン（Activity / Evidence）**:
  - **入力ソース（Evidence）**: 値の根拠（抽出元ページ/座標、OCR結果、ラベル一致）
  - **編集履歴（Activity）**: 変更前後、誰が（user/agent）変更したか、時刻、理由
  - 競合解決の履歴（候補値、選択理由、却下理由）

### 基本操作（自然言語＋直接操作）
- **自然言語（チャット）でできること**
  - 取り込み: 「この2つのPDFで転記して」「このPDFをゼロから埋めて」
  - ルール: 「氏名は全角、電話はハイフンあり」「住所は郵便番号から生成して」
  - 修正: 「この欄の座標を少し下に」「このページの表は手入力に切り替えて」
  - 検証: 「重なっているところを直して」「不足だけ質問して」
- **ドキュメント直接編集でできること**
  - フィールドをクリックして値を編集（即時プレビュー）
  - フィールドのドラッグで座標補正（Adjustにフィードバック）
  - テキストのフォント/サイズ調整（Fillにフィードバック）

### UIとエージェントループの接続（重要）
- **左ペイン選択 → 上部ペインにジャンプ**: 選択フィールドを自動スクロールして強調表示。
- **上部ペイン編集 → 右ペインに証跡**: 編集がActivityとして積まれ、根拠（Evidence）を更新。
- **チャットの回答 → すぐ再描画**: 回答が `Map/Adjust/Fill/Review` をトリガし、上部ペインを更新。

### レビュー体験（ミスを減らす）
- 差分モード: 「元PDF」「新PDF」「オーバーレイ」「差分強調」を切替。
- エラー検知表示: はみ出し/重なり/桁ズレ/未入力を右ペインのIssueとして一覧化。
- 1クリック修正導線: Issueクリックで対象フィールドへジャンプ→編集→再描画。

### AcroForm Field Visualization（フォームフィールド可視化）

PDFドキュメントにAcroFormフィールドが存在する場合、プレビュー上にフィールド境界をハイライト表示する機能。

**機能**:
- AcroFormフィールドの自動検出
- フィールド境界の視覚的ハイライト（半透明の青色オーバーレイ）
- ホバー時にフィールド名をツールチップ表示
- ズーム・ページ切替に追従
- フィールドクリックで選択（将来的に編集連携）

**API**:
- `GET /api/v1/documents/{id}/acroform-fields`
- レスポンス: フィールド情報（名前、種別、座標）、ページ寸法、プレビュースケール

**座標系**:
- PDF座標（左下原点）→ 画面座標（左上原点）に変換
- プレビュー画像のスケール（2x）を考慮
- UIズームレベルに追従

**コンポーネント**:
- `FieldOverlay`: フィールドハイライトオーバーレイ
- `PageViewer`: `showFieldOverlay`プロパティでオーバーレイ表示を制御

## データモデル（最小）
- `Document`: id, kind(source/target), pages, meta
- `Field`: id, name, type, page, bbox, anchor
- `Extraction`: field_id, value, source, confidence, evidence
- `Mapping`: source_field_id, target_field_id, transform
- `Activity`: actor(user/agent), action, before/after, timestamp, reason

## API（最小）
- `POST /documents` アップロード（PDFまたは画像ファイルをサポート）
- `POST /analyze` フィールド/アンカー推定
- `POST /extract` 値抽出（必要時OCR含む）
- `POST /fill` 記入（AcroForm or overlay）
- `POST /review` レビュー用（差分画像 + フィールド状態 + Evidence/Activity）

**サポートするファイル形式**:
- PDF: `application/pdf`
- PNG: `image/png`
- JPEG: `image/jpeg`
- TIFF: `image/tiff`
- WebP: `image/webp`（オプション）

## 非機能要件（最小）
- **性能**: 5ページあたり解析10秒以内（ベストエフォート）
- **再現性**: 同一入力＋同一テンプレで決定的に同一出力
- **プライバシー**: アップロード文書の安全な保管/削除（要件に応じて）

## リスク（最小）
- **検出ミス**: 手動フィールド作成/アンカー定義で救済
- **OCR誤り**: レビュー＋質問で確実化
- **フォント**: 日本語フォント選択/埋め込み（例: `cid0jp` 系）を用意
- **年次差分**: アンカー相対補正＋テンプレバージョニング

## 指標（最小）
- フィールド正解率、質問率、ユーザー修正率、完了時間

## マイルストーン（最小）
1. **MVP**: AcroForm入力＋手動マッピング＋レビュー
2. **非AcroForm**: オーバーレイ描画＋アンカー補正
3. **ループ**: 信頼度スコア＋質問→再描画
4. **学習**: テンプレ/補正の蓄積（再利用）
5. **表対応**: 表構造推定とセル単位マッピング
