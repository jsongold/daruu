# Document Auto-Fill アーキテクチャ比較：As-Is vs To-Be

## 1. 現行アーキテクチャの要約（As-Is）

### 1.1 コンポーネント/モジュール一覧

| コンポーネント | 役割 | 入力 | 出力 | 責務境界 |
|---------------|------|------|------|----------|
| **Ingest** | PDF正規化・検証・メタ抽出・ページ描画 | PDF/画像 | 正規化済みDocument | 決定論 |
| **StructureLabellingService** | 構造検出＋ラベル-位置リンク | PDF, page_images | LinkedField[], Evidence[] | 決定論 orchestration + LLM agent |
| **FieldLabellingAgent** | ラベル→bboxの意味的リンク | labels, boxes, spatial_clusters | linkages, unlinked_boxes | **LLM** |
| **MappingService** | ソース→ターゲット対応 | source_fields, target_fields | MappingItem[], FollowupQuestion[] | 決定論 matching + LLM agent |
| **MappingAgent** | 曖昧マッピング解消・質問生成・一括推論 | candidates, fields | MappingItem, FollowupQuestion, BatchMappingOutput | **LLM** |
| **ExtractService** | 値抽出の調整 | document_ref, fields | ExtractResult, ValueCandidate[] | 決定論 native/OCR + LLM agent |
| **ValueExtractionAgent** | 候補解消・正規化・衝突検出・質問生成 | field, candidates | ValueCandidate, str, FollowupQuestion | **LLM** |
| **AdjustService** | 座標補正（アンカー相対） | fields, anchors | 補正済みbbox | 決定論 |
| **FillService** | PDF生成（AcroForm or overlay） | FillRequest | FillResult, render_report | 決定論 |
| **ReviewService** | 品質検証・issue検出・confidence | JobContext | issues, confidence | 決定論 |
| **VisionAutofillService** | フォーム単位で一括マッチング | VisionAutofillRequest | VisionAutofillResponse | **LLM** + rule-based fallback |
| **ConversationAgent** | v2 Agent Chat のステージ制御 | Message, attachments | AgentResponse | stub（LLM呼び出しなし） |
| **TextExtractionService** | データソースからのテキスト抽出 | DataSource | ExtractionResult | 決定論（key:value正規、CSV解析） |
| **Orchestrator / DecisionEngine** | パイプライン制御・分岐・ループ | JobContext | NextAction | 決定論 |

### 1.2 データフロー

```
[v1 Pipeline]
Upload → Ingest → StructureLabelling → Map → Extract → Adjust → Fill → Review
                    ↑ LLM               ↑ LLM   ↑ LLM
                    page単位            field単位 field単位
                    (label-link)        (map)    (resolve/normalize/conflict)

[v2 Agent Chat]
Upload → ConversationAgent (stub) → ステージ遷移のみ
         VisionAutofillService は 直接API / PromptingPage から呼び出し
         DataSource → TextExtractionService → VisionAutofillService (1回LLM)
```

### 1.3 LLM呼び出し点

| 呼び出し点 | 粒度 | 入力 | 回数（1フォーム想定） |
|------------|------|------|------------------------|
| FieldLabellingAgent.link_labels_to_boxes | **ページ単位** | labels, boxes, spatial_clusters | ページ数 N |
| MappingAgent.resolve_mapping | **フィールド単位** | source_field, candidates | 曖昧フィールド数 M |
| MappingAgent.generate_question | フィールド単位 | source_field, candidates | ask時のみ |
| MappingAgent.infer_mappings_batch | **フォーム単位** | source_fields, target_fields | 1回（batch時） |
| ValueExtractionAgent.resolve_candidates | フィールド単位 | field, candidates | 複数候補時 |
| ValueExtractionAgent.normalize_value | フィールド単位 | field, value | 正規化が必要なフィールド数 |
| ValueExtractionAgent.detect_conflicts | フィールド単位 | field, candidates | 候補衝突時 |
| ValueExtractionAgent.generate_question | フィールド単位 | field, reason | ask時のみ |
| **VisionAutofillService._llm_autofill** | **フォーム単位** | fields, extractions, rules | **1回** |

### 1.4 決定論ロジック

- **フォーム解析**: StructureDetector（box/table/text region）は決定論。Label-to-box は LLM or fallback proximity。
- **検証**: FillService で overlap/overflow/truncation を決定論検出。required/format は Review に一部あり。
- **描画**: FillService は完全に決定論（AcroForm / overlay）。
- **候補生成**: Mapping は StringMatcher（RapidFuzz）で候補生成。Extract は native/OCR で候補生成。VisionAutofill は TextExtractionService で key:value 抽出。
- **ルール適用**: VisionAutofill では `rules` をプロンプトに埋め込むのみ。構造化ルールの適用はなし。

---

## 2. 新アーキテクチャとのマッピング（As-Is → To-Be対応表）

| 既存モジュール/関数 | 対応する新サービス | 現状の責務 | To-Beでの責務 | 差分 | 方針 |
|-------------------|-------------------|------------|---------------|------|------|
| Ingest | Compiler | PDF正規化・メタ抽出 | FormSpec + 正規化入力 + provenance | ほぼ同等 | そのまま Compiler の一部に |
| StructureDetector | Compiler | box/table/label候補検出 | label候補・制約の抽出 | 同等 | Compiler に内包 |
| FieldLabellingAgent | Decision | ラベル→bboxリンク | canonical_key / fill|skip の一部 | ページ単位→フォーム単位に統合 | 1回LLMに統合 |
| TextExtractionService | Compiler | データソース抽出 | 正規化済み入力データ | 同等 | Compiler に内包 |
| TextExtractionService.extract_from_text | Compiler | key:value抽出 | 同上 | 決定論のまま強化 | そのまま |
| MappingService + MappingAgent | Compiler + Decision | 候補生成（決定論）+ LLM解消 | Compiler: 候補生成 / Decision: 一括決定 | 複数回LLM→1回に | 候補はCompiler、決定はDecision |
| ExtractService + ValueExtractionAgent | Compiler + Decision | 抽出 + LLM正規化/解消 | Compiler: 抽出・正規化 / Decision: fill|skip | 複数回LLM→1回に | 正規化はCompiler、決定はDecision |
| VisionAutofillService | Decision + Executor | 1回LLMで一括マッチ | Decision: SemanticPlan出力 / Executor: 描画 | 近い | モデルを SemanticPlan に拡張 |
| FillService | Executor | 描画・検証 | 完成PDF + render_report | ほぼ同等 | Executor にそのまま |
| ReviewService | Executor | 検証・confidence | validation_result | 同等 | Executor に統合 |
| AdjustService | Executor | 座標補正 | 描画前の補正 | 同等 | Executor に統合 |
| DecisionEngine | - | パイプライン分岐 | 不要（Compiler→1回LLM→Executor） | 過剰 | 廃止または簡素化 |
| ConversationAgent | - | ステージ制御（stub） | 新UIの制御 | stubのまま | 新フローに合わせて再実装 |
| ルール（rules） | Compiler | プロンプトに埋め込むだけ | 構造化・制約抽出 | 不足 | Compiler でルール構造化 |
| EditService / EditRepository | Learning | 編集適用 | 差分収集・資産化 | 不足 | Learning Adapter で拡張 |

---

## 3. ギャップ分析（過不足の洗い出し）

### Missing（必要だが存在しない）

- **SemanticContextBundle**: FormSpec + label候補 + 制約 + ルールテキスト + 正規化済み入力 + provenance の統合構造がない。
- **SemanticPlan**: canonical_key / fill|skip|ask_user / source / formatter / confidence / rule_trace の出力フォーマットがない。
- **ルールの構造化**: 記載ルール（rules）は文字列リストのまま。構造化・適用ロジックがない。
- **ユーザー修正差分の収集/資産化**: Edit は適用のみ。Learning Adapter 用の導線がない。
- **フィールドクラスタリング**: トークン圧縮のためのクラスタリングがない。
- **候補キーの絞り込み（3〜7）**: 現状は全候補をLLMに渡している。

### Excess（存在するが新設計では不要/縮小）

- **複数のLLM呼び出し点**: FieldLabelling, Mapping, Extract の多点呼び出しは 1回LLM に統合するため縮小。
- **DecisionEngine の複雑な分岐**: 新設計では Compiler→1回LLM→Executor の直列のため、大幅簡素化。
- **Orchestrator のループ制御**: 改善率や max_iterations による再試行は、1回LLM体制では別設計が必要。

### Ambiguous（境界が曖昧で分割が必要）

- **正規化の担当**: 日付・電話番号などの正規化が ValueExtractionAgent と TextExtractionService に分散。Compiler に集約すべき。
- **候補生成の境界**: Mapping の候補は RapidFuzz、Extract の候補は native/OCR。両方を Compiler で統合する設計が必要。
- **ルール適用の場所**: 現状は LLM プロンプト内のみ。Compiler で制約抽出し、Decision に渡す境界が不明。

### Unknown（仕様不確定/判断保留）

- **過去申告書の扱い**: 現状の DataSource に「過去申告書」としての役割・優先度があるか不明。
- **provenance の形式**: Evidence はあるが、SemanticContextBundle の provenance 形式との対応が未定義。
- **ask_user の導線**: 現状は FollowupQuestion で「ask」を表現。新設計の ask_user との対応方法が未定。

### 重点チェック結果

| 項目 | 状態 |
|------|------|
| SemanticContextBundle | **存在しない** |
| SemanticPlan | **存在しない**（VisionAutofillResponse は類似だが source/confidence のみ） |
| ルールの構造化・適用 | **LLMプロンプトに埋め込むのみ**。構造化なし |
| マッピングがLLM任せ | **部分的**。Mapping は候補生成後にLLM、Extract も同様。VisionAutofill は一括LLM |
| 候補生成の決定論化 | **一部あり**。Mapping: RapidFuzz、Extract: native/OCR。VisionAutofill: key:value正規 |
| 検証の決定論 | **一部あり**。Fill で overlap/overflow。required/format は限定的 |
| ユーザー修正差分の収集/資産化 | **導線なし** |

---

## 4. LLM呼び出し削減の設計案（To-Beの具体案）

### 4.1 現行のLLM呼び出し点と統合方針

| 現行呼び出し | 1回LLM統合時の Decision の役割 | Compiler の前処理 | Executor の決定論 |
|-------------|--------------------------------|-------------------|-------------------|
| FieldLabellingAgent | ラベル→bbox のリンクを SemanticPlan に含める | 候補（label/box）のクラスタ化・絞り込み | 描画座標の適用のみ |
| MappingAgent | ソース→ターゲットの対応を一括決定 | 候補キーを3〜7に絞り込み | - |
| ValueExtractionAgent | 正規化・衝突解消・fill|skip を一括決定 | 正規化を可能な限り決定論化 | 検証・再試行 |
| VisionAutofillService | **既に1回LLM**。SemanticPlan 形式に拡張 | Bundle の組立・圧縮 | 描画・検証 |

### 4.2 Compiler 側で前処理すべき内容

- **候補生成**: 全候補を決定論で生成（RapidFuzz, native/OCR, key:value）。
- **制約抽出**: ルールドキュメントから制約を抽出（日付形式、必須、最大長など）。
- **OCR**: 既存の OCR はそのまま Compiler の入力として利用。
- **過去申告書抽出**: DataSource からの抽出結果を正規化して Bundle に含める。
- **正規化**: 日付・電話番号・郵便番号など、パターンが明確なものは Compiler で決定論正規化。
- **候補キー絞り込み**: フィールドあたり 3〜7 候補に限定。

### 4.3 Executor 側で決定論に固定すべき内容

- **描画**: FillService と同等。AcroForm / overlay。
- **検証**: required / format / overflow を決定論でチェック。
- **再試行**: 検証失敗時の再描画は決定論ロジック（フォント縮小、改行など）。

### 4.4 Bundle の圧縮戦略

- **フィールドのクラスタリング**: セクション単位でグループ化し、セクションごとに LLM に入力するオプションを検討（フォーム単位1回を維持する場合もあり）。
- **候補キーの絞り込み**: フィールドあたり 3〜7 に制限。RapidFuzz スコア順で上位を採用。
- **ルールテキストの要約**: 長いルールは要約して渡す。要約は **事前バッチ処理** で別LLM呼び出しとし、ランタイムの 1回LLM には含めない。
- **正規化済み入力**: 生データではなく、正規化済みの key-value のみを渡す。

---

## 5. 移行計画（段階的リファクタリング）

### Phase 0: 計測の追加

- **対象**: `app/agents/llm_wrapper.py`, `app/models/cost.py`, 各 Agent の `_invoke_llm`
- **やること**: LLM呼び出し回数/コスト/遅延、エラー分類のログ・メトリクス追加
- **受け入れ基準**: フォーム1件あたりの LLM 呼び出し回数・トークン数が追跡可能
- **リスク**: 低。ログ追加のみ
- **ロールバック**: 計測コードの削除

### Phase 1: Compiler の導入

- **対象**: `app/services/text_extraction_service.py`, `app/services/vision_autofill/service.py` の前処理部分
- **やること**: SemanticContextBundle のデータ構造を定義し、TextExtraction + 候補生成 + ルールテキストを組み立てる Compiler モジュールを新設
- **受け入れ基準**: 既存 VisionAutofill と同じ入力から Bundle が生成できる
- **リスク**: 中。既存フローを壊さないように差し込み
- **ロールバック**: Compiler を未使用にし、既存パスに戻す

### Phase 2: SemanticPlan の導入

- **対象**: `app/services/vision_autofill/models.py`, `prompts.py`
- **やること**: FilledField を SemanticPlan 形式（canonical_key, fill|skip|ask_user, source, formatter, confidence, rule_trace）に拡張
- **受け入れ基準**: VisionAutofill の LLM 出力が SemanticPlan 形式でパース可能
- **リスク**:  Low。出力スキーマの拡張
- **ロールバック**: 従来形式のパースにフォールバック

### Phase 3: 1回LLMへの統合

- **対象**: `FieldLabellingAgent`, `MappingAgent`, `ValueExtractionAgent`, `VisionAutofillService`
- **やること**: v1 Pipeline の多用 LLM を廃止し、Compiler が生成した Bundle を 1回の Decision LLM に渡す新フローを導入
- **受け入れ基準**: 1フォームあたり LLM 呼び出しが 1回、既存テストが通る
- **リスク**: 高。複数 Agent の統合、品質維持が課題
- **ロールバック**: 既存パイプラインを feature flag で切り替え可能にしておく

### Phase 4: Learning Adapter の分離（オプション）

- **対象**: `app/services/edit/`, `app/repositories/edit_repository.py`
- **やること**: ユーザー修正差分を収集し、分類・資産化する Adapter を分離
- **受け入れ基準**: 修正差分が保存され、後続分析で利用可能
- **リスク**: 低。既存 Edit の拡張
- **ロールバック**: Adapter を無効化

---

## 6. 追加の確認事項（不足情報リスト）

1. v1 Pipeline（Job）と v2 Agent Chat のどちらを主軸とするか？両方維持するか？
2. VisionAutofill は Agent Chat の FILLING ステージから呼ばれる想定か？現状は呼ばれていない。
3. 過去申告書は DataSource の一種として扱うか、別エンティティか？
4. ルールドキュメントの入力形式は？PDF、Markdown、構造化JSON のいずれか？
5. 1回LLM に統合した場合、フィールド数が極端に多い（100以上）フォームの分割方針は？
6. prompt_attempts と Learning Adapter の関係は？プロンプトチューニングとユーザー修正は別軸か？
7. 計算機能は不要とのことだが、現状の FillService に計算ロジックは含まれているか？（含まれていなければ変更不要）
