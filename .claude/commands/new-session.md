---
name: new-session
description: セッション開始時の定型チェック。前回の進捗確認とコンテキスト整理を行う。
allowed_tools: ["Read", "Bash"]
---

# /new-session

新しい Claude Code セッションを開始する際に実行するウォームアップコマンド。

## Goal

前回セッションの状態を素早く把握し、クリーンなコンテキストで作業を開始する。

## Suggested Sequence

1. `@docs/progress.md` を読んで前回の進捗を確認する
2. `git log --oneline -10` で最近のコミット履歴を確認する
3. `git status` で作業中のファイルを確認する
4. 作業すべきタスクのサマリーを出力する

## Notes

- セッション開始時に必ず実行する習慣をつける
- 前回の未完了タスクがあれば優先的に対処する
