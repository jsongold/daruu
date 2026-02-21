# PRD: Adjust Service（座標補正）

## 目的
`Field` の bbox/描画パラメータを、アンカー相対・レイアウト差分・ReviewのIssueに基づいて補正し、枠内率と重なりゼロに収束させる。

## Service の性質

本Serviceは **決定論的なService** です（Agentを含みません）。
- 同じ入力→同じ出力
- 単体テスト可能
- LLM推論は使用しない

## 責務
- bbox補正案の生成（提案）。採用/確定はOrchestratorが決め、Activityに残す
- 折り返し/フォントサイズ/アライン等の描画パラメータ提案（必要時）

## 入出力（Contract）
- **入力**: fields[], issues[], page_meta, user_edits（任意）
- **出力**: field_patches[]（bbox/formatの差分）, confidence_updates（任意）

## API（案）
- `POST /adjust`（fields + issues → patches）

## 推奨ライブラリ
- shapely（bbox交差判定など。必要なら）
- numpy（計算）

## 受け入れ基準（MVP）
- Issue（はみ出し/重なり）を減らす方向のpatchを返せる
- 同入力で決定的なpatchを返す

