# PRD: Review Service（可視化＋不整合検知）

## 目的
`filled.pdf` をレンダリングし、差分/オーバーレイで品質を検査して `Issue[]` を生成する。

## Service の性質

本Serviceは **決定論的なService** です（Agentを含みません）。
- 同じ入力→同じ出力
- 単体テスト可能
- LLM推論は使用しない

## 責務（Single writer）
- `Issue[]` の生成（はみ出し、重なり、未入力、矛盾 など）
- プレビュー画像（page_images）の生成（UI向け）

## 入出力（Contract）
- **入力**: filled_document_ref, fields[], page_meta
- **出力**: issues[], preview_artifacts（image refs）, confidence_updates（任意）

## API（案）
- `POST /review`（filled_ref + fields → issues + previews）

## 推奨ライブラリ
- PyMuPDF(fitz)（レンダリング）
- OpenCV（差分/検知の補助）

## 受け入れ基準（MVP）
- 「はみ出し」「重なり」を検知してIssue化できる
- プレビューが生成できる

