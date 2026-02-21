
## 1) PRD理解（要点の再構成）

このプロダクトは「データ抽出」ではなく **“フォームを正しく完成させる”**ことが目的で、UXの核は **Golden Flow（先に全部埋めてから、ユーザーが直す）**です。

* **UI**: 左がドキュメントプレビュー（ページ/ズーム/ハイライト/クリック編集）、右がチャット
* **動作原則**:

  * まず **Auto-fill**（プロフィール/添付ソース/デフォルト/推論）
  * 不明は空欄のまま
  * **質問はしない**（ユーザーが編集した時のみ最小限）
  * チャットは極小（例: “Filled 45 fields.”）
* **技術**: Agent（LLM推論）と Services（実行系）を分離し、テンプレ（embedding + bbox + rules）で運用

---

## 2) MCP Appsで「Chat部分をClaudeに載せ替える」ことは可能か？

### 結論

**可能。**
ただし「載せ替え」の定義が2通りあるので分けます。

1. **Claudeを“ホストUI”として使う（＝右側チャットをClaudeにする）**

   * これは **MCP Apps の想定ド真ん中**です。Claude（Web/Desktop）が **MCP Apps をホストして iframe UI を会話内に表示**し、UI⇄ホストは JSON-RPC（postMessage）で双方向通信します。([Model Context Protocol][1])
2. **あなたのWebアプリの右ペインを“Claudeチャット画面そのもの”に置換する**

   * これは **原理的には難しい**です。ClaudeのチャットUIをあなたのWebに埋め込むのではなく、**Claude側にあなたのUIを埋め込む**のがMCP Appsの構図です（主従が逆）。

したがって、「PRDのChat部分をClaudeに載せ替え」は、実装としては **“Claudeをアプリのホストにする”**形が現実解です。

---

## 3) どう構成すればPRDのUXをClaude上で再現できるか（設計案）

### 3.1 全体像（Claudeホスト + MCPサーバ + MCP App UI）

* **Claude（ホスト）**: 右側チャット担当（= もはやアプリのチャットUIは不要）
* **あなたのMCPサーバ**: フォーム埋め、bbox、検証、PDF生成、状態管理（Redis/Supabase）などをツールとして提供
* **MCP App UI（iframe）**: 左側プレビュー＋クリック編集＋フィールド一覧など「フォームUI」を提供
  MCP Appsは「ツール定義で `ui://` リソースを宣言 → ホストがHTMLを取得してiframe表示 → UI⇄ホスト双方向通信」というモデルです。([Model Context Protocol][1])

### 3.2 PRDのGolden FlowをMCPに落とすとこうなる

1. ユーザーがClaudeで「このフォーム埋めて」と依頼
2. Claudeが **tool call**（例: `autofill_form`）を実行
3. 結果として

   * チャットには最小限のテキスト（“Filled 45 fields.”）
   * 同時に **MCP App UI** が表示され、左プレビューでハイライト＆編集可能
4. ユーザーがUIでクリック編集（またはチャットで “Change name to John”）
5. UIは `update_field` / `render_preview` / `export_pdf` などのツールを呼び、更新反映
6. 最後に `export_pdf` → ダウンロード（または生成物リンク）

※ MCP Appsはホストがツール結果をUIにプッシュでき、UIからもツールを呼べます。([Model Context Protocol][1])

---

## 4) あなたのPRD要件とMCP Appsのフィット感（○/△/×）

### ○ かなり相性が良い

* **「会話の文脈を保ったままUIを出す」**（フォーム編集はまさにこれ）([Model Context Protocol][1])
* **左プレビューのリッチUI**（PDFビューア、ズーム、ページ、bboxハイライト）
* **クリック→編集→再レンダ**（UIからtool callで実行）
* **AskUserQuestion的な“選択UI”**もMCP Appsで実装例が出ています（Claude Codeでよく見るやつ）。([クラスメソッド発「やってみた」系技術メディア | DevelopersIO][2])

### △ 要注意（プロダクトとしての制約）

* **配布形態**: エンドユーザーに「Claudeアカウント＋コネクタ設定」を前提にすると、SaaSとしての導線/課金/UXが変質します
* **ファイルアップロード**: Claude側の添付・コネクタ仕様に依存（サイズ上限や扱いの制約が出やすい）
* **状態/履歴**: PRDの「会話履歴サイドバー」はClaudeが持つが、あなたのSaaS側の履歴UXとは統合が必要
* **PII/コンプラ**: 「PII戦略はユーザー選択」というPRD方針は維持できるが、Claude側に載る分の境界設計が必要

### × 目的とズレる可能性

* 「一般ユーザー向けSaaSのChat UIをClaudeで置換して提供」
  → これは **“あなたのプロダクトがClaude上のアプリになる”**方向。SaaSとして独立提供したいなら、**“オプションとしてClaudeホスト版も提供”**が自然です。

---

## 5) 実装方針（最短で現実的な落とし所）

### 推奨：二正面作戦

1. **本線（PRD通り）**: あなたのWebアプリ（React/Next + useChat + preview）を継続
2. **並行で“Claudeホスト版”**: MCP Apps版UIを作り、内部利用・パワーユーザー・業務利用に展開

この形なら、PRDの成功指標（ターン数<5、<3分、完了率>90%）を損なわずに、Claude側の強み（会話・既存コネクタ・アプリ内UI）も取り込めます。MCP Apps自体も「スタンドアロンWebより、会話内UI・双方向データフロー・ホスト能力統合・sandbox」の利点を公式に強調しています。([Model Context Protocol][1])

---

## 6) 具体的に用意すべきMCPツール（PRDのService群をそのまま“Tool化”）

最低限（Phase 0/1相当）：

* `upload_form` / `ingest_source_docs`
* `autofill_form`
* `render_preview(page, zoom, highlights)`
* `update_field(field_id, value)`
* `validate_document`
* `export_pdf`

Phase 2〜（テンプレ/embedding）：

* `match_template(visual_embedding)`
* `get_template_fields` / `apply_template_rules`

MCP Appsは **UIが `callServerTool()` でツールを直接叩ける**ため、プレビュー操作（ページ送り、ズーム）も全部ツール化してよいです。([Model Context Protocol][1])

---

## 7) 最終判断

* **「Chat部分をClaudeに載せ替える」＝ Claudeを会話ホストにする**なら、**MCP Appsで実現可能**。
* ただし、あなたのPRDが想定するSaaS提供形態（一般ユーザー、履歴、課金、オンボーディング）を考えると、**完全置換はプロダクト戦略を変える**。
* よって、**“Claudeホスト版（MCP Apps）を別フロントとして追加”**が最も合理的。

---

必要なら次に、あなたの現行アーキ（FastAPI/LangGraph/Redis/Supabase/PyMuPDF）を前提に、**「MCPサーバとして外に出す時の境界（state/ファイル/認可/署名URL）」**と、**MCP App UIで左プレビューを作る最小構成（ui:// resource設計、bboxハイライト、inline edit）**を、PRDのPhase 0→1の粒度で設計図に落とします。

[1]: https://modelcontextprotocol.io/docs/extensions/apps "MCP Apps - Model Context Protocol"
[2]: https://dev.classmethod.jp/articles/shuntaka-mcp-apps-askuserquestion-ui/?utm_source=chatgpt.com "MCP AppsでAskUserQuestionライクな質問UIを実装する"
