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
python yt.py

# exeビルド（PyInstaller）
pyinstaller yt.spec

# ビルド成果物は dist/yt/ に出力される
```

## アーキテクチャ

`yt.py` の単一ファイル構成。2つのクラスで責務を分離している：

- **`Downloader`** — yt-dlpのラッパー。`download_video(url, format_key, cookies_path)` でダウンロードを実行し、`_progress_hook` でコールバック経由にGUIへ進捗を通知する。
- **`App(tk.Tk)`** — Tkinter GUIクラス。ダウンロード処理は `threading.Thread` で別スレッド実行し、GUIがフリーズしないようにしている。完了後は `self.after(100, ...)` でメインスレッドに戻ってUIをリセット。

## 形式オプション (`FORMAT_OPTIONS`)

`yt.py` 冒頭の辞書でyt-dlpのフォーマット指定文字列を管理。キーがGUI表示テキスト、値がyt-dlpの`format`パラメータ。MP3は`postprocessors`でFFmpegを使い変換する。

## バンドルするバイナリ

- `deno.exe` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `ffmpeg/ffmpeg.exe` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）
- `cookies.txt` — デフォルトのCookiesファイル（GUIで変更可能）

`yt.spec` の `binaries` でこれらをexeに同梱するよう設定済み。

## ダウンロード先

実行時は `~/Downloads` フォルダに保存される（`App.__init__` 内で設定）。
