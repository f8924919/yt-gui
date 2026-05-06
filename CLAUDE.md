# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Tkinter製のyt-dlp GUIダウンローダー。YouTubeなどの動画をMP4（最高画質/解像度指定）・MP3（音声のみ）・オリジナル形式（映像/音声トラックを個別指定）でダウンロードできるWindows / macOS向けデスクトップアプリ。PyInstallerでスタンドアロンバイナリとしてビルドする。

ダウンロードキューを持ち、URLと形式を複数登録してからまとめて実行できる。一時停止・再開にも対応。キューにはURLではなく動画タイトルを表示する。

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

# ビルド（PyInstaller）
pyinstaller yt-gui.spec

# ビルド成果物は dist/yt-gui/ に出力される（macOS は dist/yt-gui.app/）
```

## アーキテクチャ

`yt_gui/` パッケージ構成。各ファイルの責務：

- **`yt_gui/i18n.py`** — 多言語対応モジュール。`set_language(lang)` で言語を切り替え、`t(key)` で翻訳文字列を返す。キーが見つからない場合は日本語にフォールバックし、それもなければキー名をそのまま返す。
- **`yt_gui/locales/ja.py`** / **`yt_gui/locales/en.py`** — 各言語の文字列辞書（`STRINGS: dict[str, str]`）。新言語追加時はこのパターンで `xx.py` を追加し、`i18n.py` の `_LANGUAGES` に登録する。`fmt_720p` / `fmt_mp3` の値はテンプレート文字列（`{resolution}` / `{bitrate}` プレースホルダーを含む）になっており、`App._build_format_display()` が設定値を埋めて表示名を生成する。
- **`yt_gui/formats.py`** — `FORMAT_SPECS` 定数（内部キー → `(yt-dlpフォーマット文字列, 音声のみフラグ)` のタプル）と `FORMAT_KEYS`（表示順リスト）。また `VIDEO_RESOLUTIONS`（`"480"` 〜 `"2160"` のタプル）と `MP3_BITRATES`（`"128"` 〜 `"320"` のタプル）を定義し、設定ダイアログの選択肢として使用する。`fmt_720p` の spec と `fmt_mp3` のビットレートは実行時に設定値から動的に決定されるため、`FORMAT_SPECS` の値はデフォルトの参考値に過ぎない。
- **`yt_gui/downloader.py`** — `Downloader` クラス。yt-dlpのラッパー。`__init__` で `video_resolution`（デフォルト `"720"`）と `mp3_bitrate`（デフォルト `"192"`）を受け取り属性として保持する。`fetch_title_or_entries(url, cookies_path)` で URL が単独動画かプレイリストかを自動判別し、単独の場合は `{'type': 'single', 'url': ..., 'title': ...}`、プレイリストの場合は `{'type': 'playlist', 'entries': [...]}` を返す（`extract_flat='in_playlist'` で高速取得）。`fetch_formats(url, cookies_path)` で `extract_info(download=False)` を呼び、映像/音声/字幕フォーマットと動画タイトルを `{"title": ..., "video": [...], "audio": [...], "subtitles": [...]}` で返す。字幕は手動字幕を先に列挙し、自動生成字幕は動画の主言語に合致するものだけに絞る。`download_video(url, format_id, cookies_path, format_spec=None, subtitle_opts=None, mp3_bitrate_override=None)` でダウンロードを実行。`format_spec` を渡すと `FORMAT_SPECS` より優先し、`is_audio` は常に `format_id` から `FORMAT_SPECS` を参照して決定する。`fmt_720p` は `format_spec` が `None` の場合のみ `video_resolution` から spec を組み立てる。`mp3_bitrate_override` が渡された場合はそちらを優先し、なければ `self.mp3_bitrate` を使用する。`subtitle_opts` を渡すと字幕ダウンロード設定（`writesubtitles` / `writeautomaticsub` / `subtitleslangs` / `subtitlesformat` / `embed`）を `ydl_opts` に適用する。`_progress_hook` でコールバック経由にGUIへ進捗を通知する。
- **`yt_gui/settings.py`** — `Settings` dataclassと `SettingsManager` クラス。設定をJSONファイルに読み書きする。保存先はOS標準のconfigディレクトリ（Windows: `%APPDATA%/yt-gui/`、macOS: `~/Library/Application Support/yt-gui/`、Linux: `~/.config/yt-gui/`）。フィールド: `cookies_path`、`download_path`（空文字のとき `~/Downloads`）、`language`（デフォルト `"ja"`）、`video_resolution`（デフォルト `"720"`）、`mp3_bitrate`（デフォルト `"192"`）。
- **`yt_gui/settings_dialog.py`** — `SettingsDialog(tk.Toplevel)` クラス。モーダルの設定画面。`ttk.Notebook` によるタブ構成。「一般」タブに保存フォルダ・Cookiesファイル・言語選択を配置。「画質・音質」タブに解像度上限コンボ（480p〜2160p）と MP3ビットレートコンボ（128〜320kbps）を配置し、「最高画質」と「オリジナルの形式」には影響しない旨を注記する。言語変更時は再起動を促すダイアログを表示。
- **`yt_gui/app.py`** — `App(tk.Tk)` クラス。Tkinter GUIクラス。`__init__` で設定を読み込んだ直後に `i18n.set_language()` を呼び、以降の全UI文字列は `t()` 経由で取得する。`_build_format_display()` が `fmt_720p` / `fmt_mp3` のラベルを `Settings.video_resolution` / `Settings.mp3_bitrate` の現在値から生成し、設定保存後にフォーマットコンボボックスを再描画する。メニューバー（ファイル > 設定.../終了）を持つ。「オリジナルの形式」選択時は `_original_frame`（LabelFrame）を `grid` で表示し、ウィンドウ高さを拡張する。`_start_fetch_formats_thread` / `_populate_format_combos` で映像/音声/字幕コンボを非同期に更新する（`fetch_formats` から返されたタイトルを `_fetched_title` にキャッシュする）。**ダウンロードキュー**は `_QueueItem` dataclass（`url` / `format_id` / `format_label` / `format_spec` / `subtitle_opts` / `title` / `mp3_bitrate` / `status` / `tree_iid`）のリスト `_queue_items` で管理し、`_queue_lock`（`threading.Lock`）で保護する。「追加」ボタン（`_add_url`）は単独/プレイリストを自動判別し、バックグラウンドスレッドで `fetch_title_or_entries()` を呼び出してタイトルを取得してからキューに追加する（`fmt_original` 選択済みでフォーマット取得済みの場合はキャッシュタイトルを使って即時追加）。Treeviewのタイトル列には動画タイトルを表示する。キュー追加時に `fmt_720p` は `format_spec` を解決してスナップショット、`fmt_mp3` は `mp3_bitrate` をスナップショットする（設定変更が既存キューアイテムに影響しないようにするため）。`fmt_original` 選択時はプレイリスト追加を禁止（format_id が動画ごとに異なるため）。「ダウンロード開始」で `_worker` スレッドを起動し待機アイテムを逐次処理する。「一時停止」を押すと `_paused=True` になり、現在のダウンロード完了後にワーカーが終了する。`_showing_pause_button` フラグで開始/一時停止ボタンの表示状態を管理し、`_swap_to_pause_button` / `_swap_to_start_button` で pack/pack_forget を行う。Treeviewの更新は全て `self.after(0, self._refresh_tree_item, item)` 経由でメインスレッドに委譲する。追加成功時はURL入力欄をクリアする。
- **`yt_gui/__main__.py`** — エントリーポイント。`python -m yt_gui` で起動。
- **`yt_gui/__init__.py`** — `get_resource_base()` ユーティリティ。PyInstallerバンドル時は `sys._MEIPASS`、開発時はプロジェクトルートを返す。

## 新しい言語を追加する手順

1. `yt_gui/locales/xx.py` を作成し `STRINGS: dict[str, str]` を定義する
2. `yt_gui/i18n.py` の `_LANGUAGES` に `"xx": xx.STRINGS` を追加する
3. 全ロケールファイル（`ja.py`, `en.py`, ...）に `"lang_xx": "表示名"` を追加する

## バンドルするバイナリ

- `bin/deno.exe` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `bin/ffmpeg/ffmpeg.exe` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）

`yt-gui.spec` の `binaries` でこれらをexeに同梱するよう設定済み。CookiesファイルはGUIの設定画面でユーザーが任意に指定する（ビルド成果物には含まない）。

バイナリは `scripts/download_binaries.py` で自動取得し `bin/` に配置する（`yt-gui.spec` ビルド時に自動呼び出し）。`--update` フラグを渡すと既存ファイルを強制的に再ダウンロードする。

```bash
python scripts/download_binaries.py --update
```

実行時にCookiesフィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookiesなしでダウンロードを続行する。

## ダウンロード先

実行時は `~/Downloads` フォルダに保存される（設定画面で変更可能）。
