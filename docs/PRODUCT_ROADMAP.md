# PDF Form Autofill — Product Roadmap

## Vision

ドキュメントと必要情報を入れたら、正しい位置に正しい情報が入った完成PDFを出力する。
未知のドキュメントにも高速・高精度で対応し、使うほど賢くなるシステム。

---

## Phase 1: FieldMapping精度向上 ← 現在地

### 目的
AcroFormフィールド（Text1, Text2...）が何を意味するかを正確に識別する。
現状30%精度 / 70秒 → 目標85-95%精度 / <10秒。

### 実装ステップ

```
Step 0: 候補絞り込み + プロンプト改善 + ベンチマーク
        → ANNOTATION_AGENT_SPEC.md で定義済み
        → candidate_filter.py, prompts_v2.py, benchmark.py

Step 1: Template Fingerprint
        → AcroForm構造hash → Supabase lookup
        → 既知テンプレートは$0、<1sで処理

Step 2: SpatialScorer
        → 多特徴量ロジスティック回帰（LLMなし）
        → 30% → 55-70%

Step 3: LLMカスケード（Gemini Flash → Claude Sonnet）
        → 未確定フィールドのみLLMで解決

Step 4: Iterative Annotation Loop
        → LLM推論 → 人間部分修正 → LLM再推論 → repeat
        → 確認済みペアがfew-shotとして蓄積
        → 2-3ラウンドで95%+達成

Step 5: Annotationカバレッジ拡大
        → 年末調整以外のフォーム（確定申告、扶養控除等）
        → テンプレートライブラリ構築
```

### 成果物
- 高精度なsemantic field map（{Text3: applicant_name, ...}）
- テンプレート別の確認済みAnnotationペアデータベース
- 未知フォームへの対応力（few-shot転用）

### 技術基盤（リサーチから）
- IVB座標エンコーディング（CVPR 2024）
- 候補絞り込み（770→7ラベル/フィールド）
- Many-shot ICL（NeurIPS 2024）
- 日本語帳票の方向補正係数
- Prompt Caching（Anthropic 90%割引 / OpenAI 75%割引）

---

## Phase 2: DocumentRules

### 目的
フォームに記載されたルール（記入条件、基準日、対象者等）を理解し、
正しい値を正しい条件で入力する。

### 問題の例

```
FieldMappingだけでは解決しない問題:

1. 「氏名」欄が2つある
   → 1つは本人、1つは世帯主。どちらにどの名前を入れるか？
   → ルール: 「世帯主の氏名を記入してください」

2. 「住所」欄
   → 現住所？住民票の住所？令和X年1月1日時点の住所？
   → ルール: 「令和6年1月1日現在の住所を記入」

3. 「配偶者控除」セクション
   → 配偶者がいない場合は記入不要
   → ルール: 条件分岐（配偶者の有無、所得制限）

4. 金額計算
   → 給与所得控除後の金額 = 給与収入 - 控除額
   → ルール: 国税庁の計算式に基づく
```

### ルール取得の2アプローチ

```
A) 自動抽出（LLM）
   - PDFの注記・小文字テキスト・欄外説明をLLMで解析
   - 「この欄は〜の場合に記入」「〜時点の情報を記入」等のパターン認識
   - FieldMappingのテキストブロックデータを再利用可能

B) ユーザーへの質問（Q&A）
   - ルールから導かれる質問を自動生成
   - 「配偶者はいますか？」「世帯主はあなたですか？」
   - 回答に基づいて条件分岐し、必要フィールドのみ入力
```

### DocumentRules Annotation
- FieldMapping同様、同じテンプレートのルールは全ユーザー共通
- 一度ルールを抽出・確認すれば、テンプレートキャッシュとして再利用
- ルールの構造: {field_id, condition, rule_text, question_for_user}

### 依存関係
- Phase 1のFieldMappingが前提（どのフィールドにどのルールが適用されるか）
- Phase 1のAnnotationインフラ（Supabase、テンプレートキャッシュ）を再利用

---

## Phase 3: PII対応

### 目的
個人情報（氏名、住所、マイナンバー、給与等）を安全に扱う。

### 対応範囲

```
1. データ分類
   - フィールドのsemantic_keyからPIIレベルを自動判定
   - Level 1: 氏名、住所、生年月日（個人情報）
   - Level 2: マイナンバー、口座番号（特定個人情報 / 金融情報）
   - Level 3: 給与、控除額（機微情報）

2. 処理時の保護
   - LLM API送信時のPIIマスキング / トークン化
   - 処理後の復元
   - マスキング方式: 可逆暗号化 or プレースホルダー置換

3. 保存時の保護
   - Supabaseでの暗号化（at-rest encryption）
   - PIIフィールドのカラムレベル暗号化
   - アクセスログ / 監査証跡

4. アクセス制御
   - ユーザー単位のデータ分離
   - API keyスコープによる権限制御
   - データ保持期間の設定（処理完了後X日で自動削除）
```

### Phase 1との関係
- Phase 1のsemantic_key（applicant_name, tax_amount等）がPII分類の入力
- PII対応はPhase 2と並行実装可能（直交する関心事）

---

## Phase 4: ドキュメントキャリブレーション（RAG）

### 目的
同じフォームの年度違い・版違い（レイアウトの微差）を吸収し、
既存Annotationを新バージョンに自動転用する。

### 問題

```
2024年版 年末調整 → hash_level2 = "abc123"（Annotation完備）
2025年版 年末調整 → hash_level2 = "def456"（未登録）

差異:
- 「配偶者特別控除」欄が5mm右にずれた
- 「基礎控除」の説明文が更新された
- 新しいフィールドが1つ追加された
- 2つのフィールドが統合された

→ 完全一致hashではヒットしないが、90%+のフィールドは同じ
```

### 技術アプローチ

```
1. ColPali / ColQwen2（視覚的文書埋め込み）
   - ページ画像をベクトル化
   - 類似テンプレート検索（コサイン類似度）
   - 0.39秒/page（リサーチ#6）

2. 差分検出 + 転用
   - 類似テンプレートのAnnotationを転用
   - フィールド位置の差分を自動補正
   - 新規/変更フィールドのみ人間確認

3. バージョン管理
   - テンプレートの親子関係（2024版 → 2025版）
   - 差分のみを保存（ストレージ効率）
   - ルール（Phase 2）の継承と差分管理
```

### 依存関係
- Phase 1のAnnotationデータが検索対象コーパス
- Phase 2のDocumentRulesも版違いで差分管理

---

## Phase 5: ドキュメントカバレッジ拡大

### 目的
対応フォーム数を拡大し、未知のドキュメントへの初回対応速度と精度を高める。

### アプローチ

```
1. バックグラウンド学習パイプライン
   - 公開されている政府フォーム（国税庁、年金機構、ハローワーク等）を
     自動収集 → FieldMapping → ルール抽出 → テンプレートDB登録
   - 人間の確認はバッチで効率化（Active Learning: 不確実なもの優先）

2. 未知ドキュメント対応の高速化
   - Phase 4のRAGで類似テンプレートを検索
   - 類似テンプレートのAnnotation + Rulesをfew-shotとして活用
   - 初回でも70-80%の精度を達成（類似テンプレートの転用効果）

3. カバレッジメトリクス
   - 対応テンプレート数
   - テンプレートあたりの平均Annotation精度
   - 未知ドキュメントの初回精度
   - 人間介入が必要なフィールド数の推移

4. ドキュメントカテゴリ拡大ロードマップ
   - Tier 1: 年末調整関連（扶養控除、保険料控除、配偶者控除）
   - Tier 2: 確定申告（青色申告、白色申告、医療費控除）
   - Tier 3: 社会保険（健康保険、厚生年金）
   - Tier 4: 企業固有フォーム（入社手続き、人事異動届）
   - Tier 5: 汎用フォーム（契約書、申請書）
```

### 依存関係
- Phase 1-4の全インフラが前提
- Phase 1のAnnotation品質がカバレッジ拡大の速度を決定

---

## Phase 6: 自前モデル開発（条件付き）

### トリガー条件
以下のいずれかが満たされた場合に検討開始:

```
コスト:     月間API費用 > $5,000（現在のGemini Flash利用で$3-15/月程度）
速度:       <1秒/フォームが必要（リアルタイムUI、バッチ大量処理）
セキュリティ: PII外部API送信が不可（金融機関、官公庁のオンプレ要件）
エンプラ:    SLA 99.9%+、専用インフラ、カスタマイズ要件
```

### アプローチ候補

```
1. LiLT fine-tuning（MIT license）
   - LayoutLMv3のライセンス問題を回避
   - Phase 1-5のAnnotationデータでfine-tuning
   - 必要データ: 200+テンプレート × 各50+確認済みペア
   - 推定コスト: A100 1台で数時間の訓練

2. Donut fine-tuning（MIT license）
   - OCR不要、日本語SynthDoG事前学習済み
   - T4 GPUで75分の訓練（リサーチ#3）
   - FieldMapping + FieldRendering一体型モデル

3. Distillation（大→小モデルの知識蒸留）
   - Claude Opus / GPT-5の出力をteacher dataとして
   - 8B-13Bクラスの小型モデルにfine-tuning
   - 推論コスト1/100、レイテンシ1/10
   - Qwen2.5-VL-7B等が候補

4. ハイブリッド
   - FieldMapping: 自前fine-tunedモデル（高速・低コスト）
   - DocumentRules: LLM API（複雑な推論が必要）
   - FieldRendering: 自前モデル（パターン学習済み）
```

### Phase 1-5のデータが学習資産になる

```
Phase 1 Annotation pairs      → FieldMappingモデルの訓練データ
Phase 2 Document rules         → ルール推論モデルの訓練データ
Phase 4 Template variations    → キャリブレーション頑健性の訓練データ
Phase 5 Background learning    → 大規模コーパス（数千テンプレート）
```

---

## 戦略的な堀（Strategic Moat）

```
Annotationデータが複利で効く:

1テンプレート目:   全フィールド手動確認（コスト高）
10テンプレート目:  few-shot転用で50%自動化
100テンプレート目: RAG + テンプレート類似検索で80%自動化
1000テンプレート目: 自前モデル訓練可能、95%+自動化

競合が同じ精度を達成するには、同じ量のAnnotationデータが必要。
先にデータを蓄積した側が、コスト・速度の両面で圧倒的優位を持つ。

Phase 1で蓄積するAnnotationデータは:
- Phase 2のルール抽出の学習データ
- Phase 4のRAG検索対象コーパス
- Phase 5のカバレッジ拡大の基盤
- Phase 6の自前モデルの訓練データ

全てのフェーズが同じデータ資産の上に構築される。
だからPhase 1の品質が全体を決める。
```

---

## 現在の状態と次のアクション

```
現在地: Phase 1, Step 0
成果物: ANNOTATION_AGENT_SPEC.md（Claude Code実装仕様書）

次のアクション:
1. ANNOTATION_AGENT_SPEC.md → Claude Code で実装
2. ベンチマーク実行（5パターン比較）
3. 結果に基づきIterative Loop実装判断
4. テンプレートライブラリ構築開始
```
