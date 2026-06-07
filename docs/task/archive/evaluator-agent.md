# evaluator サブエージェントの新設

対応 Issue: [#99](https://github.com/f8924919/yt-gui/issues/99)

## 背景

Anthropic の「計画・生成・評価」3分離パターンを本プロジェクトに適用する。調査（`investigate`）・検証（`verify`）・docs 整合（`docs-check`）は揃っているが、実装が受け入れ条件・spec を実質的に満たすかを独立判定する「評価（Evaluator）」が欠けていた。

## 設計判断

- **責務分離**: `verify` は lint / 型 / テストを機械的に green にするだけ。`evaluator` は受け入れ条件・spec を正本に「本物の実装か」「条件を満たすか」を判定する。両者を分ける。
- **独立性**: 主エージェントの意図を渡さず、diff・コード・Issue・spec のみで判定（自己評価バイアスの排除）。
- **起動条件（A案）**: `feature`/`bugfix`/`hotfix` ブランチで PR 前に必須。費用対効果での省略はしない（「単純だから不要」という判断自体がバイアスのため）。`refactor`/`docs`/`chore` は対象外。
- **モデル**: Opus。生成側（主エージェント）が Opus のため、評価者が弱いと見落としを追認する。コスト懸念が出たら Sonnet 降格を検討。

## 変更内容

- `.claude/agents/evaluator.md`（新規）
- `docs/git-workflow.md` §5 step 7（評価ゲート追記）/ §5.2（委譲表に追加・モデル列追加・「いずれも Sonnet」修正・起動条件明文化）

## メモ

- spec/arch はアプリ実装の設計ドキュメントで、本タスク（開発ワークフロー定義の拡張）の設計正本は `git-workflow.md` 側。そのため spec/arch の更新は不要。
