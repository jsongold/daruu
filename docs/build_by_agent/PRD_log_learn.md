# PRD: Log/Learn Service（Evidence/Activity永続化＋テンプレ管理）

## 目的
Evidence/Activity/Template/Mappingの保存と版管理を担い、次回以降の精度と効率を上げる。

## 責務（Single writer）
- `Evidence` / `Activity` の永続化
- テンプレ（Field定義、Mapping、調整履歴）の版管理
- 参照API提供（特定フォームの既知テンプレを返す等）

## 入出力（Contract）
- **入力**: evidence[], activity[], templates（任意）
- **出力**: ids/refs, template_candidates（任意）

## API（案）
- `POST /log/evidence`
- `POST /log/activity`
- `GET /templates?fingerprint=...`
- `POST /templates`（新規/更新）

## 推奨ライブラリ
- **supabase-py**（Supabase API client）
- （必要なら）SQLAlchemy + Alembic（ローカル開発/マイグレーション管理用）

## 受け入れ基準（MVP）
- Evidence/Activityが検索可能に保存できる
- テンプレをfingerprint等で再利用できる

## 永続化先（Supabase）
- **DB**: Supabase Postgres（Evidence/Activity/Template/Mapping）
- **Storage**: Supabase Storage（PDF/プレビュー/切り出し画像/成果物）

