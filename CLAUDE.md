# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 言語ルール

- **入出力は日本語**: ユーザーへの応答・ドキュメント・コミットメッセージ・PR の説明はすべて日本語で記述する。
- **思考は英語**: 推論・計画・内部の思考プロセスは英語で行う。
- **既存スレッドへの追従（例外）**: 既に存在する GitHub Issue / PR の**本文・コメント**が日本語以外で書かれている場合は、そのスレッドの言語に合わせて記述する（外部参加者とのやり取りを成立させるため）。この例外の対象は Issue / PR の本文・コメントに限る。Claude が新規に起票する Issue / PR は日本語をデフォルトとし、ユーザーへのチャット応答・ドキュメント・コミットメッセージは常に日本語とする。

## 調査ルール: docs 先・コード裏取り

新しいタスクの設計・実装に着手する前に、必ず以下の順序でドキュメントを先に確認する。コードの探索（grep / ファイル読み込み）は **docs に書かれている内容の裏取り** として使うこと。

1. このファイル（CLAUDE.md）
2. [docs/task/index.md](docs/task/index.md) — 既存タスクの状況
3. 該当機能の [docs/spec/index.md](docs/spec/index.md) 配下のファイル — 動作仕様・画面仕様
4. 該当モジュールの [docs/arch/index.md](docs/arch/index.md) 配下のファイル — 実装の意図・接続ポイント
5. 上記で当たりを付けた箇所をコードで確認

このリポジトリは spec ↔ arch ↔ コードのマッピングが整備されており、コード変更時は docs も同時更新する運用なので、docs の鮮度は高い前提で読んでよい。docs が薄いトピック、または docs と実装が乖離している箇所を見つけた場合は、コード優先に切り替えたうえで docs の更新も提案すること。

### 調査の委譲

この調査フェーズ（上記 1〜5）は、読み取り専用の **`investigate` サブエージェント（[.claude/agents/investigate.md](.claude/agents/investigate.md)、Sonnet）へ委譲**し、主エージェントは結論（要点・関連 `path:line`・裏取りメモ）だけを受け取ること。大量のファイル読み込みで主エージェントの文脈を占有しないための運用。**設計・実装方針の判断は委譲せず主エージェントが行い、設計外の問題はユーザーに確認する**（[docs/git-workflow.md](docs/git-workflow.md) §5.1）。複数観点での広い探索や、特定ファイルをピンポイントで読むだけの軽い確認は、委譲せず主エージェントが直接行ってよい。

## タスク管理ルール

進行中・未完了のタスクは [docs/task/index.md](docs/task/index.md) で管理する。

> **`未着手` または `進行中` のタスクがある場合は、それらの対応を行うかをユーザーに尋ねること。** 一覧はセッション開始時に [SessionStart hook](.claude/hooks/session_task_status.py) が自動で注入する（[docs/git-workflow.md](docs/git-workflow.md) §5.6）。**注入が見当たらない場合は hook が動いていないので、[docs/task/index.md](docs/task/index.md) を直接読んで確認すること。** タスクを完了したら [docs/docs-guide.md](docs/docs-guide.md) §4.2 の手順で `docs/task/archive/` へアーカイブする。新規タスクが発生した場合は `docs/task/{slug}.md` を作成して index.md にも追記する。

GitHub Issue は「起票・仕様・受け入れ条件の正本」、`docs/task/` は「作業中の設計・進捗メモ」として併用する。両者は相互リンクで紐付ける。詳細は [docs/git-workflow.md](docs/git-workflow.md) を参照。

## Git / GitHub 運用ルール

絶対に守るルール（詳細・ブランチ命名表・Issue 起票テンプレは [docs/git-workflow.md](docs/git-workflow.md)）。

- **`main` で直接作業しない**: 必ず `main` からブランチを切り、`main` へ PR を出す（GitHub Flow）。`main` 上での**ファイル編集**と `git commit` / `git push` は hook がブロックする（[docs/git-workflow.md](docs/git-workflow.md) §1・§5.6）。
- **GitHub 操作は `gh` を使う**: 起票・閲覧・PR 作成は `gh` コマンド経由。
- **Issue ベース開発**: 修正・機能追加は Issue に基づいて行う。Claude が起票する Issue は、AI が単独で実装・完結できる粒度の技術仕様（背景・受け入れ条件・対象ファイル・関連 spec/arch リンク）まで記述する。
- **ブランチ命名**: `feature/<issue>-<desc>` / `bugfix/<issue>-<desc>` / `hotfix/<issue>-<desc>`、Issue を伴わない作業は `refactor/<desc>` / `docs/<desc>` / `chore/<desc>`。
- コミットメッセージは常に日本語。Issue 本文・PR の本文・コメントは[言語ルール](#言語ルール)に従い、原則日本語・既存スレッドが日本語以外なら当該言語に合わせる。
- **評価ゲート（evaluator）モード**: `always`（`always` / `auto` / `off`）。`feature` / `bugfix` / `hotfix` で受け入れ条件・spec の充足を独立評価する `evaluator` の起動可否を決める単一の正本。定義・`auto` の閾値は [docs/git-workflow.md](docs/git-workflow.md) §5.2。
- **設計レビュー（design-review）モード**: `auto`（`always` / `auto` / `off`）。実装前に設計案の妥当性を点検する `design-review`（Opus）の起動可否を決める単一の正本。`auto` は [docs/git-workflow.md](docs/git-workflow.md) §5.5 の構造トリガで発火する。定義・モード表は §5.2。
- **受け入れ条件レビュー（criteria-review）**: 安価な常時運用の助言のためモードを設けない。受け入れ条件を持つ作業（`feature` / `bugfix` / `hotfix`）で用いる（§5.2）。

## Overview

PySide6製のyt-dlp GUIダウンローダー。YouTubeなどの動画をMP4（最高画質/解像度指定）・MP3/FLAC（音声のみ）・オリジナル形式（映像/音声トラックを個別指定）でダウンロードできるWindows / macOS向けデスクトップアプリ。PyInstallerでスタンドアロンバイナリとしてビルドする。

ダウンロードキューを持ち、URLと形式を複数登録してからまとめて実行できる。一時停止・再開にも対応。キューにはURLではなく動画タイトルを表示する。保存先はデフォルト `~/Downloads`（設定画面で変更可能）。プレイリストURLを追加すると、プレイリスト名のサブフォルダを自動作成してそこへ保存する。

## 環境セットアップ

```bash
# 依存パッケージのインストール・仮想環境構築
uv sync

# 仮想環境の有効化
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac
```

## Lint / Format / 型チェック

```bash
# Lint（問題の検出。CI も同じくリポジトリ全体を対象）
uv run ruff check .

# Lint + 自動修正
uv run ruff check --fix .

# フォーマット（差分確認のみ。CI も同じくリポジトリ全体を対象）
uv run ruff format --check .

# フォーマット（適用）
uv run ruff format .

# 型チェック（対象は pyproject.toml の [tool.mypy] files で管理）
uv run mypy
```

## テスト

```bash
# 全テスト実行
uv run pytest

# カバレッジ計測
uv run pytest --cov=yt_gui --cov-report=term-missing
```

テスト方針・対象スコープ・記述ルールは [docs/testing/policy.md](docs/testing/policy.md) を参照。

## 主要コマンド

```bash
# アプリの起動（開発時）
uv run python -m yt_gui

# ビルド（PyInstaller）
uv run pyinstaller yt-gui.spec

# 依存パッケージの追加 / 削除
uv add {パッケージ}
uv remove {パッケージ}
```

ビルドの詳細・バンドルバイナリ構成は [docs/build.md](docs/build.md) を参照。

## スレッド間通信パターン

バックグラウンドスレッドから直接 Qt ウィジェットを操作しないこと。`Signal` / `Slot` を経由してメインスレッドにキューイングすること。シグナル定義・一覧は [docs/arch/app.md](docs/arch/app.md) を参照。

## ドキュメントマップ

詳細は以下の目次から参照する。コード変更時は対応するファイルも合わせて更新すること。

| ドキュメント | 内容 |
|---|---|
| [docs/spec/index.md](docs/spec/index.md) | 動作仕様・画面仕様の目次 |
| [docs/arch/index.md](docs/arch/index.md) | モジュール実装の目次 |
| [docs/build.md](docs/build.md) | PyInstaller ビルド・バンドルバイナリ・CI/セキュリティ設定の詳細 |
| [docs/git-workflow.md](docs/git-workflow.md) | ブランチ運用・Issue ベース開発・PR の詳細ルール |
| [docs/testing/index.md](docs/testing/index.md) | テスト実行コマンド・方針・カバレッジ運用 |
| [docs/task/index.md](docs/task/index.md) | タスクの進捗管理（セッション開始時に必ず確認） |
| [docs/docs-guide.md](docs/docs-guide.md) | CLAUDE.md / docs の更新ルール（ドキュメント編集時に必ず参照） |

> **コードまたは仕様を変更・拡張するときは、対応する `docs/spec/` / `docs/arch/` のファイルも合わせて更新すること。詳細な記載基準は [docs/docs-guide.md](docs/docs-guide.md) に従うこと。**
