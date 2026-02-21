# PRD: Extract Service（値抽出＋Evidence生成）

## 目的
Source（またはTarget）の `Field[]` に対し、値を抽出して `Extraction[]` と `Evidence[]` を生成する。
順序は **native PDF text → OCR →（必要時）ValueExtractionAgent補助**。

## Service と Agent の関係

本Serviceは以下の構成：
- **Extract Service**: 決定論的な値抽出の調整と、Service/Agent呼び出しの管理
- **OcrService**: OCR処理（決定論的）
- **ValueExtractionAgent**: LLMによる推論・判断（曖昧さ解消・正規化・矛盾検知）

ServiceはAgentをPort（interface）として実装し、差し替え可能にする。

## 責務（Single writer）
- `Extraction` と `Evidence(kind=native_text|ocr)` の生成
- OCRの対象領域（crop）を決めるための `ocr_requests[]` 生成（D3）

## 非責務
- ラベル⇄位置同定（Structure/Labellingの責務）
- bbox補正（Adjustの責務）

## 入出力（Contract）
- **入力**: document_ref, fields[], artifacts(page_images), user_rules（任意）
- **出力**: extractions[], evidence[], ocr_requests[]（任意）, followup_questions[]（任意）

## API（案）
- `POST /extract`（document_ref + fields → extractions + evidence）

## 推奨ライブラリ
- pdfplumber / PyMuPDF（native text）
- PaddleOCR（推奨）/ pytesseract / EasyOCR（OCR）- OcrServiceとして実装
- OpenCV（前処理）
- **ValueExtractionAgent実装**: LangChain（推奨）を使用してAgentを実装
  - LangChainの `create_agent` または LangGraphでカスタムワークフローを構築
  - OCR結果、PDFテキスト、座標情報をツールとしてAgentに提供
  - 構造化出力（Structured Output）を活用し、`value_candidates[]`、`normalized_value`、`conflict_detected` などを型安全に取得
  - ※「OCR代替」ではなく補助に限定（曖昧さ解消・形式正規化・矛盾検知・質問生成）
  - AgentはPort（interface）として実装し、差し替え可能にする

## 受け入れ基準（MVP）
- `evidence_refs` が常に辿れる（page/bbox/confidence）
- OCR結果は tokens/lines + confidence を返せる

