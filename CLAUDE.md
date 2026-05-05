# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Tkinter製のyt-dlp GUIダウンローダー。YouTubeなどの動画をMP4（最高画質/720p）またはMP3（音声のみ）でダウンロードできるWindows向けデスクトップアプリ。PyInstallerでスタンドアロンexeとしてビルドする。

## 環境セットアップ

```bash
# 仮想環境の有効化
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 主要コマンド

```bash
# アプリの起動（開発時）
python -m yt_gui

# exeビルド（PyInstaller）
pyinstaller yt.spec

# ビルド成果物は dist/yt/ に出力される
```

## アーキテクチャ

`yt_gui/` パッケージ構成。各ファイルの責務：

- **`yt_gui/i18n.py`** — 多言語対応モジュール。`set_language(lang)` で言語を切り替え、`t(key)` で翻訳文字列を返す。キーが見つからない場合は日本語にフォールバックし、それもなければキー名をそのまま返す。
- **`yt_gui/locales/ja.py`** / **`yt_gui/locales/en.py`** — 各言語の文字列辞書（`STRINGS: dict[str, str]`）。新言語追加時はこのパターンで `xx.py` を追加し、`i18n.py` の `_LANGUAGES` に登録する。
- **`yt_gui/formats.py`** — `FORMAT_SPECS` 定数。内部キー（`"fmt_best_mp4"` など）が辞書のキーで、値が `(yt-dlpフォーマット文字列, 音声のみフラグ)` のタプル。GUI表示名は `i18n.t(key)` で取得する。`FORMAT_KEYS` は表示順を保持したキーのリスト。
- **`yt_gui/downloader.py`** — `Downloader` クラス。yt-dlpのラッパー。`download_video(url, format_id, cookies_path)` でダウンロードを実行し、`_progress_hook` でコールバック経由にGUIへ進捗を通知する。ステータス文字列は `t()` 経由で多言語対応済み。
- **`yt_gui/settings.py`** — `Settings` dataclassと `SettingsManager` クラス。設定をJSONファイルに読み書きする。保存先はOS標準のconfigディレクトリ（Windows: `%APPDATA%/yt-gui/`、macOS: `~/Library/Application Support/yt-gui/`、Linux: `~/.config/yt-gui/`）。`Settings.language`（デフォルト `"ja"`）で使用言語を保存する。
- **`yt_gui/settings_dialog.py`** — `SettingsDialog(tk.Toplevel)` クラス。モーダルの設定画面。`ttk.Notebook` によるタブ構成。一般タブに保存フォルダ・Cookiesファイル・言語選択を配置。言語変更時は再起動を促すダイアログを表示。
- **`yt_gui/app.py`** — `App(tk.Tk)` クラス。Tkinter GUIクラス。`__init__` で設定を読み込んだ直後に `i18n.set_language()` を呼び、以降の全UI文字列は `t()` 経由で取得する。メニューバー（ファイル > 設定.../終了）を持つ。ダウンロード処理は `threading.Thread` で別スレッド実行し、GUIがフリーズしないようにしている。完了後は `self.after(100, ...)` でメインスレッドに戻ってUIをリセット。
- **`yt_gui/__main__.py`** — エントリーポイント。`python -m yt_gui` で起動。
- **`yt_gui/__init__.py`** — `get_resource_base()` ユーティリティ。PyInstallerバンドル時は `sys._MEIPASS`、開発時はプロジェクトルートを返す。

## 新しい言語を追加する手順

1. `yt_gui/locales/xx.py` を作成し `STRINGS: dict[str, str]` を定義する
2. `yt_gui/i18n.py` の `_LANGUAGES` に `"xx": xx.STRINGS` を追加する
3. 全ロケールファイル（`ja.py`, `en.py`, ...）に `"lang_xx": "表示名"` を追加する

## バンドルするバイナリ

- `bin/deno.exe` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `bin/ffmpeg/ffmpeg.exe` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）

`yt.spec` の `binaries` でこれらをexeに同梱するよう設定済み。CookiesファイルはGUIの設定画面でユーザーが任意に指定する（ビルド成果物には含まない）。

バイナリは `scripts/download_binaries.py` で自動取得し `bin/` に配置する（`yt.spec` ビルド時に自動呼び出し）。`--update` フラグを渡すと既存ファイルを強制的に再ダウンロードする。

```bash
python scripts/download_binaries.py --update
```

実行時にCookiesフィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookiesなしでダウンロードを続行する。

## ダウンロード先

実行時は `~/Downloads` フォルダに保存される（`App.__init__` 内で設定）。
