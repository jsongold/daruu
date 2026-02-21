# PRD: Frontend（4ペインUI＋Chat操作）

## 目的
ユーザーが自然言語（チャット）と直接編集で、PDFの転記/スクラッチ入力を完了できるUIを提供する。
Evidence/Activityを可視化し、反復ループ（Ask/Adjust/Fill/Review）を迷わず回せる体験を作る。

## 前提
- UIは **チャットがベース**
- レイアウトは **上:ドキュメント / 左:フィールド / 下:チャット / 右:Evidence+Activity**
- 操作は「自然言語」と「ドキュメント直接編集」が基本

## 主要画面/レイアウト
### 上部ペイン（Document Viewer）
- PDF表示（ページ切替、ズーム、回転）
- Fieldハイライト（bbox、anchor表示切替）
- 直接編集
  - 値編集（テキスト/チェック）
  - bbox移動/サイズ変更（ドラッグ）
  - 編集結果を即時プレビュー

### 左ペイン（Field List / Inspector）
- フィールド一覧（ページ/種別/状態: filled/missing/low-confidence）
- フィールド詳細（bbox、anchor、confidence、mapping先/元）
- フィルタ（missing/low-confidence/ページ/カテゴリ）

### ボトム（Chat）
- 自然言語での指示（例: 「不足だけ聞いて」「住所は2行で」）
- システムからの質問（最小質問）
- 実行ログ（どこまで進んだか）と再実行ボタン（run/step）

### 右ペイン（Evidence / Activity）
- Evidence（抽出元、ページ/座標、OCR信頼度、根拠プレビュー）
- Activity（before/after、actor、理由、時刻）
- Issue一覧（Review結果）→クリックで該当フィールドへジャンプ

## ユースケース（MVP）
- Transfer: source+targetアップロード → run → 質問に答える → done → output.pdf取得
- Scratch: targetアップロード → 質問に答える/直接編集 → done
- Review: Issueを潰す（bbox調整/書式変更/値修正）→再実行→done

## UIからAPIへのアクション対応
- Upload: `POST /documents`
- Job作成: `POST /jobs`
- 実行: `POST /jobs/{id}/run`（step / until_blocked / until_done）
- 質問回答: `POST /jobs/{id}/answers`
- 直接編集: `POST /jobs/{id}/edits`
- Review取得: `GET /jobs/{id}/review`
- Evidence/Activity: `GET /jobs/{id}/evidence`, `GET /jobs/{id}/activity`
- 出力DL: `GET /jobs/{id}/output.pdf`

## リアルタイム更新（推奨）
- SSE/WSでジョブ進捗とActivity追加を購読し、チャットに逐次表示する

## 状態管理（最小）
- `JobContext` を単一のソースとして保持（サーバ返却を正）
- フィールド選択状態（selected_field_id）
- ページ/ズーム状態
- 未送信の編集（optimisticに見せる場合は差分管理）

## 受け入れ基準（MVP）
- 4ペインUIでE2Eが完走できる（transfer/scratch）
- フィールド選択→PDFジャンプ、Issueクリック→ジャンプが動く
- 直接編集がActivityとして反映され、再実行で結果が更新される

