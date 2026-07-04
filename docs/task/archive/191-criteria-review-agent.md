# 受け入れ条件レビュー用サブエージェント新設と start-task 前段への組み込み

- Issue: [#191](https://github.com/f8924919/yt-gui/issues/191)
- PR: [#192](https://github.com/f8924919/yt-gui/pull/192)（マージ済み）
- ブランチ: `feature/191-criteria-review-agent`
- ステータス: 完了
- 更新日: 2026-07-04

## 目的

現行ワークフローの `evaluator`（Opus）は PR 前に「実装が受け入れ条件・spec を満たすか（**適合性**）」を独立評価するが、**受け入れ条件・spec そのものの妥当性**（テスト可能・網羅的・非曖昧・Issue 意図との整合）を点検する手順がない。誤った受け入れ条件は `evaluator` を通過しても的外れな成果物を生む。妥当性の点検は shift-left が原則で、条件の品質はテストファースト運用の red テスト品質に直結する。

そこで実装前（start-task の `investigate` 後・docs 先行前）に受け入れ条件を点検する**読み取り専用の助言エージェント** `criteria-review`（Sonnet）を新設する。`evaluator` と対象が逆で補完関係にあり、**ゲート化せず助言に留める**（採否は主エージェント＋ユーザー、git-workflow §5.1 と整合）。

## 設計メモ（investigate #191 の裏取り）

- **エージェント書式**: `.claude/agents/*.md` は `name` / `description` / `model` / `tools` の YAML フロントマター＋本文（役割宣言→言語ルール→核心原則→進め方→制約→報告フォーマット）。read-only エージェント（`investigate` / `evaluator`）は `Edit` を持たず、Bash は参照系限定を本文で明示（`.claude/agents/investigate.md:29-33`）。雛形は `investigate.md` が最も近い。
- **差し込み位置**: `investigate`（step 3）の後・docs 先行（step 4）の前（案 B）。コード文脈を踏まえた網羅性指摘が可能（`.claude/skills/start-task/SKILL.md:25-31`）。
- **step 番号**: `step 3`/`step 7`/`step 9` が複数ファイル（各 agent・verify-gate・finish-task）から参照されるため、renumber せず **step 3.5** として挿入（`start-task` の担当範囲 step 1〜6 内に収まる）。
- **役割分担**: `evaluator` は「実装後・適合性・独立ゲート・ブランチ種別で強制」（`docs/git-workflow.md:102`）、`criteria-review` は「実装前・妥当性・助言・任意」。目的が逆なので重複・矛盾なし。
- **§5.1 との整合**: 「設計外の問題はユーザー確認」の精神から、条件の通過可否を勝手に止めない助言型が整合的（`docs/git-workflow.md:85`）。

## 変更対象

| ファイル | 変更 |
|---|---|
| `.claude/agents/criteria-review.md` | 新規（エージェント定義） |
| `.claude/skills/start-task/SKILL.md` | step 3.5 追加・フロントマター説明更新 |
| `docs/git-workflow.md` | §5 step 一覧に 3.5 追加・§5.2 表に行追記＋助言の性格を注記・§5.3 start-task 説明更新 |
| `docs/docs-guide.md` | §4.1 に「エージェント/スキル変更」行を追記（docs 乖離の解消） |
| `docs/task/index.md` | 本タスク行を追加 |

## 検証方針

- 製品コード（`yt_gui/`）は不変のため自動テストのスコープ外。単体テストは追加しない。
- `docs-check` で docs 整合（index 更新漏れ・リンク切れ・命名・関連リンク）を点検する。
- `evaluator` は受け入れ条件チェックリストの充足判定として実行する（評価軸 2 が該当）。
