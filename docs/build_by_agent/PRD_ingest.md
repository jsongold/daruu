# PRD: Ingest Service（PDF/画像正規化）

## 目的
PDFおよび画像ファイルを解析/描画/抽出に適した形へ正規化し、後続サービスが同一前提で処理できる入力を作る。

画像ファイルは自動的にPDFに変換してから処理する。

## Service の性質

本Serviceは **決定論的なService** です（Agentを含みません）。
- 同じ入力→同じ出力
- 単体テスト可能
- LLM推論は使用しない

## 責務（Single writer）
- PDF/画像ファイルの検証（形式、破損、パスワード保護等）
- 画像ファイルのPDF変換（PNG、JPEG、TIFF等をPDFに変換）
- PDFメタ取得（ページ数、サイズ、回転、解像度基準）
- ページレンダリング（プレビュー/LLM/OCR用の画像生成）
- 入力の検証（壊れたPDF、パスワード、ページ0等のエラー）

## 入出力（Contract）
- **入力**: `Document`（PDFまたは画像ファイルのバイナリ参照 or object storage ref）
- **出力**: `Document.meta` 更新、`artifacts`（page_images refs など）
- **画像処理**: 画像ファイルは自動的にPDFに変換され、変換後のPDFが処理される

## API（案）
- `POST /ingest`（document_ref → normalized meta + artifacts）

## 実装（推奨ライブラリ）
- PyMuPDF(fitz)（レンダリング/メタ、画像→PDF変換）
- pypdf（補助）
- Pillow（画像読み込み、形式変換）
- pdf2image（画像→PDF変換の補助、必要に応じて）

## 受け入れ基準（MVP）
- PDFのページ情報が取得できる
- 画像ファイル（PNG、JPEG、TIFF）がPDFに変換できる
- ページ画像が生成でき、bbox座標系が後続と一致する（同一原点/単位）
- 変換後のPDFは通常のPDFと同様に処理される

