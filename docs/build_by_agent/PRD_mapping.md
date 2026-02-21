# PRD: Mapping Service（Source↔Target対応づけ）

## 目的
Source/Targetの `Field[]` を入力として、対応関係 `Mapping[]` を生成し、転記（copy/transfer）の骨格を作る。

## Service と Agent の関係

本Serviceは以下の構成：
- **Mapping Service**: 決定論的なマッピング処理と、Agent呼び出しの調整
- **MappingAgent**: LLMによる推論・判断（曖昧な対応の解消）

ServiceはAgentをPort（interface）として実装し、差し替え可能にする。

## 責務（Single writer）
- `Mapping` の生成・更新（1対1、1対多、表行対応を含む）
- 不確実な対応に対する `followup_questions[]` の生成（必要時）

## 入出力（Contract）
- **入力**: source_fields[], target_fields[], user_rules（任意）, template_history（任意）
- **出力**: mappings[], evidence_refs（任意）, followup_questions[]（任意）

## API（案）
- `POST /map`（source_fields + target_fields → mappings）

## 推奨ライブラリ
- **MappingAgent実装**: LangChain（推奨）を使用してAgentを実装
  - LangChainの `create_agent` または LangGraphでカスタムワークフローを構築
  - 複数プロバイダー（OpenAI/Anthropic/Google等）を統一APIで扱える
  - 構造化出力（Structured Output）を活用し、`mappings[]`、`followup_questions[]` を型安全に取得
  - AgentはPort（interface）として実装し、差し替え可能にする
- httpx + tenacity（リトライ/エラーハンドリング）
- rapidfuzz（文字列類似の候補生成・高速化）

## 受け入れ基準（MVP）
- top-N候補生成→確定（または質問）まで一貫して返せる
- 生成したmappingがschemaを満たし、決定的に再現できる（同入力で同出力）

