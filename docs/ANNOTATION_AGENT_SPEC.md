# AnnotationAgent 実装仕様書
# Phase 0: 候補絞り込み + プロンプト改善 + ベンチマーク

## 目的

PDF form autofill パイプラインのFIELD_IDENTIFICATION ステップ（現在70秒+、精度30%）を、
プロンプト改善と前処理追加により **10秒以下、精度60-75%** に引き上げる。
既存パイプラインへの差し込みと、将来のAnnotation蓄積型Iterative Loopへの拡張を見据えた設計とする。

---

## 背景・制約

### 既存システム構成

```
apps/api/app/services/vision_autofill/
├── prompts.py          # 現行プロンプト定義（FIELD_IDENTIFICATION, AUTOFILL, REFILL）
├── ...（他のサービスファイル）
```

### 現行FIELD_IDENTIFICATIONの問題点

1. **候補絞り込みなし**: 189フィールド + 770テキストブロックを全件LLMに投入
2. **座標が生ピクセル値**: ページサイズ不明のためスケール感がLLMに伝わらない
3. **reasoning出力を要求**: 189フィールド × 平均30トークン ≈ 5,670トークンが推論説明だけに浪費
4. **1リクエストで全フィールド処理**: タイムアウト・出力切れリスク
5. **低confidenceフィールドを省略**: デバッグ不能

### 入力データ形式（現行、変更不可）

```python
# フィールド（AcroFormから取得済み）
field = {
    "id": "Text1",          # フィールドID（意味のない名前）
    "t": "text",            # type: text, checkbox, radio, choice, button
    "p": 1,                 # ページ番号（1-indexed）
    "b": [120, 80, 150, 20] # [x, y, width, height] PDF座標（ポイント単位）
}
# オプショナルで "l" (label) キーが存在する場合がある（idと異なる場合のみ）

# テキストブロック（PDF上の可視テキスト）
text_block = {
    "s": "氏名",            # テキスト内容
    "p": 1,                 # ページ番号
    "b": [60, 78, 50, 15]   # [x, y, width, height] PDF座標（ポイント単位）
}
```

### PDF座標系

- 原点: 左下（PDFデフォルト）ただし既存コードで左上原点に変換済みの可能性あり
- 単位: ポイント（1pt = 1/72 inch）
- 典型的なページサイズ: A4 = 595 x 842pt, Letter = 612 x 792pt
- **ページサイズはフィールド/テキストブロックのデータには含まれていない**
  → bboxの最大値から推定するか、PDF metadataから取得する必要がある

---

## 成果物一覧

以下の3ファイルを `apps/api/app/services/vision_autofill/` 配下に作成する。

```
apps/api/app/services/vision_autofill/
├── prompts.py              # 既存（変更しない）
├── candidate_filter.py     # [新規] 候補絞り込み + IVB座標変換
├── prompts_v2.py           # [新規] 改善プロンプト定義
└── benchmark.py            # [新規] v1 vs v2 比較テストスクリプト
```

---

## ファイル1: `candidate_filter.py`

### 責務

1. ページサイズ推定
2. PDF座標 → IVB (0-999) 正規化
3. フィールドごとに近傍テキストブロックを top-K に絞り込み
4. 結果を構造化して返却

### 公開インターフェース

```python
from dataclasses import dataclass

@dataclass
class CandidateLabel:
    """フィールドに対する候補ラベル"""
    text: str                    # テキスト内容
    bbox_ivb: tuple[int, int, int, int]  # IVB座標 [x1, y1, x2, y2]
    distance_score: float        # 距離スコア（小さいほど近い）
    direction: str               # "left", "above", "right", "below", "overlap"

@dataclass 
class FieldWithCandidates:
    """候補ラベル付きフィールド"""
    field_id: str
    field_type: str              # "text", "checkbox", etc.
    page: int
    bbox_ivb: tuple[int, int, int, int]  # IVB座標
    candidates: list[CandidateLabel]

def filter_candidates(
    fields: list[dict],          # 現行フォーマットのフィールドリスト
    text_blocks: list[dict],     # 現行フォーマットのテキストブロックリスト
    top_k: int = 7,
    page_sizes: dict[int, tuple[float, float]] | None = None,
        # {page_number: (width, height)} 省略時は自動推定
) -> list[FieldWithCandidates]:
    """
    各フィールドに対して近傍テキストブロックをtop_kに絞り込み、
    IVB座標に変換して返却する。
    """
    ...
```

### ページサイズ推定ロジック

```python
def estimate_page_sizes(
    fields: list[dict],
    text_blocks: list[dict],
) -> dict[int, tuple[float, float]]:
    """
    フィールドとテキストブロックのbbox最大値からページサイズを推定する。
    
    ロジック:
    1. ページごとに全bboxの右端(x+w)と下端(y+h)の最大値を算出
    2. 既知のページサイズ（A4: 595x842, Letter: 612x792, A3: 842x1191, Legal: 612x1008）
       から最も近いものを選択
    3. 最大値が既知サイズの95%以上であれば、その既知サイズを採用
    4. それ以外は最大値に10%マージンを追加して使用
    
    戻り値: {page_number: (width_pt, height_pt)}
    """
```

### IVB変換

```python
def to_ivb(
    bbox: list[float],  # [x, y, w, h] PDF座標
    page_width: float,
    page_height: float,
) -> tuple[int, int, int, int]:
    """
    PDF座標 → IVB (0-999) に変換
    
    入力: [x, y, width, height] （左上原点、ポイント単位）
    出力: (x1, y1, x2, y2) （左上原点、0-999正規化）
    
    計算:
      x1 = clamp(int(x / page_width * 999), 0, 999)
      y1 = clamp(int(y / page_height * 999), 0, 999)
      x2 = clamp(int((x + width) / page_width * 999), 0, 999)
      y2 = clamp(int((y + height) / page_height * 999), 0, 999)
    """
```

### 距離スコア計算

```python
def compute_distance_score(
    field_bbox: list[float],     # [x, y, w, h]
    label_bbox: list[float],     # [x, y, w, h]
) -> tuple[float, str]:
    """
    フィールドとラベルの空間的距離を計算し、方向を判定する。
    
    戻り値: (score, direction)
    - score: 0.0（完全一致/重なり）~ 大きいほど遠い
    - direction: "left" | "above" | "right" | "below" | "overlap"
    
    スコア計算ロジック:
    1. ラベル中心とフィールド中心を算出
    2. 基本距離 = ユークリッド距離（中心間）
    3. 方向補正:
       - ラベルがフィールドの左にある → ×0.8（日本語帳票で最も一般的）
       - ラベルがフィールドの上にある → ×0.9（次に一般的）
       - ラベルがフィールドの右にある → ×2.0（稀、ペナルティ）
       - ラベルがフィールドの下にある → ×1.5（やや稀）
       - 重なっている → ×0.5（ラベルとフィールドが重なるケース）
    4. 垂直アライメントボーナス:
       - ラベルとフィールドのy座標中心差が高さの50%以内 → ×0.7
         （同じ行にあることを示す強い手がかり）
    
    方向判定:
    - dx = field_center_x - label_center_x
    - dy = field_center_y - label_center_y
    - |dx| > |dy| の場合: dx > 0 → "left", dx < 0 → "right"
    - |dy| >= |dx| の場合: dy > 0 → "above", dy < 0 → "below"
    - bboxが重なっている場合: "overlap"
    """
```

### 絞り込みフロー

```python
def filter_candidates(...) -> list[FieldWithCandidates]:
    """
    処理フロー:
    1. page_sizes が未指定なら estimate_page_sizes() で推定
    2. フィールドをページごとにグループ化
    3. テキストブロックをページごとにグループ化
    4. 各フィールドに対して:
       a. 同一ページのテキストブロックのみを対象
       b. 全テキストブロックに対して compute_distance_score() を実行
       c. score昇順でソートし、top_k件を採択
       d. bbox を to_ivb() で変換
       e. FieldWithCandidates を構成
    5. 全フィールドの FieldWithCandidates リストを返却
    """
```

### テスト要件

```python
# test_candidate_filter.py に以下のテストを含めること

def test_to_ivb_basic():
    """A4サイズ(595x842)での基本変換"""
    assert to_ivb([0, 0, 595, 842], 595, 842) == (0, 0, 999, 999)
    assert to_ivb([297.5, 421, 0, 0], 595, 842) == (499, 499, 499, 499)

def test_to_ivb_clamp():
    """はみ出し座標のクランプ"""
    assert to_ivb([-10, -10, 605, 852], 595, 842)[0] == 0  # 負の値は0にクランプ

def test_direction_left():
    """ラベルがフィールドの左にある場合"""
    score, direction = compute_distance_score(
        [200, 100, 150, 20],   # field
        [50, 100, 100, 15],    # label (左にある)
    )
    assert direction == "left"

def test_direction_above():
    """ラベルがフィールドの上にある場合"""
    score, direction = compute_distance_score(
        [100, 200, 150, 20],   # field
        [100, 160, 100, 15],   # label (上にある)
    )
    assert direction == "above"

def test_vertical_alignment_bonus():
    """同じ行にあるラベルが優先される"""
    score_aligned, _ = compute_distance_score(
        [200, 100, 150, 20],   # field
        [50, 102, 100, 15],    # label (ほぼ同じy座標)
    )
    score_offset, _ = compute_distance_score(
        [200, 100, 150, 20],   # field
        [50, 60, 100, 15],     # label (y座標がずれている)
    )
    assert score_aligned < score_offset  # aligned の方がスコアが低い（=近い）

def test_filter_returns_correct_count():
    """top_k=5の場合、最大5件の候補が返る"""
    fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
    blocks = [
        {"s": f"label{i}", "p": 1, "b": [50 + i*20, 100, 40, 15]}
        for i in range(20)
    ]
    result = filter_candidates(fields, blocks, top_k=5)
    assert len(result) == 1
    assert len(result[0].candidates) == 5

def test_filter_same_page_only():
    """異なるページのテキストブロックは候補に含まれない"""
    fields = [{"id": "Text1", "t": "text", "p": 1, "b": [200, 100, 150, 20]}]
    blocks = [
        {"s": "同ページ", "p": 1, "b": [50, 100, 60, 15]},
        {"s": "別ページ", "p": 2, "b": [50, 100, 60, 15]},
    ]
    result = filter_candidates(fields, blocks, top_k=5)
    assert len(result[0].candidates) == 1
    assert result[0].candidates[0].text == "同ページ"

def test_estimate_page_sizes_a4():
    """A4サイズの推定"""
    fields = [{"id": "Text1", "t": "text", "p": 1, "b": [500, 800, 80, 20]}]
    blocks = [{"s": "test", "p": 1, "b": [10, 10, 50, 15]}]
    sizes = estimate_page_sizes(fields, blocks)
    assert sizes[1] == (595, 842)  # A4
```

---

## ファイル2: `prompts_v2.py`

### 責務

1. 改善されたFIELD_IDENTIFICATIONプロンプトを定義
2. FieldWithCandidates からコンパクトなプロンプト文字列を構築
3. LLMレスポンスをパースしてAnnotationPair相当の構造に変換
4. 将来のfew-shot例挿入に対応した設計

### 定数

```python
FIELD_IDENTIFICATION_SYSTEM_V2 = """You are a Japanese PDF form field identification expert.
Your task: match each form field to its most relevant text label from the provided candidates.

## Coordinate system
- Integer-Valued Binning: 0-999 grid, origin at top-left
- [x1, y1, x2, y2] where (x1,y1) = top-left corner, (x2,y2) = bottom-right corner

## Japanese form layout patterns
- Labels are typically LEFT of or ABOVE their field
- Dense forms may have labels INSIDE or OVERLAPPING the field area
- Common label patterns: 氏名, フリガナ, 住所, 生年月日, 電話番号, etc.
- Checkbox labels may be to the RIGHT of the checkbox

## Output format
Return ONLY a JSON array. No markdown, no explanation, no code fences.
Each element:
{"field_id":"Text1","label":"法人名","semantic_key":"company_name","confidence":85}

## Fields
- field_id: exact field ID from input
- label: matched text (exact string from candidates), or null if no match
- semantic_key: English snake_case key describing the field's purpose
  Examples: applicant_name, date_of_birth, postal_code, phone_number,
  company_name, department, employee_number, address_line1, ward_city,
  prefecture, salary_amount, tax_amount, insurance_premium,
  dependent_name, dependent_relationship, dependent_dob
- confidence: 0-100 integer
  - 90-100: label is directly adjacent and semantically clear
  - 70-89: label is nearby and contextually appropriate
  - 50-69: reasonable inference from position and context
  - 30-49: weak match, likely but uncertain
  - 0-29: no suitable match found (set label to null)

## Rules
- Process ALL fields. Never skip a field.
- For each field, return exactly one result (best match or null).
- Consider direction: left/above labels have higher prior probability.
- Use vertical alignment as strong signal: same y-center = likely same row.
- If candidate labels contain numbers or single characters, they may be
  sub-labels or section markers — prefer longer descriptive text."""
```

### few-shot挿入スロット

```python
def build_few_shot_section(confirmed_pairs: list[dict] | None) -> str:
    """
    確認済みAnnotationペアからfew-shot例セクションを構築する。
    
    引数:
      confirmed_pairs: 確認済みペアのリスト。各要素は:
        {
          "field_id": "Text3",
          "label": "氏名",
          "semantic_key": "applicant_name",
          "field_bbox_ivb": [200, 148, 450, 172],
          "label_bbox_ivb": [120, 150, 180, 170],
          "confidence": 95
        }
      None or 空リストの場合はセクション自体を省略。
    
    戻り値: プロンプトに挿入する文字列。例:
    
    ## Confirmed mappings for this form template (use as reference)
    - "氏名" [120,150,180,170] → Text3 [200,148,450,172] = applicant_name (95)
    - "住所" [120,200,180,220] → Text5 [200,198,650,222] = address_line1 (92)
    
    confirmed_pairsが空/Noneの場合は空文字列を返す。
    """
```

### ユーザープロンプト構築

```python
def build_field_identification_prompt(
    fields_with_candidates: list,  # FieldWithCandidates のリスト
    confirmed_pairs: list[dict] | None = None,
) -> tuple[str, str]:
    """
    FIELD_IDENTIFICATION用のsystem promptとuser promptを構築する。
    
    戻り値: (system_prompt, user_prompt)
    
    system_prompt構成:
      FIELD_IDENTIFICATION_SYSTEM_V2
      + build_few_shot_section(confirmed_pairs)  # あれば
    
    user_prompt構成:
      "Match each field to its best candidate label.\n\n"
      + ページごとにグループ化した以下のフォーマット:
    
      --- Page 1 ---
      Text1 [200,148,450,172] type=text
        candidates: "氏名"[120,150,180,170] left | "フリガナ"[120,180,200,198] above | ...
      Text2 [200,198,650,222] type=text
        candidates: "住所"[120,200,180,220] left | "郵便番号"[120,230,200,248] above | ...
      
      --- Page 2 ---
      Text50 [100,80,300,100] type=text
        candidates: ...
    
    フォーマット詳細:
    - 1行目: field_id [x1,y1,x2,y2] type=xxx
    - 2行目（インデント2スペース）: candidates: "text"[x1,y1,x2,y2] direction | ...
    - direction は CandidateLabel.direction の値
    - candidatesはdistance_score昇順（最も近い候補が先）
    - ページ間は空行 + "--- Page N ---" で区切る
    """
```

### レスポンスパース

```python
@dataclass
class IdentifiedField:
    """LLMが識別したフィールド"""
    field_id: str
    label: str | None
    semantic_key: str
    confidence: int              # 0-100

def parse_identification_response(
    response_text: str,
    expected_field_ids: list[str],
) -> tuple[list[IdentifiedField], list[str]]:
    """
    LLMのレスポンスをパースし、IdentifiedFieldリストに変換する。
    
    引数:
      response_text: LLMの生出力テキスト
      expected_field_ids: 入力に含まれていた全フィールドIDのリスト
    
    戻り値: (identified_fields, missing_field_ids)
      - identified_fields: パース成功したフィールドのリスト
      - missing_field_ids: レスポンスに含まれていなかったフィールドIDのリスト
    
    パースロジック:
    1. response_textから ```json ``` や ``` ``` のフェンスを除去
    2. JSON配列としてパース
    3. 各要素をIdentifiedFieldに変換
       - field_id が expected_field_ids に含まれない場合はスキップ（警告ログ）
       - confidence が文字列の場合はintに変換
       - label が空文字列の場合はNoneに変換
    4. expected_field_ids のうちレスポンスに含まれていないものを missing_field_ids として返却
    
    エラーハンドリング:
    - JSONパース失敗 → 空リスト + 全field_idsをmissingとして返却 + エラーログ
    - 部分的にパース可能な場合は可能な分だけ返却
    """
```

### テスト要件

```python
# test_prompts_v2.py

def test_build_prompt_no_few_shot():
    """few-shotなしでプロンプトが正しく構築される"""
    fields = [FieldWithCandidates(
        field_id="Text1", field_type="text", page=1,
        bbox_ivb=(200, 148, 450, 172),
        candidates=[
            CandidateLabel(text="氏名", bbox_ivb=(120, 150, 180, 170),
                          distance_score=50.0, direction="left"),
        ]
    )]
    system, user = build_field_identification_prompt(fields)
    assert "氏名" in user
    assert "Text1" in user
    assert "[120,150,180,170]" in user
    assert "left" in user
    assert "Confirmed mappings" not in system  # few-shotなし

def test_build_prompt_with_few_shot():
    """few-shotありでプロンプトにConfirmed mappingsセクションが含まれる"""
    pairs = [{"field_id": "Text3", "label": "氏名",
              "semantic_key": "applicant_name",
              "field_bbox_ivb": [200, 148, 450, 172],
              "label_bbox_ivb": [120, 150, 180, 170],
              "confidence": 95}]
    fields = [FieldWithCandidates(
        field_id="Text1", field_type="text", page=1,
        bbox_ivb=(200, 200, 450, 220),
        candidates=[CandidateLabel("住所", (120, 200, 180, 220), 30.0, "left")]
    )]
    system, user = build_field_identification_prompt(fields, confirmed_pairs=pairs)
    assert "Confirmed mappings" in system
    assert "氏名" in system
    assert "applicant_name" in system

def test_parse_valid_response():
    """正常なJSONレスポンスのパース"""
    response = '[{"field_id":"Text1","label":"氏名","semantic_key":"applicant_name","confidence":90}]'
    fields, missing = parse_identification_response(response, ["Text1", "Text2"])
    assert len(fields) == 1
    assert fields[0].label == "氏名"
    assert fields[0].confidence == 90
    assert "Text2" in missing

def test_parse_fenced_response():
    """```json ... ``` で囲まれたレスポンスのパース"""
    response = '```json\n[{"field_id":"Text1","label":"氏名","semantic_key":"name","confidence":85}]\n```'
    fields, missing = parse_identification_response(response, ["Text1"])
    assert len(fields) == 1

def test_parse_invalid_json():
    """JSONパース失敗時のフォールバック"""
    fields, missing = parse_identification_response("not json", ["Text1", "Text2"])
    assert len(fields) == 0
    assert set(missing) == {"Text1", "Text2"}

def test_parse_null_label():
    """label=null のフィールド"""
    response = '[{"field_id":"Text1","label":null,"semantic_key":"unknown","confidence":10}]'
    fields, _ = parse_identification_response(response, ["Text1"])
    assert fields[0].label is None
```

---

## ファイル3: `benchmark.py`

### 責務

1. 同一フォームデータで現行v1 vs 改善v2を比較実行
2. 複数モデル対応（gpt-4.1-mini, gemini-2.5-flash, gpt-5.4-nano）
3. 精度・レイテンシ・コスト・confidence分布を計測・出力
4. 結果をJSON保存（後続分析用）

### CLIインターフェース

```bash
# 基本実行（全パターン実行）
python -m apps.api.app.services.vision_autofill.benchmark \
    --fields-json path/to/fields.json \
    --blocks-json path/to/text_blocks.json

# 特定モデルのみ
python -m apps.api.app.services.vision_autofill.benchmark \
    --fields-json fields.json \
    --blocks-json blocks.json \
    --models gpt-4.1-mini gemini-2.5-flash

# few-shot例付き
python -m apps.api.app.services.vision_autofill.benchmark \
    --fields-json fields.json \
    --blocks-json blocks.json \
    --few-shot-json confirmed_pairs.json

# 出力先指定
python -m apps.api.app.services.vision_autofill.benchmark \
    --fields-json fields.json \
    --blocks-json blocks.json \
    --output-dir ./benchmark_results/
```

### 入力ファイルフォーマット

```jsonc
// fields.json — 現行システムと同じ形式
[
  {"id": "Text1", "t": "text", "p": 1, "b": [120, 80, 150, 20]},
  {"id": "CheckBox1", "t": "checkbox", "p": 1, "b": [300, 200, 15, 15]},
  // ...
]

// text_blocks.json — 現行システムと同じ形式
[
  {"s": "氏名", "p": 1, "b": [60, 78, 50, 15]},
  {"s": "フリガナ", "p": 1, "b": [60, 100, 80, 15]},
  // ...
]

// confirmed_pairs.json（オプション）— few-shot例
[
  {
    "field_id": "Text3",
    "label": "氏名",
    "semantic_key": "applicant_name",
    "field_bbox_ivb": [200, 148, 450, 172],
    "label_bbox_ivb": [120, 150, 180, 170],
    "confidence": 95
  }
]
```

### テストパターン定義

```python
TEST_PATTERNS = [
    {
        "name": "A_baseline_gpt41mini",
        "description": "現行プロンプト + gpt-4.1-mini（ベースライン）",
        "prompt_version": "v1",
        "model": "gpt-4.1-mini",
        "few_shot": False,
    },
    {
        "name": "B_improved_gpt41mini",
        "description": "改善プロンプト + 候補絞り込み + gpt-4.1-mini",
        "prompt_version": "v2",
        "model": "gpt-4.1-mini",
        "few_shot": False,
    },
    {
        "name": "C_improved_gemini_flash",
        "description": "改善プロンプト + 候補絞り込み + Gemini 2.5 Flash",
        "prompt_version": "v2",
        "model": "gemini-2.5-flash",
        "few_shot": False,
    },
    {
        "name": "D_improved_gemini_flash_fewshot",
        "description": "改善プロンプト + 候補絞り込み + Gemini 2.5 Flash + few-shot",
        "prompt_version": "v2",
        "model": "gemini-2.5-flash",
        "few_shot": True,  # confirmed_pairs.json が必要
    },
    {
        "name": "E_improved_gpt54nano",
        "description": "改善プロンプト + 候補絞り込み + GPT-5.4 nano",
        "prompt_version": "v2",
        "model": "gpt-5.4-nano",
        "few_shot": False,
    },
]
```

### 各モデルのAPI呼び出し仕様

```python
# モデル別設定
MODEL_CONFIGS = {
    "gpt-4.1-mini": {
        "provider": "openai",
        "api_model": "gpt-4.1-mini",
        "max_tokens": 16384,
        "temperature": 0.0,
        "cost_input_per_m": 0.40,
        "cost_output_per_m": 1.60,
        "supports_structured_output": True,
    },
    "gemini-2.5-flash": {
        "provider": "google",
        "api_model": "gemini-2.5-flash-preview-05-20",  # 最新の安定版を使用
        "max_tokens": 16384,
        "temperature": 0.0,
        "cost_input_per_m": 0.30,
        "cost_output_per_m": 2.50,
        "supports_structured_output": True,
        # Gemini固有: thinking_config を無効化（コスト節約）
        # thinking_config: {"thinking_budget": 0} or省略
    },
    "gpt-5.4-nano": {
        "provider": "openai",
        "api_model": "gpt-5.4-nano",
        "max_tokens": 16384,
        "temperature": 0.0,
        "cost_input_per_m": 0.15,
        "cost_output_per_m": 0.90,
        "supports_structured_output": True,
    },
}
```

### API呼び出し共通関数

```python
async def call_llm(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 16384,
    temperature: float = 0.0,
) -> tuple[str, dict]:
    """
    LLMを呼び出し、レスポンスとメタデータを返却する。
    
    戻り値: (response_text, metadata)
    metadata = {
        "model": str,
        "input_tokens": int,
        "output_tokens": int,
        "latency_ms": int,
        "cached_tokens": int,  # prompt caching hit分
    }
    
    OpenAI呼び出し:
      openai.chat.completions.create(
          model=model,
          messages=[
              {"role": "system", "content": system_prompt},
              {"role": "user", "content": user_prompt},
          ],
          max_tokens=max_tokens,
          temperature=temperature,
          response_format={"type": "json_object"},  # JSONモード
      )
    
    Google Gemini呼び出し:
      google.generativeai.GenerativeModel(model).generate_content(
          contents=[user_prompt],
          generation_config={
              "response_mime_type": "application/json",
              "max_output_tokens": max_tokens,
              "temperature": temperature,
          },
          system_instruction=system_prompt,
      )
    
    注意:
    - OpenAIは response_format={"type":"json_object"} でJSONモード有効化
    - Geminiは response_mime_type="application/json" でJSONモード有効化
    - タイムアウトは120秒
    - リトライは最大2回（exponential backoff: 2s, 4s）
    """
```

### ベンチマーク実行フロー

```python
async def run_benchmark(
    fields: list[dict],
    text_blocks: list[dict],
    confirmed_pairs: list[dict] | None,
    patterns: list[dict],
    output_dir: str,
):
    """
    処理フロー:
    1. candidate_filter.filter_candidates() で候補絞り込み（v2用、1回だけ実行）
    2. 各テストパターンに対して:
       a. prompt_version に応じてプロンプトを構築
          - "v1": 現行 prompts.py のプロンプトをそのまま使用
          - "v2": prompts_v2.py のプロンプトを使用
       b. few_shot=True の場合、confirmed_pairs を挿入
       c. タイマー開始
       d. call_llm() でAPI呼び出し
       e. タイマー停止
       f. parse_identification_response() でパース
       g. 結果を記録
    3. 全パターンの結果を比較表として stdout に出力
    4. 詳細結果を output_dir にJSON保存
    """
```

### 出力フォーマット

```python
# stdout出力（テーブル形式）
"""
=== Benchmark Results ===

Pattern                          | Fields | Identified | Missing | Latency | Input Tok | Output Tok | Cost
---------------------------------|--------|------------|---------|---------|-----------|------------|------
A_baseline_gpt41mini             |    189 |        142 |      47 |  72.3s  |    41,230 |     12,400 | $0.036
B_improved_gpt41mini             |    189 |        168 |      21 |   8.1s  |     8,450 |      3,200 | $0.009
C_improved_gemini_flash          |    189 |        171 |      18 |   6.3s  |     8,450 |      3,100 | $0.010
D_improved_gemini_flash_fewshot  |    189 |        179 |      10 |   7.2s  |    10,800 |      3,200 | $0.012
E_improved_gpt54nano             |    189 |        155 |      34 |   4.1s  |     8,450 |      3,000 | $0.004

Confidence Distribution:
Pattern                          | 90-100 | 70-89 | 50-69 | 30-49 | 0-29 (null)
---------------------------------|--------|-------|-------|-------|------------
A_baseline_gpt41mini             |     45 |    52 |    45 |     - |      47
B_improved_gpt41mini             |     78 |    55 |    35 |    12 |       9
...
"""

# JSON出力（output_dir/benchmark_YYYYMMDD_HHMMSS.json）
{
    "timestamp": "2026-03-26T15:30:00Z",
    "input_summary": {
        "field_count": 189,
        "text_block_count": 770,
        "page_count": 4,
        "few_shot_count": 0
    },
    "results": [
        {
            "pattern": "A_baseline_gpt41mini",
            "description": "...",
            "model": "gpt-4.1-mini",
            "prompt_version": "v1",
            "metrics": {
                "identified_count": 142,
                "missing_count": 47,
                "latency_ms": 72300,
                "input_tokens": 41230,
                "output_tokens": 12400,
                "cached_tokens": 0,
                "cost_usd": 0.036,
                "confidence_distribution": {
                    "90_100": 45,
                    "70_89": 52,
                    "50_69": 45,
                    "30_49": 0,
                    "0_29": 47
                }
            },
            "fields": [
                {
                    "field_id": "Text1",
                    "label": "法人名",
                    "semantic_key": "company_name",
                    "confidence": 92
                },
                // ...
            ]
        }
    ]
}
```

### テスト要件

```python
# test_benchmark.py

def test_v1_prompt_construction():
    """v1プロンプトが現行形式と一致すること"""
    # 現行prompts.pyのフォーマットと同一出力であることを確認

def test_v2_prompt_construction():
    """v2プロンプトが候補付きフォーマットで構築されること"""

def test_token_count_reduction():
    """v2のinputトークン数がv1の30%以下であること（推定）"""
    # 実際のトークンカウントではなく文字数ベースの推定でOK
    # v1: fields_json + blocks_json の文字数
    # v2: fields_with_candidates のコンパクト表現の文字数

def test_output_json_schema():
    """出力JSONが定義済みスキーマに適合すること"""
```

---

## 依存パッケージ

```
# 既存プロジェクトにあるはず（確認のみ）
openai>=1.0
# 追加が必要な可能性
google-generativeai>=0.8      # Gemini API
```

### 環境変数

```bash
OPENAI_API_KEY=sk-...          # gpt-4.1-mini, gpt-5.4-nano用
GOOGLE_API_KEY=AI...           # または GEMINI_API_KEY  Gemini用
```

---

## 実装優先順位

```
1. candidate_filter.py + テスト   ← 最初に完成させる（LLM不要で動作確認可能）
2. prompts_v2.py + テスト         ← 次に完成（モック入力でテスト可能）
3. benchmark.py                   ← 最後（API key必要、実際のLLM呼び出し）
```

---

## 品質基準

- Python 3.11+ 対応
- 型ヒント（type hints）必須。全ての関数に引数型と戻り値型を記述
- docstring必須（日本語可）
- f-string使用（.format() は不可）
- dataclass使用（TypedDict不可）
- async/await使用（benchmark.pyのLLM呼び出し部分）
- logging使用（print不可、デバッグ出力はlogger.debug）
- テストは pytest で実行可能なこと

---

## NOT in scope（この仕様書に含まれない）

- Supabaseへの保存（Phase 1以降で実装）
- テンプレートフィンガープリント（Phase 1で実装）
- SpatialScorer（ロジスティック回帰）（Phase 2で実装）
- LLMカスケード（Phase 3で実装）
- Active Learning / Human Review UI（Phase 4で実装）
- 既存 prompts.py の変更（v2は新規ファイルとして追加）
- AUTOFILLプロンプトの改善（別タスク）

---

## 完了条件

1. `candidate_filter.py` の全テストがパスする
2. `prompts_v2.py` の全テストがパスする
3. `benchmark.py` が `--fields-json` と `--blocks-json` を受け取り、
   最低1モデル（gpt-4.1-mini）でベンチマークを実行し、結果テーブルとJSONを出力できる
4. v2プロンプトの入力トークン数がv1の30%以下であること（文字数ベース推定）
