# PRD: Orchestrator Service（ループ制御）

## 目的
`Ingest → Structure/Labelling → Map → Extract → Adjust → Fill → Review` を実行し、`Issue` と `Confidence` に基づいて **再実行・質問・手動編集**へ分岐しながら、完了条件まで収束させる。

## 責務（Single writer）
- **JobContextの更新/ループ制御**（次アクション決定、最大反復、停止条件）
- **サービス呼び出しの順序/並列の管理**（重い処理は非同期に）
- **Activity生成**（「何をしたか」のイベント履歴。UI/Log-Learnへ渡す）

## 非責務
- OCR/Agent/PDF処理そのもの（各サービスの責務）
- スキーマ定義（contractsの責務）

## Service と Agent の関係

Orchestratorは **Service** を呼び出す。Serviceは以下のいずれか：
- **決定論的なService**: `OcrService`, `PdfWriteService`, `ValidationService` など
- **Agentを含むService**: `Structure/Labelling Service`（内部で`FieldLabellingAgent`使用）、
  `Extract Service`（内部で`ValueExtractionAgent`使用）、
  `Mapping Service`（内部で`MappingAgent`使用）など

OrchestratorはServiceの内部実装（Agentの有無）を知る必要はなく、Contract（入出力）のみで接続する。

## 入出力（Contract）
- **入力**: `JobContext`（documents, rules, thresholds, state）
- **出力**: 更新された `JobContext`、`next_actions[]`、`Activity[]`

## API（案）
- `POST /jobs` 作成（documents参照、初期rules/thresholds）
- `POST /jobs/{job_id}/run` 1ステップまたは完了まで実行（mode: step|until_blocked|until_done）
- `GET /jobs/{job_id}` 状態取得

## ループ制御（要点）
- **基本シーケンス**: `Ingest Service → Structure/Labelling Service → Mapping Service → Extract Service → Adjust Service → Fill Service → Review Service`
- **分岐**:
  - `issues.severity>=high` または `confidence<threshold` → `Ask` or `Manual` を要求して停止（blocked）
  - `layout_issue`（はみ出し/重なり）→ `Adjust/Fill/Review Service` を再実行
  - `mapping_ambiguous` → `Mapping/Extract Service` を再実行（追加Evidence/OCR含む）
- **終了条件**: `Issue==0` かつ `confidence>=threshold` かつ（必要なら）ユーザー承認
- **無限ループ防止**: `max_iterations`、改善率が閾値未満なら `Ask/Manual` へ

## 依存ライブラリ（推奨）
- FastAPI, Pydantic, httpx, tenacity
- Redis（ジョブ状態/ロック）、Celery or RQ（非同期実行）

## テスト/受け入れ基準（MVP）
- examplesで定義した `JobContext` 入力に対し、決定的に同じ `next_actions` を返す
- `max_iterations` を超えない
- blocked/done の状態遷移が仕様通り

