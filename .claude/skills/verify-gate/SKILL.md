---
name: verify-gate
description: PR 前の検証ゲートを一括実行する。ブランチ種別を判定し、verify（lint/型/テスト）→ docs-check（docs 変更時）→ evaluator（feature/bugfix/hotfix 時・省略不可）のサブエージェントを順に起動して結果を集約する。実装が一段落し PR を出す前に使う。
---

# verify-gate — PR 前検証ゲート

[docs/git-workflow.md](../../../docs/git-workflow.md) §5 step 7 の検証ゲートを、ブランチ種別に応じて順に起動するオーケストレーション skill。
**判定ルールの正本は git-workflow §5.2**。この skill は手順の入口であり、ルールを再定義しない（変更は git-workflow 側で行う）。

## 前提

- 実装が一段落し、ローカルに変更がある状態で実行する。
- これは委譲の入口なので、各ゲートの**合否判断・設計判断はサブエージェントと主エージェント／ユーザーが行う**（§5.1）。skill はサブエージェントを正しい順序・条件で起動することだけを担う。
- **直列化**: `docs-check` と `evaluator` を同時並行で起動しない。`evaluator` の `git` 参照が `docs-check` の作業ツリー修正と干渉しうるため、必ず順に回す。

## 手順

1. **対象の把握**
   - `git branch --show-current` でブランチ名を取得し、接頭辞からブランチ種別を判定する。
   - `git status --short` / `git diff --name-only main...HEAD`（無ければ `git diff --name-only`）で変更ファイル一覧を取得する。

2. **verify（常時）**
   - `verify` サブエージェントを起動し、lint / フォーマット / 型 / テストを green にする。
   - 設計判断が必要な失敗が残った場合はここで止め、主エージェント／ユーザーに上げる。

3. **docs-check（docs/CLAUDE.md を変更した場合のみ）**
   - 変更ファイルに `docs/` 配下または `CLAUDE.md` が含まれるなら `docs-check` サブエージェントを起動し、index 更新漏れ・リンク切れ・命名・関連仕様リンクを点検する。
   - 含まれないならスキップしてよい。

4. **evaluator（`feature` / `bugfix` / `hotfix` ブランチのみ・省略不可）**
   - ブランチ種別が `feature` / `bugfix` / `hotfix` なら、**必ず** `evaluator` サブエージェントを起動する（受け入れ条件・spec の充足を独立評価。§5.2）。
   - **「単純だから」という理由でスキップしない**。スキップ判断自体が evaluator で排除したい自己評価バイアスに当たる。
   - `refactor` / `docs` / `chore` ブランチ（受け入れ条件を持たない作業）は対象外。スキップしてよい。
   - 必ず **`verify` を green にした後**に実行する。

5. **集約報告**
   - 起動した各ゲートの結果（pass/fail・要対応・要判断）を主エージェントがまとめて報告する。
   - いずれかが FAIL／要対応を返した場合は PR 作成に進まず、主エージェント／ユーザーで対応方針を決める。

## やらないこと

- ルール（起動条件・モデル選定など）の再定義。正本は git-workflow §5.2。
- サブエージェントの判断結果の上書き。skill は起動と集約に徹する。
