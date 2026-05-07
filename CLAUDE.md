# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Tkinter製のyt-dlp GUIダウンローダー。YouTubeなどの動画をMP4（最高画質/解像度指定）・MP3（音声のみ）・オリジナル形式（映像/音声トラックを個別指定）でダウンロードできるWindows / macOS向けデスクトップアプリ。PyInstallerでスタンドアロンバイナリとしてビルドする。

ダウンロードキューを持ち、URLと形式を複数登録してからまとめて実行できる。一時停止・再開にも対応。キューにはURLではなく動画タイトルを表示する。プレイリストURLを追加すると、プレイリスト名のサブフォルダを自動作成してそこへ保存する。

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
- **`yt_gui/utils.py`** — `strip_ansi(text: str) -> str`。ANSI エスケープコードを正規表現で除去する共通ユーティリティ。yt-dlp の進捗文字列やエラーメッセージから色付けコードを取り除くために `app.py` と `original_format_panel.py` で使用する。
- **`yt_gui/downloader.py`** — `Downloader` クラス。yt-dlpのラッパー。`__init__` で `video_resolution`（デフォルト `"720"`）と `mp3_bitrate`（デフォルト `"192"`）を受け取り属性として保持する。`_cookies_opts(cookies_path, cookies_browser) -> dict` でCookies設定を構築（ブラウザ優先）し、`_base_ydl_opts()` で全メソッド共通のyt-dlp基底オプション（JSランタイム・ffmpeg・Cookies）を返す。`fetch_title_or_entries(url, cookies_path, cookies_browser)` で URL が単独動画かプレイリストかを自動判別し、単独の場合は `{'type': 'single', 'url': ..., 'title': ...}`、プレイリストの場合は `{'type': 'playlist', 'entries': [...], 'title': str}` を返す（`extract_flat='in_playlist'` で高速取得）。`fetch_formats(url, cookies_path, cookies_browser)` で `extract_info(download=False)` を呼び、映像/音声/字幕フォーマットと動画タイトルを `{"title": ..., "video": [...], "audio": [...], "subtitles": [...]}` で返す（`noplaylist: True` のためプレイリストURLではエラーになる）。音声フォーマットのラベルには言語コードを `[ja]` 形式で付加する（情報がある場合のみ）。字幕は手動字幕を先に列挙し、自動生成字幕は動画の主言語に合致するものだけに絞る。`download_video(url, format_id, cookies_path, format_spec, subtitle_opts, mp3_bitrate_override, embed_thumbnail, remux_only, output_dir_override, cookies_browser)` でダウンロードを実行。`output_dir_override` を渡すとプレイリストのサブフォルダ等に出力先を切り替えられる。ダウンロード前に `prepare_filename()` で期待出力パスを確認し、重複時は `(N)` サフィックスを付与。`'color': 'no_color'` オプションでyt-dlpの進捗文字列からANSIコードを排除する。`_progress_hook` でコールバック経由にGUIへ進捗を通知する。
- **`yt_gui/original_format_panel.py`** — `OriginalFormatPanel(ttk.LabelFrame)` クラス。オリジナル形式の詳細設定パネル。映像コンボ・音声コンボ・字幕リストボックス・出力形式ラジオボタンの構築・状態管理・ロジックをすべて内包し、`App` 側は公開メソッド経由で結果だけを受け取る。公開 API: `get_format_spec()` / `get_subtitle_opts()` / `get_remux_only()` / `has_formats_loaded()` / `get_fetched_title()` / `is_both_skipped()`。形式取得は `_start_fetch_thread()` でバックグラウンドスレッドを起動し、`self.after(0, callback)` でGUIを安全に更新する。プレイリストURLを入力して形式取得を試みた場合（エラー文字列に `"playlist"` が含まれる場合）は、エラーダイアログではなく分かりやすい警告ダイアログを表示する。映像/音声コンボには `[自動, スキップ, フォーマット1, ...]` の順で値を設定し、`_format_index()` がオフセット -2 でフォーマットリストのインデックスに変換する。複合フォーマット（★印）選択時は音声コンボを自動無効化する。
- **`yt_gui/settings.py`** — `Settings` dataclassと `SettingsManager` クラス。設定をJSONファイルに読み書きする。保存先はOS標準のconfigディレクトリ（Windows: `%APPDATA%/yt-gui/`、macOS: `~/Library/Application Support/yt-gui/`、Linux: `~/.config/yt-gui/`）。フィールド: `cookies_path`、`cookies_browser`（ブラウザ名、空文字のとき未使用）、`download_path`（空文字のとき `~/Downloads`）、`language`（デフォルト `"ja"`）、`video_resolution`（デフォルト `"720"`）、`mp3_bitrate`（デフォルト `"192"`）。
- **`yt_gui/settings_dialog.py`** — `SettingsDialog(tk.Toplevel)` クラス。モーダルの設定画面。`ttk.Notebook` によるタブ構成。「一般」タブに保存フォルダ・Cookies・言語選択を配置。Cookies は「使用しない / ファイルを指定 / ブラウザから取得」のラジオボタンで切り替え、選択に応じてファイルパス入力欄またはブラウザ選択コンボを表示する（排他）。保存時は非選択側のフィールドを空文字にリセットする。「画質・音質」タブに解像度上限コンボ（480p〜2160p）と MP3ビットレートコンボ（128〜320kbps）を配置し、「最高画質」と「オリジナルの形式」には影響しない旨を注記する。言語変更時は再起動を促すダイアログを表示。
- **`yt_gui/app.py`** — `App(tk.Tk)` クラス。Tkinter GUIクラス。`__init__` で設定を読み込んだ直後に `i18n.set_language()` を呼び、以降の全UI文字列は `t()` 経由で取得する。`Downloader` の生成はウィジェット構築より先に行う（`OriginalFormatPanel` がコンストラクタで受け取るため）。`_resolve_cookies() -> (cookies_path, cookies_browser)` で設定値をチェックし、ブラウザ設定を優先して返す（ファイルが存在しない場合は `None` に変換）。`_sanitize_folder_name()` モジュール関数でプレイリスト名をフォルダ名として安全な文字列に変換（無効文字を `_` 置換・100文字截断）。`_QueueItem` dataclass に `playlist_folder`（プレイリスト時のサブフォルダ名）と `remux_only` フィールドを持つ。`_STATUS_KEY_MAP` クラス定数でキュー状態文字列 → ロケールキーのマッピングを管理する。`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理する。`_build_format_display()` が `fmt_720p` / `fmt_mp3` のラベルを `Settings.video_resolution` / `Settings.mp3_bitrate` の現在値から生成し、設定保存後にフォーマットコンボボックスを再描画する。`_on_format_changed` で `OriginalFormatPanel` を `grid` / `grid_remove` で切り替え表示する。プレイリスト追加時は `_sanitize_folder_name(playlist_title)` をサブフォルダ名として各 `_QueueItem.playlist_folder` にセットし、ダウンローダー呼び出し時に `output_dir_override` として渡す。Treeviewの更新は全て `self.after(0, self._refresh_tree_item, item)` 経由でメインスレッドに委譲する。
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

実行時は `~/Downloads` フォルダに保存される（設定画面で変更可能）。プレイリストの場合はその下にプレイリスト名のサブフォルダが自動作成される。
