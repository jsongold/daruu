# PRD: Public API（Backend API Gateway）

## 目的
フロント/外部クライアントに対して、ジョブ作成〜実行〜レビュー〜成果物取得までを提供する。
内部サービス（Ingest/Structure/Labelling/…）の実装詳細を隠蔽し、Contractを介した安定した境界を作る。

## 前提
- BackendはPythonで開発（FastAPI想定）
- Contract-driven（OpenAPI/JSON Schema）を正とし、後方互換を維持する
- 重い処理（OCR/レンダリング/Agent推論）は非同期ジョブとして扱う
- 認証/ユーザー管理/ファイル保管は **Supabase** を利用する（スクラッチ回避）

## Service と Agent の関係

APIは内部の **Service** を呼び出す。Serviceは以下のいずれか：
- **決定論的なService**: `OcrService`, `PdfWriteService`, `ValidationService` など
- **Agentを含むService**: `Structure/Labelling Service`（内部で`FieldLabellingAgent`使用）、
  `Extract Service`（内部で`ValueExtractionAgent`使用）、
  `Mapping Service`（内部で`MappingAgent`使用）など

APIはServiceの内部実装（Agentの有無）を知る必要はなく、Contract（入出力）のみで接続する。

## APIの原則（他PRDとの整合）
- **ベースパス**: `/api/v1`（実装と揃える）
- **単一の状態表現**: 画面は `JobContext` を正とする（Field/Evidence/Activity/Issueを内包）
- **Blockedを第一級に扱う**: 処理は `blocked` で止まり、`answers`/`edits` により再開する
- **Agent/OCR/PDFの内製はしない**: APIは境界であり、処理は内部Serviceへ委譲する

## スコープ
- 認証、ドキュメントアップロード、ジョブ管理、ステップ実行、レビュー取得、成果物DL
- UIの4ペインに必要なデータ（Field/Evidence/Activity/Issue/Preview）を返す

## 非スコープ
- OCR/Agent/PDF処理の実装（内部Service）
- テンプレ学習のアルゴリズム（Log/Learn Service）

## Auth / RBAC（Supabase）
- クライアントはSupabase Authでログインし、**JWT** を取得する
- APIは `Authorization: Bearer <supabase_jwt>` を検証し、`user_id` を特定する
- マルチテナント運用を想定する場合は、Supabase RLSで `user_id` スコープに制限する

## エンドポイント（MVP案）
### Documents
- `POST /api/v1/documents`
  - multipart upload（source/targetのアップロード）
  - レスポンス: `document_id`, `document_ref`, `meta`（ページ数/サイズ等）
  - 取り込み後のPDF原本は Supabase Storage に保存し、`document_ref` はその参照を指す
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/pages/{page}/preview`（PNG/JPEG）
  - UI表示用。大きいPDFはプレビュー画像を返すほうが安定
  - 方式: APIがバイナリを返す or Storageの署名URLを返す（どちらかに統一）

### Jobs（copy/transfer / scratch）
- `POST /api/v1/jobs`
  - body: `{ mode: "transfer"|"scratch", source_document_id?, target_document_id, rules?, thresholds? }`
  - response: `job_id`
- `GET /api/v1/jobs/{job_id}`
  - response: `JobContext`（状態/fields/mappings/extractions/issues/activities…）

### Run / Loop control
- `POST /api/v1/jobs/{job_id}/run`
  - body: `{ run_mode: "step"|"until_blocked"|"until_done", max_steps?: number }`
  - response: `{ status: "running"|"blocked"|"done", job_context, next_actions? }`
  - `next_actions` はUIが次にやること（ask/manual/retry等）を表す（任意）

### Q&A（不足情報入力）
- `POST /api/v1/jobs/{job_id}/answers`
  - body: `{ answers: [{ field_id, value }] }`
  - response: updated `JobContext`

### Manual edits（UI直接編集の反映）
- `POST /api/v1/jobs/{job_id}/edits`
  - body: `{ edits: [{ field_id, value?, bbox?, render_params? }] }`
  - response: updated `JobContext`

### Review / Activity / Evidence
- `GET /api/v1/jobs/{job_id}/review`
  - response: `{ issues[], previews[], fields[], confidence_summary }`
- `GET /api/v1/jobs/{job_id}/activity`
- `GET /api/v1/jobs/{job_id}/evidence?field_id=...`

### Output
- `GET /api/v1/jobs/{job_id}/output.pdf`
- `GET /api/v1/jobs/{job_id}/export.json`（fields/mappings/extractions/evidence/activity）

## リアルタイム更新（推奨）
UIの体験（チャット/進捗）を良くするため、いずれかを採用。
- **SSE**: `GET /api/v1/jobs/{job_id}/events`（progress, activity追加, status遷移）
  - 最初のMVPはSSE推奨（実装が軽い）
- **WebSocket**: `WS /api/v1/jobs/{job_id}/ws`（必要になってから）

## Storage参照（Supabase Storage）
- PDF原本・生成物・プレビュー・OCR切り出しは Supabase Storage に置く
- APIが返すのは次のどちらかに統一
  - **(A) APIがバイナリをプロキシして返す**（権限管理が単純）
  - **(B) 署名URLを返す**（帯域効率が良い。期限管理が必要）

## エラー設計（最小）
- `400`：入力不正（schema違反）
- `401/403`：認証/権限
- `404`：存在しないID
- `409`：状態競合（同時編集/実行）
- `422`：処理不能（パスワードPDF等）
- `500`：内部エラー（trace_idを返す）

## 互換性（Contract-driven）
- OpenAPI/JSON Schema/examplesを `apps/contracts` に置き、APIはそれに追従する
- 破壊的変更はSemVer majorのみ（後方互換を壊さない）

## 受け入れ基準（MVP）
- フロントが「アップロード→ジョブ作成→実行→blockedで質問→回答→done→PDF取得」まで完走できる
- `JobContext` が常にschemaに一致し、後方互換を壊さない
- 進捗がSSE/WSのいずれかで取得できる（なくてもMVP可だが推奨）

