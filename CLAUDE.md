# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
# Lint（問題の検出）
uv run ruff check yt_gui/

# Lint + 自動修正
uv run ruff check --fix yt_gui/

# フォーマット（差分確認のみ）
uv run ruff format --check yt_gui/

# フォーマット（適用）
uv run ruff format yt_gui/

# 型チェック
uv run mypy yt_gui/
```

## 主要コマンド

```bash
# アプリの起動（開発時）
uv run python -m yt_gui

# ビルド（PyInstaller）
uv run pyinstaller yt-gui.spec

# ビルド成果物は dist/yt-gui/ に出力される（macOS は dist/yt-gui.app/）

# 依存パッケージの追加
uv add {パッケージ}

# 依存パッケージの削除
uv remove {パッケージ}
```

## スレッド間通信パターン

バックグラウンドスレッドから直接 Qt ウィジェットを操作しないこと。`Signal` / `Slot` を経由してメインスレッドにキューイングすること。シグナル定義・一覧は [docs/arch/app.md](docs/arch/app.md) を参照。

## 仕様書

動作仕様・画面仕様は [`docs/spec/index.md`](docs/spec/index.md) を目次として `docs/spec/` 以下に記載。

> **仕様を変更・拡張するときは、対応する `docs/spec/` のファイルも合わせて更新すること。**

## アーキテクチャ

`yt_gui/` パッケージ構成。各モジュールの詳細は `docs/arch/` 以下を参照。

| ファイル | ドキュメント | 概要 |
|----------|------------|------|
| `yt_gui/__main__.py` / `__init__.py` | [docs/arch/entry.md](docs/arch/entry.md) | エントリーポイント・リソースパス解決 |
| `yt_gui/app.py` | [docs/arch/app.md](docs/arch/app.md) | メインウィンドウ・キュー管理・シグナル定義 |
| `yt_gui/downloader.py` | [docs/arch/downloader.md](docs/arch/downloader.md) | yt-dlp ラッパー・ダウンロード実行 |
| `yt_gui/original_format_panel.py` | [docs/arch/original_format_panel.md](docs/arch/original_format_panel.md) | オリジナル形式パネル |
| `yt_gui/settings_dialog.py` | [docs/arch/settings_dialog.md](docs/arch/settings_dialog.md) | 設定ダイアログ |
| `yt_gui/log_dialog.py` | [docs/arch/log_dialog.md](docs/arch/log_dialog.md) | ログ表示ダイアログ |
| `yt_gui/settings.py` | [docs/arch/settings.md](docs/arch/settings.md) | 設定の読み書き |
| `yt_gui/formats.py` | [docs/arch/formats.md](docs/arch/formats.md) | フォーマット定数・仕様生成関数 |
| `yt_gui/i18n.py` | [docs/arch/i18n.md](docs/arch/i18n.md) | 多言語対応 |
| `yt_gui/locales/` | [docs/arch/locales.md](docs/arch/locales.md) | 言語別文字列辞書 |
| `yt_gui/utils.py` | [docs/arch/utils.md](docs/arch/utils.md) | 共通ユーティリティ |

> モジュールの実装を変更・拡張するときは、対応する `docs/arch/` のファイルも合わせて更新すること。

## 新しい言語を追加する手順

[docs/arch/locales.md](docs/arch/locales.md) 参照。

## バンドルするバイナリ

- `bin/deno[.exe]` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `bin/ffmpeg/ffmpeg[.exe]` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）
- `bin/ffmpeg/ffprobe[.exe]` — 動画メタデータ取得に使用（ffmpegと同じ `ffmpeg_location` から自動検索される）

`yt-gui.spec` の `binaries` でこれらをバイナリに同梱するよう設定済み。CookiesファイルはGUIの設定画面でユーザーが任意に指定する（ビルド成果物には含まない）。

バイナリは `scripts/download_binaries.py` で自動取得し `bin/` に配置する（`yt-gui.spec` ビルド時に自動呼び出し）。`--update` フラグを渡すと既存ファイルを強制的に再ダウンロードする。

```bash
python scripts/download_binaries.py --update
```

`yt-gui.spec` はPySide6向けに設定済み。`pyinstaller-hooks-contrib` がPySide6プラグイン・データを自動検出するため追加設定は最小限。macOS向けビルドでは `BUNDLE` ブロックで `.app` バンドルを自動生成する。

実行時にCookiesフィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookiesなしでダウンロードを続行する。
