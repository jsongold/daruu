# PRD: Contracts（OpenAPI / JSON Schema / examples）

## 目的
サービス間の唯一の共有物として、**契約（Contract）** を定義・バージョン管理し、リポジトリ構成変更や並行開発でも壊れない接続を保証する。

## スコープ
- OpenAPI（HTTP境界）と JSON Schema（データ型）と examples（入出力サンプル）
- SemVer、互換性ポリシー、Contract test、コード生成方針

## Deliverables
- `openapi/*.yaml`（サービス別 or 集約）
- `schemas/*.json`（Document/Field/Mapping/Extraction/Evidence/Activity/Issue/JobContext…）
- `examples/**`（request/response の最小セット）

## 互換性ルール（必須）
- Contractは **SemVer** で管理
- **破壊的変更**: メジャーアップのみ（古いフィールド削除、意味変更 等）
- **後方互換**: 追加は原則OK（optional追加）、deprecate期間を設ける

## Contract test（必須）
- examplesを用いて
  - JSON Schema validation
  - OpenAPI validation
  - （可能なら）サンプルをサービスに投げてレスポンスがschemaを満たす

## コード生成（スクラッチ回避）
- OpenAPI → クライアントSDK生成（各サービス内に取り込む）
- JSON Schema → Pydanticモデル生成（各サービス内に取り込む）
- 生成物は **サービス内完結**（repo移動しても壊れない）

