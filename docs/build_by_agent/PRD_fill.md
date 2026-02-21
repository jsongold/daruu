# PRD: Fill Service（PDF記入）

## 目的
`Field + Extraction/Value` を使って Target PDF に記入し、`filled.pdf`（または参照）を生成する。
AcroFormは直接入力、非AcroFormはオーバーレイ描画→マージ。

## Service の性質

本Serviceは **決定論的なService** です（Agentを含みません）。
- 同じ入力→同じ出力
- 単体テスト可能
- LLM推論は使用しない

## 責務（Single writer）
- `filled.pdf` の生成
- 文字描画のルール（折返し、フォント、サイズ、アライン）の適用

## 入出力（Contract）
- **入力**: target_document_ref, fields[], values（extractions or user_input）, render_params（任意）
- **出力**: filled_document_ref, render_artifacts（任意：overlay_refなど）

## API（案）
- `POST /fill`（target + fields + values → filled_ref）

## 推奨ライブラリ
- PyMuPDF(fitz)（描画/マージ）
- reportlab（オーバーレイ生成の選択肢）
- pypdf（マージ補助）

## 受け入れ基準（MVP）
- AcroForm/非AcroFormの両方で出力PDFが生成できる
- 日本語描画が破綻しない（フォント選択/埋め込み方針を実装）

