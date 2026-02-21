以下は、**Yパターン（＝同一ユーザー判定はあなたのSaaSのログイン状態で行い、ログイン済みならClaude画面から遷移なし）**で進める場合の **設計・UX・課金・セキュリティを一気通貫でまとめた最終整理**です。
このまま **設計判断ドキュメント／PRD補遺**として使える粒度にしています。

---

# Yパターン最終まとめ

**「Claudeは入口、同一ユーザー判定と課金の正はあなたのSaaS」**

---

## 1. 基本方針（最重要）

* **ClaudeはユーザーIDを持たない**
* **同一ユーザー判定・課金・権限管理の正はあなたのSaaS**
* Claude上では

  * 未ログイン → 制限付き体験
  * ログイン済み → 自動リンク（遷移なし）

> UX的には「Claudeが覚えている」
> セキュリティ的には「あなたのAuthが正」

---

## 2. 同一ユーザー判定の結論

### 2回目アクセス時の判定根拠

* **Supabase Auth のログインセッション（Cookie）**
* ClaudeユーザーIDは一切不要

### 判定フロー（Yパターン）

1. Claude会話開始 → `session_token` 発行
2. Claudeが MCP tool `link_session(session_token)` を呼ぶ
3. サーバ側で：

   * Cookie から `user_id` が取れる → **自動リンク**
   * 取れない → **未ログイン**

👉 **ログイン済みなら、別ページ遷移は不要**

---

## 3. ページ遷移の要否

| 状態             | 別ページ遷移        |
| -------------- | ------------- |
| 初回・未ログイン       | ✅ 必要（ログイン/課金） |
| 2回目以降・ログイン済み   | ❌ 不要          |
| 課金変更（Upgrade等） | ✅ 必要          |

**原則**

* 遷移は「必要な時だけ」
* 2回目以降の通常利用は Claude 内で完結

---

## 4. 課金モデルの成立性

### Claude内課金は不可

* Claudeは決済主体になれない
* Claudeユーザー情報も取得不可

### 現実解（成立する）

* Claude → あなたのSaaSで課金
* 課金結果は **entitlements（権限）** として反映
* Claude上では「即時解放」

👉 UX的には「Claude内課金」に見える
👉 実態は「あなたのSaaS課金」

---

## 5. 技術構成（要点）

### 中核コンポーネント

* **Supabase Auth**：ユーザーIDの正
* **Stripe**：決済
* **entitlements**：機能ON/OFFの最終判定
* **mcp_sessions**：Claude会話単位の入口（短命）

### session_token の役割

* Claude会話 ⇄ あなたのバックエンドを一時的につなぐ
* **恒久IDではない**
* user_id が取れたら即リンク → 以後は user_id で判定

---

## 6. UXの完成形（Golden Flow + Y）

### 初回（未ログイン）

```
Filled 45 fields.
🔒 Download requires login.
[Login]
```

→ Webへ遷移（ログイン/課金）

---

### 2回目以降（ログイン済み）

```
Filled 45 fields.
[Download PDF]
```

* ログイン操作なし
* Claudeから離脱なし
* PRDの「<5 turns / <3 min」を満たす

---

## 7. セキュリティ設計（Y前提で必須）

### 最大リスク

1. **session_token 漏洩**
2. **CSRF（Cookie認証 × 自動リンク）**
3. **認可不備（tokenだけでデータに触れる）**

### 必須対策（要約）

* session_token

  * 短命（10分〜1時間）
  * ワンタイム
  * ハッシュ保存
* link_session API

  * CSRFトークン必須
  * Originチェック
* 機密操作（export/download）

  * **user認証 + entitlement必須**
* Supabase

  * **RLS必須**
* Storage

  * private bucket
  * 短命署名URL

👉 **「遷移なし」は安全に実現可能だが、ガードは必須**

---

## 8. PRDとの整合性

| PRD要件                     | Yパターン                 |
| ------------------------- | --------------------- |
| One form per conversation | mcp_sessionで一致        |
| Minimal chat              | 自動リンクで会話増えない          |
| Auto-fill first           | 影響なし                  |
| History / Resume          | Web側で一元管理             |
| 課金                        | Stripe + entitlements |
| Trust the user            | 再ログイン強要なし             |

---

## 9. 設計判断の最終結論

* **Yパターンが最も現実的・安全・スケーラブル**
* Claudeは「入口UI・会話体験」
* あなたのSaaSは「認証・課金・データの正」
* 2回目以降は **遷移なしで同一ユーザー判定が可能**
* セキュリティは
  **token短命 + CSRF + entitlement + RLS** で担保

---

## 10. 次にやるべき実装順（推奨）

1. `mcp_sessions` + `link_session` API
2. Supabase Auth 前提の自動リンク
3. entitlements ベースの機能制御
4. Stripe webhook → entitlements更新
5. export/download の最終ガード
