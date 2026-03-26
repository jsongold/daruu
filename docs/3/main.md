# PDF Form Field Identification - Multi-Level Architecture Implementation

## Overview

PDF フォーム自動入力システムの `FIELD_IDENTIFICATION` モジュールをリファクタリングする。
現在LLMに70秒かかっているフィールドラベル特定処理を、3段階のフォールバック戦略 + 非同期First Actionパターンで最適化する。

## 背景と制約

### 現状の問題
- AcroFormのfield_idは "Text1", "Text2" 等の無意味な連番
- 189フィールドのラベル特定に LLM (GPT-4o-mini via LiteLLM) で70秒かかる
- 出力トークン数（~9,500）がボトルネック（入力は~3,000トークン）
- 出力を削ると精度が落ちる（nullフィールドもChain-of-Thoughtとして機能）
- 世界中の多様なフォームに対応する必要あり（特定フォーム特化は不可）

### 目標
- ユーザーへの最初の応答を3-5秒以内に
- フィールドラベル特定の精度を維持または向上
- 汎用性を保つ（テーブル構造のないフォームにも対応）

## Architecture

### 全体フロー

```
PDF到着
  │
  ├─→ Python前処理（0.1秒）
  │     ├─ AcroFormフィールド抽出
  │     ├─ テキストブロック抽出 + マージ
  │     └─ nearby_labels生成
  │
  ├─→ Level 1: 構造化ラベル解析（Python, 0.1秒）
  │     ├─ field_idセマンティクスチェック
  │     ├─ find_tables() → 行×列ヘッダーマッピング
  │     └─ 結果: resolved / unresolved フィールド分類
  │
  ├─→ [async] 質問生成（3秒）← Level 1結果で起動
  │
  └─→ [async] Level 2: Vision + ページ単位LLM（10-25秒）← unresolvedのみ
        └─ Level 2完了 or ユーザー回答到着 → 高精度マッピング
```

### First Action パターン（2モード）

```python
# Quick Mode: Level 1 + 即質問、FIELD_IDスキップ
# Precise Mode: Level 1 + 即質問 + 裏でLevel 2実行

# ユーザー回答がLevel 2完了前に来た場合:
#   → nearby_labelsベースで暫定マッピング → Level 2完了後に差分補正
```

## 実装仕様

### Module 1: `field_preprocessing.py` — Python前処理

pdfplumber を使用してPDFからフィールドとテキストを抽出する。

#### 関数: `extract_fields(pdf_path: str) -> list[FieldInfo]`

```python
@dataclass
class FieldInfo:
    field_id: str           # AcroFormのT属性 (例: "Text1")
    field_type: str         # "text" | "checkbox" | "dropdown"
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1) page座標
    page: int               # ページ番号 (0-indexed)
    max_length: int | None  # MaxLen属性
    options: list[str] | None  # ドロップダウン選択肢
```

実装詳細:
- `pdfplumber.open(pdf_path)` でPDFを開く
- 各ページの `page.annots` からAcroFormフィールドを抽出
- `data['FT']` でフィールド種別を判定: `/Tx`=text, `/Btn`=checkbox, `/Ch`=dropdown
- bbox は `page.annots` の `x0, top, x1, bottom` を使用（pdfplumber page座標系）

#### 関数: `extract_text_blocks(pdf_path: str) -> list[TextBlock]`

```python
@dataclass
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    page: int
```

実装詳細:
- `page.extract_words(x_tolerance=5, y_tolerance=3)` でワード抽出
- 近接ワードをマージする `merge_nearby_words()` を適用:
  - x方向12pt以内、y方向5pt以内のワードを結合
  - これにより930ブロック → 約250ブロックに集約される
- 1文字の記号・句読点（`・（）、。□■○●/-`）はフィルタ

マージアルゴリズム:
```
1. ワードを (round(top/5)*5, x0) でソート
2. 順番に走査し、前のワードと同一行 (y差 < 5pt) かつ近接 (x gap < 12pt) なら結合
3. それ以外は新しいブロックとして追加
```

#### 関数: `generate_nearby_labels(fields, text_blocks) -> dict[str, list[NearbyLabel]]`

```python
@dataclass
class NearbyLabel:
    text: str
    direction: str  # "left" | "above" | "right"
    distance: float  # pt
```

各フィールドに対して:
1. 同一ページのテキストブロックのみ対象
2. 方向別に候補を探索:
   - **左方向**: テキスト右端 <= フィールド左端、Y中心の差 < 15pt、距離 < 50pt
   - **上方向**: テキスト下端 <= フィールド上端、X中心の差 < 80pt、距離 < 50pt
   - **右方向**: テキスト左端 >= フィールド右端、Y中心の差 < 15pt、距離 < 50pt
3. 距離でソートし上位3-5件を返す
4. 1文字以下のテキストは除外

### Module 2: `level1_structural.py` — Level 1: 構造化ラベル解析

LLMを一切使わず、Pythonだけでフィールドのセマンティクスを確定する。

#### 関数: `resolve_field_ids(fields: list[FieldInfo]) -> dict[str, str]`

field_idに意味があるかチェック:
- `_` や camelCase で区切り、英単語が2つ以上含まれるか
- 例: `employee_name`, `dateOfBirth`, `address_line1` → セマンティックと判定
- 例: `Text1`, `Field_3`, `CheckBox2` → 非セマンティック

#### 関数: `resolve_by_table_structure(pdf_path: str, fields: list[FieldInfo], text_blocks: list[TextBlock]) -> StructuralResult`

```python
@dataclass
class StructuralResult:
    resolved: dict[str, str]      # field_id → semantic_label
    unresolved: list[str]         # 解決できなかったfield_id群
    confidence: dict[str, float]  # field_id → 確信度
```

実装手順:

1. **テーブル検出**: `page.find_tables()` でテーブルを検出
2. **フィールド→セル マッピング**: 各フィールドのbbox中心がどのセルに属するか判定
3. **ヘッダー抽出**: `table.extract()` の最初の1-3行をヘッダーとして取得
4. **行セクション特定**: 行ヘッダー（最左列のテキスト）からセクション名を取得
5. **列ヘッダー特定**: ヘッダー行の各セルテキストを列の意味として使用
6. **構造化ラベル生成**: `{行セクション} > {列ヘッダー}` 形式

フィールド→セル判定:
```python
def field_in_cell(field: FieldInfo, cell_bbox: tuple) -> bool:
    fx = (field.bbox[0] + field.bbox[2]) / 2
    fy = (field.bbox[1] + field.bbox[3]) / 2
    return cell_bbox[0] <= fx <= cell_bbox[2] and cell_bbox[1] <= fy <= cell_bbox[3]
```

セル内テキスト取得:
```python
def get_text_in_cell(text_blocks: list, cell_bbox: tuple) -> str:
    texts = []
    for tb in text_blocks:
        tx = (tb.bbox[0] + tb.bbox[2]) / 2
        ty = (tb.bbox[1] + tb.bbox[3]) / 2
        if cell_bbox[0] <= tx <= cell_bbox[2] and cell_bbox[1] <= ty <= cell_bbox[3]:
            texts.append(tb.text)
    return ' '.join(texts)
```

confidence基準:
- 行ヘッダー + 列ヘッダーの両方あり → 0.9
- 列ヘッダーのみ → 0.7
- セルに所属するがヘッダーが取れない → 0.5
- テーブルに属さない → unresolved

#### 関数: `level1_resolve(pdf_path: str) -> Level1Result`

上記の関数を組み合わせた統合関数:

```python
@dataclass
class Level1Result:
    field_labels: dict[str, str]       # field_id → semantic_label (resolved)
    unresolved_fields: list[FieldInfo] # Level 2に渡すフィールド群
    nearby_labels: dict[str, list[NearbyLabel]]  # 全フィールドのnearby_labels
    form_title: str | None             # フォームタイトル（検出できた場合）
    field_infos: list[FieldInfo]       # 全フィールド情報
```

処理順序:
1. `extract_fields()` + `extract_text_blocks()`
2. `resolve_field_ids()` → 意味あるfield_id を resolved に追加
3. `resolve_by_table_structure()` → テーブル構造で解決したものを追加
4. `generate_nearby_labels()` → 全フィールドに対して生成（Level 2用 + autofill用）
5. フォームタイトル検出: ページ上部(y < 50pt)の最大テキストブロック

### Module 3: `level2_vision.py` — Level 2: Vision + ページ単位LLM

Level 1で解決できなかったフィールドをVision LLMで特定する。

#### 関数: `resolve_by_vision(pdf_path: str, unresolved: list[FieldInfo], nearby_labels: dict, page_images: dict[int, bytes] | None = None) -> dict[str, str]`

ページ単位で処理:
1. 未解決フィールドをページ別にグループ化
2. 各ページについて:
   a. ページ画像を生成（pdf2imageまたはfitz）
   b. 未解決フィールドのbbox座標 + nearby_labels候補をプロンプトに含める
   c. Vision LLM呼び出し

プロンプト設計（ページ単位）:
```
System: You are a PDF form field identification assistant.
You will see a page image and a list of form fields with their positions.
For each field, identify its semantic label based on the visual layout.

User:
[Page image attached]

Identify the label for each of these form fields:

Fields on this page:
- Text23: bbox=[577,165,682,199], nearby_candidates=["住所又は居所(L,3pt)", "異動月日(A,2pt)"]
- Text24: bbox=[683,165,750,199], nearby_candidates=["異動月日及び事由(A,0pt)"]
...

Respond in compact format:
field_id:label
(Only include fields you can identify with confidence >= 0.5)
```

重要な設計判断:
- Vision入力はページ画像1枚（10,000-30,000トークン）
- nearby_labelsを候補として渡す（LLMのヒントになり出力が速くなる）
- **出力はfield_id:label の1行形式**（JSONではなく。出力トークン削減）
- ページあたりの未解決フィールドが少なければLLM呼び出し自体が速い

#### ページ画像生成

```python
# pdf2image または PyMuPDF (fitz) を使用
# 解像度: 150 DPI（Visionに十分かつトークン節約）
# フォーマット: PNG
```

### Module 4: `orchestrator.py` — 非同期オーケストレーション

#### 関数: `async identify_fields(pdf_path: str, mode: str = "precise") -> FieldIdentificationResult`

```python
@dataclass  
class FieldIdentificationResult:
    field_labels: dict[str, str]         # field_id → semantic_label
    confidence: dict[str, float]         # field_id → confidence
    resolution_method: dict[str, str]    # field_id → "field_id" | "table" | "vision" | "nearby"
    nearby_labels: dict[str, list[NearbyLabel]]  # autofillに渡す用
    form_title: str | None
    field_infos: list[FieldInfo]
```

Quick Mode:
```python
async def identify_fields_quick(pdf_path):
    level1 = level1_resolve(pdf_path)  # 0.1秒
    # Level 2はスキップ
    # unresolvedフィールドはnearby_labelsのままautofillに渡す
    return FieldIdentificationResult(
        field_labels=level1.field_labels,
        # unresolved分はnearby_labelsの最有力候補をラベルとして使用
        ...
    )
```

Precise Mode:
```python
async def identify_fields_precise(pdf_path):
    level1 = level1_resolve(pdf_path)  # 0.1秒
    
    if not level1.unresolved_fields:
        return build_result(level1)  # 全て解決済み
    
    # Level 2を非同期で起動（裏側で実行）
    level2_task = asyncio.create_task(
        resolve_by_vision(pdf_path, level1.unresolved_fields, level1.nearby_labels)
    )
    
    return level1, level2_task  # 呼び出し元がawaitするタイミングを制御
```

#### 関数: `async first_action_flow(pdf_path: str, mode: str, user_data: dict | None = None)`

First Action + 裏側処理の統合フロー:

```python
async def first_action_flow(pdf_path, mode, user_data=None):
    # Phase 1: 即座に開始
    level1 = level1_resolve(pdf_path)
    
    # Phase 2: 並行タスク起動
    question_task = asyncio.create_task(
        generate_questions(level1, user_data)  # 3-5秒
    )
    
    level2_task = None
    if mode == "precise" and level1.unresolved_fields:
        level2_task = asyncio.create_task(
            resolve_by_vision(pdf_path, level1.unresolved_fields, level1.nearby_labels)
        )
    
    # Phase 3: 質問を先に返す
    questions = await question_task
    yield {"type": "questions", "questions": questions}  # t=3秒
    
    # Phase 4: ユーザー回答を待つ
    user_answers = yield  # ユーザー回答受信
    
    # Phase 5: マッピング
    if level2_task:
        # Level 2が完了しているか確認
        if level2_task.done():
            level2_labels = level2_task.result()
            merged_labels = {**level1.field_labels, **level2_labels}
            result = await autofill(merged_labels, user_answers)
        else:
            # 未完了: nearby_labelsで暫定マッピング
            preliminary = await autofill_with_nearby(level1, user_answers)
            yield {"type": "preliminary_result", "result": preliminary}
            
            # Level 2完了を待って差分補正
            level2_labels = await level2_task
            correction = await correct_mapping(preliminary, level2_labels)
            result = apply_corrections(preliminary, correction)
    else:
        result = await autofill_with_nearby(level1, user_answers)
    
    yield {"type": "final_result", "result": result}
```

### Module 5: `diff_correction.py` — 差分補正

Level 2完了後に暫定マッピングを補正する。

#### 関数: `async correct_mapping(preliminary: dict, level2_labels: dict) -> list[Correction]`

```python
@dataclass
class Correction:
    field_id: str
    old_value: str
    new_value: str
    reason: str
```

ロジック:
1. preliminaryのfield_labelsとlevel2_labelsを比較
2. ラベルが異なるフィールドを特定
3. ラベルが変わったフィールドについて、マッピングされた値が正しいか再評価
4. 値の変更が必要なもののみCorrectionとして返す

重要: 差分のみをLLMに渡す（全フィールドの再マッピングはしない）

## 既存システムとの統合

### 現在のプロンプト構造（変更しない）

```
AUTOFILL_SYSTEM_PROMPT      → autofill_quick で使用（変更なし）
DETAILED_MODE_SYSTEM_PROMPT → detailed_turn で使用（変更なし）
FIELD_IDENTIFICATION_SYSTEM_PROMPT → Level 2 Visionプロンプトで置換
```

### 入力フォーマットの改善

現在のautofillプロンプトの `nearby_labels` の代わりに、Level 1/2 で解決した `semantic_label` を使用:

```
現在:
  {"id": "Text1", "nearby_labels": ["所轄税務署長等", "給与の支払者"]}

改善後:
  {"id": "Text1", "label": "給与の支払者の名称", "resolved_by": "table"}

Level 1未解決の場合:
  {"id": "Text23", "nearby_labels": ["住所又は居所", "異動月日"], "resolved_by": "nearby"}
```

## 過去データ活用（オプション）

過去の記入済みPDFがある場合、最優先で適用:

```python
def resolve_from_past_data(pdf_path: str, past_pdf_path: str) -> dict[str, str]:
    """過去PDFの記入済み値からfield_idのセマンティクスを確定"""
    past_fields = extract_filled_fields(past_pdf_path)
    # field_id → 値 のペアから、値の内容でセマンティクスを推論
    # 例: Text1 = "株式会社Cafkah" → "会社名/給与支払者名称"
    # 例: Text7 = "竹村康正" → "氏名"
```

これはLevel 1の前に実行し、resolvedに追加する。

## テスト方針

### ユニットテスト

1. `field_preprocessing.py`:
   - 日本公的フォーム（罫線あり）でテキストブロック抽出が正しいか
   - nearby_labelsの方向・距離が正しいか
   - ワードマージが期待通りに動くか

2. `level1_structural.py`:
   - テーブル検出 → セル → フィールドマッピングの精度
   - field_idセマンティクスチェックの正確性
   - ヘッダー行の認識精度

3. `orchestrator.py`:
   - Quick/Preciseモードの切り替え
   - Level 2未完了時のフォールバック動作
   - 差分補正の正確性

### 統合テスト

テスト用PDFを3種類用意:
1. 日本公的フォーム（テーブル構造あり）→ Level 1で80%+解決を期待
2. 欧米Tax Form（部分テーブル）→ Level 1で50-60%、Level 2で残り
3. フリーレイアウトPDF → Level 1は低解決率、Level 2主体

### パフォーマンス計測

各ステップの処理時間を計測してログ出力:
```python
import time

timings = {}
t0 = time.time()
level1 = level1_resolve(pdf_path)
timings['level1'] = time.time() - t0

t1 = time.time()
level2 = await resolve_by_vision(...)
timings['level2'] = time.time() - t1

# SUMMARYとして出力（現在のフォーマットに合わせる）
```

## ファイル構成

```
src/
  field_identification/
    __init__.py
    field_preprocessing.py      # Module 1: PDF前処理
    level1_structural.py        # Module 2: 構造化ラベル（Python only）
    level2_vision.py            # Module 3: Vision LLM
    orchestrator.py             # Module 4: 非同期オーケストレーション
    diff_correction.py          # Module 5: 差分補正
    models.py                   # データクラス定義
  tests/
    test_preprocessing.py
    test_level1.py
    test_level2.py
    test_orchestrator.py
    fixtures/
      japanese_tax_form.pdf     # テスト用PDF
```

## 依存パッケージ

```
pdfplumber          # PDF解析・テーブル検出
pdf2image | PyMuPDF # ページ画像生成（Level 2 Vision用）
litellm             # LLM呼び出し（既存）
asyncio             # 非同期処理
```

## 実装順序

1. `models.py` — データクラス定義
2. `field_preprocessing.py` — Python前処理（テスト可能な独立モジュール）
3. `level1_structural.py` — テーブル構造解析（テスト可能な独立モジュール）
4. `level2_vision.py` — Vision LLMフォールバック
5. `orchestrator.py` — 統合 + 非同期制御
6. `diff_correction.py` — 差分補正
7. 既存の autofill / detailed_mode との統合
8. テスト

## 注意事項

- pdfplumber の `find_tables()` は全てのPDFで動くわけではない。罫線がベクターでない場合は空リストを返す。その場合Level 1のテーブル解析は gracefully にスキップし、全フィールドをunresolvedとしてLevel 2に渡す。
- Vision LLMのページ画像は150 DPIで十分。300 DPIにするとトークン数が4倍になり速度が大幅に低下する。
- Level 2のプロンプトでは **JSON出力ではなく `field_id:label` の1行形式** を使う。出力トークン数削減が速度に直結する。
- 差分補正は「ラベルが変わった」かつ「マッピングされた値に影響がある」フィールドのみ対象。大半のフィールドは補正不要。