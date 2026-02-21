# PRD: Structure/Labelling Service（構造解析＋ラベル⇄位置紐付け）

## 目的
Target/Sourceのページから **構造（枠/表/テキスト候補）** を抽出し、**FieldLabellingAgent**を用いて **ラベル（意味）⇄bbox（位置）** を紐付けて `Field[]` を確定する。

## 必須要件
- **ラベル⇄位置紐付けはFieldLabellingAgent必須**（ルールのみで確定しない）
- 出力は `fields[]`（name/type/page/bbox/anchor/confidence/evidence_refs）として契約化

## Service と Agent の関係

本Serviceは以下の構成：
- **Structure/Labelling Service**: 決定論的な構造抽出と、Agent呼び出しの調整
- **FieldLabellingAgent**: LLMによる推論・判断（ラベル⇄位置の紐付け）

ServiceはAgentをPort（interface）として実装し、差し替え可能にする。

## 責務（Single writer）
- `Field` の生成・更新（name/type/bbox/anchor）
- `Evidence(kind=llm_linking)` の生成（根拠を残す）

## 非責務
- 値抽出（Extractの責務）
- 座標微調整（Adjustの責務）

## 入出力（Contract）
- **入力**: page_images, native_text_blocks（任意）, box/table候補（opencv等で抽出）
- **出力**: `fields[]` + `evidence[]`

## API（案）
- `POST /structure_labelling`（document_ref + artifacts → fields + evidence）

## 推奨ライブラリ
- OpenCV（枠線/表候補/近傍特徴）
- PyMuPDF / pdfplumber（テキストブロック候補）
- **FieldLabellingAgent実装**: LangChain（推奨）を使用してAgentを実装
  - LangChainの `create_agent` または LangGraphでカスタムワークフローを構築
  - OCR結果、PDFテキスト、座標情報をツールとしてAgentに提供
  - 複数プロバイダー（OpenAI/Anthropic/Google等）を統一APIで扱える
  - AgentはPort（interface）として実装し、差し替え可能にする
- httpx + tenacity（リトライ/エラーハンドリング）

## Dynamic decision（要点）
- 複数候補があるとき、**FieldLabellingAgent**が「どのラベルがどの入力枠か」「表のヘッダと列対応」を決定
- OCR結果、PDFテキスト抽出、座標計算などのツールをFieldLabellingAgentに提供し、動的に呼び出し可能にする
- confidenceが低いフィールドは `needs_review=true` 相当のフラグで返す（schemaで定義）

## 受け入れ基準（MVP）
- 主要フィールド（氏名/住所/日付/金額など）で `Field` を返せる
- `evidence_refs` が必ず付与される

