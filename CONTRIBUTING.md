# コントリビューションガイド

yt-gui への貢献に興味を持っていただきありがとうございます。
このプロジェクトの開発ルールの**正本は [docs/git-workflow.md](docs/git-workflow.md) と [CLAUDE.md](CLAUDE.md)** です。
本ファイルは入口となる要約で、詳細は各正本を参照してください。

## 開発環境のセットアップ

[uv](https://docs.astral.sh/uv/) を使用します。

```bash
uv sync                       # 依存インストール・仮想環境構築
uv run python -m yt_gui        # アプリ起動（開発時）
```

## 変更前のチェック

PR を出す前に、ローカルで以下がすべて通ることを確認してください（CI でも `Test` ワークフローが同じ内容を実行します）。

```bash
uv run ruff check .                  # Lint（リポジトリ全体）
uv run ruff format --check yt_gui/   # フォーマット
uv run mypy yt_gui/                  # 型チェック
uv run pytest                        # テスト
```

## 開発フロー（要点）

詳細は [docs/git-workflow.md](docs/git-workflow.md) を参照してください。

- **GitHub Flow**: `main` で直接作業せず、`main` からブランチを切って `main` へ PR を出す。
- **Issue ベース**: 機能追加・修正は Issue に基づいて行う（[git-workflow.md §3](docs/git-workflow.md)）。
- **ブランチ命名**: `feature/<issue>-<desc>` / `bugfix/<issue>-<desc>` / `hotfix/<issue>-<desc>`、Issue を伴わない作業は `refactor/<desc>` / `docs/<desc>` / `chore/<desc>`（[§4](docs/git-workflow.md)）。
- **docs 先・テストファースト**: 設計を `docs/spec/` ・ `docs/arch/` に反映してから実装し、テストは仕様に基づいて先に書く（[§5](docs/git-workflow.md)、[テスト方針](docs/testing/policy.md)）。
- **コード変更時は docs も更新**: 対応する `docs/spec/` ・ `docs/arch/` を同時に更新する（[docs-guide.md](docs/docs-guide.md)）。

## 言語

コミットメッセージ・Issue / PR の本文・ドキュメントは原則**日本語**で記述します（[CLAUDE.md 言語ルール](CLAUDE.md#言語ルール)）。

## 行動規範

本プロジェクトへの参加者は [行動規範（CODE_OF_CONDUCT.md）](CODE_OF_CONDUCT.md) を遵守してください。

## セキュリティ

脆弱性の報告は公開 Issue ではなく [SECURITY.md](SECURITY.md) の手順に従ってください。
