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

- **`yt_gui/formats.py`** — `FORMAT_OPTIONS` 定数。キーがGUI表示テキスト、値が `(yt-dlpフォーマット文字列, 音声のみフラグ)` のタプル。
- **`yt_gui/downloader.py`** — `Downloader` クラス。yt-dlpのラッパー。`download_video(url, format_key, cookies_path)` でダウンロードを実行し、`_progress_hook` でコールバック経由にGUIへ進捗を通知する。
- **`yt_gui/app.py`** — `App(tk.Tk)` クラス。Tkinter GUIクラス。ダウンロード処理は `threading.Thread` で別スレッド実行し、GUIがフリーズしないようにしている。完了後は `self.after(100, ...)` でメインスレッドに戻ってUIをリセット。
- **`yt_gui/__main__.py`** — エントリーポイント。`python -m yt_gui` で起動。
- **`yt_gui/__init__.py`** — `get_resource_base()` ユーティリティ。PyInstallerバンドル時は `sys._MEIPASS`、開発時はプロジェクトルートを返す。

## バンドルするバイナリ

- `bin/deno.exe` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `bin/ffmpeg/ffmpeg.exe` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）
- `cookies.txt` — デフォルトのCookiesファイル（任意・GUIで変更可能）

`yt.spec` の `binaries` でこれらをexeに同梱するよう設定済み。`cookies.txt` はビルド時に存在すれば同梱、なければスキップする（オプション扱い）。

バイナリは `scripts/download_binaries.py` で自動取得し `bin/` に配置する（`yt.spec` ビルド時に自動呼び出し）。

実行時にCookiesフィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookiesなしでダウンロードを続行する。

## ダウンロード先

実行時は `~/Downloads` フォルダに保存される（`App.__init__` 内で設定）。
