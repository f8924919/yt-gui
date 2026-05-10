# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PySide6製のyt-dlp GUIダウンローダー。YouTubeなどの動画をMP4（最高画質/解像度指定）・MP3（音声のみ）・オリジナル形式（映像/音声トラックを個別指定）でダウンロードできるWindows / macOS向けデスクトップアプリ。PyInstallerでスタンドアロンバイナリとしてビルドする。

ダウンロードキューを持ち、URLと形式を複数登録してからまとめて実行できる。一時停止・再開にも対応。キューにはURLではなく動画タイトルを表示する。プレイリストURLを追加すると、プレイリスト名のサブフォルダを自動作成してそこへ保存する。

## 環境セットアップ

```bash
# 依存パッケージのインストール・仮想環境構築
uv sync

# 仮想環境の有効化
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac
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

バックグラウンドスレッドからGUIを安全に更新するため、`Signal` / `Slot` を使用する。Qt のシグナルは別スレッドからemitしても自動的にメインスレッドへキューイングされる（`Qt.QueuedConnection`）ため、Tkinterの `self.after(0, callback)` と同等の安全なGUI更新が実現できる。

- `App` は `_AppSignals(QObject)` 内部クラスを持ち、`status_update(str, float)`・`log_message(str)`・`queue_item_refresh(object)` 等のシグナルを定義する。バックグラウンドワーカーはこれらをemitし、メインスレッドのスロットが受け取る。
- `OriginalFormatPanel` は `_PanelSignals(QObject)` 内部クラスを持ち、フォーマット取得スレッドの成功・失敗をシグナルでメインスレッドへ渡す。

## アーキテクチャ

`yt_gui/` パッケージ構成。各ファイルの責務：

- **`yt_gui/i18n.py`** — 多言語対応モジュール。`set_language(lang)` で言語を切り替え、`t(key)` で翻訳文字列を返す。キーが見つからない場合は日本語にフォールバックし、それもなければキー名をそのまま返す。（変更なし）
- **`yt_gui/locales/ja.py`** / **`yt_gui/locales/en.py`** — 各言語の文字列辞書（`STRINGS: dict[str, str]`）。新言語追加時はこのパターンで `xx.py` を追加し、`i18n.py` の `_LANGUAGES` に登録する。`fmt_720p` / `fmt_mp3` の値はテンプレート文字列（`{resolution}` / `{bitrate}` プレースホルダーを含む）になっており、`App._build_format_display()` が設定値を埋めて表示名を生成する。コンテキストメニュー項目（`ctx_copy_url`・`ctx_edit_format` など）もここに定義する。
- **`yt_gui/formats.py`** — `FORMAT_SPECS` 定数（内部キー → `(yt-dlpフォーマット文字列, 音声のみフラグ)` のタプル）と `FORMAT_KEYS`（表示順リスト）。また `VIDEO_RESOLUTIONS`（`"480"` 〜 `"2160"` のタプル）と `MP3_BITRATES`（`"128"` 〜 `"320"` のタプル）を定義する。（変更なし）
- **`yt_gui/utils.py`** — `strip_ansi(text: str) -> str`。ANSIエスケープコードを除去する共通ユーティリティ。（変更なし）
- **`yt_gui/downloader.py`** — `Downloader` クラス。yt-dlpのラッパー。`__init__` で `video_resolution`・`mp3_bitrate`・`log_callback`・`status_callback` を受け取る。`fetch_title_or_entries()` でURL種別判別（戻り値に `thumbnail_url: str | None` を含む）、`fetch_formats()` でフォーマット一覧取得、`download_video()` でダウンロード実行。`_ffprobe_path` も `_ffmpeg_path` と同様に `bin/ffmpeg/ffprobe[.exe]` として解決し、yt-dlpに渡す。Cookies はファイルパス・ブラウザ名の両方に対応。
- **`yt_gui/settings.py`** — `Settings` dataclassと `SettingsManager` クラス。設定をJSONファイルに読み書きする。保存先はOS標準のconfigディレクトリ（Windows: `%APPDATA%/yt-gui/`、macOS: `~/Library/Application Support/yt-gui/`）。（変更なし）
- **`yt_gui/settings_dialog.py`** — `SettingsDialog(QDialog)` クラス。モーダルの設定画面。`QTabWidget` によるタブ構成（「一般」・「画質・音質」）。「一般」タブに保存フォルダ・Cookies・言語選択を配置。Cookiesは「使用しない / ファイルを指定 / ブラウザから取得」の `QRadioButton` グループで切り替え、選択に応じてファイルパス入力欄（`QLineEdit` + `QFileDialog`）またはブラウザ選択コンボ（`QComboBox`）を `setVisible()` で排他表示する。保存時は非選択側のフィールドを空文字にリセット。言語変更時は再起動なしで即座に反映（`App._retranslate_ui()` を呼び出す）。「画質・音質」タブに解像度上限コンボ（480p〜2160p）とMP3ビットレートコンボ（128〜320kbps）を配置。
- **`yt_gui/log_dialog.py`** — `LogDialog(QDialog)` クラス。非モーダルのログ表示ダイアログ。`QPlainTextEdit`（`setReadOnly(True)`、ダーク背景・等幅フォント）でログを表示する。`load(entries)` で既存ログを一括ロード、`append(text)` で逐次追記。最下部にいれば自動スクロール（`verticalScrollBar().value() == verticalScrollBar().maximum()` で判定）、上にスクロール中は追従しない。クリアボタンはテキストエリアのみを消去し `App._log_entries` は変更しない。ウィンドウクローズ時に `on_close` コールバックで `App._log_dialog` を `None` にリセットする。
- **`yt_gui/original_format_panel.py`** — `OriginalFormatPanel(QGroupBox)` クラス。オリジナル形式の詳細設定パネル。内部に `_PanelSignals(QObject)` を持ち、フォーマット取得スレッドの成功（`formats_fetched(dict)`）・失敗（`fetch_failed(str, bool)`）をシグナル経由でメインスレッドへ安全に渡す。映像コンボ（`QComboBox`）・音声コンボ（`QComboBox`）・字幕リスト（`QListWidget`、`ExtendedSelection`）・字幕フォーマットコンボ（`QComboBox`）・埋め込みチェック（`QCheckBox`）・出力形式ラジオボタン（`QRadioButton` グループ）の構築・状態管理・ロジックを内包する。複合フォーマット（★印）選択時は音声コンボを `setEnabled(False)` で自動無効化。公開API: `get_format_spec()` / `get_subtitle_opts()` / `get_remux_only()` / `has_formats_loaded()` / `get_fetched_title()` / `is_both_skipped()` / `trigger_fetch()` / `retranslate()`。`trigger_fetch()` はプログラムからフォーマット取得スレッドを起動する。`retranslate()` はグループタイトル・ラベル・コンボ固定項目テキストを現在の言語に更新する（yt-dlpから取得したフォーマット名は対象外）。
- **`yt_gui/app.py`** — `App(QMainWindow)` クラス。PySide6メインウィンドウ。内部クラス `_AppSignals(QObject)` に `status_update(str, float)`・`log_message(str)`・`queue_item_refresh(object)` シグナルを定義し、バックグラウンドスレッドからemitしてメインスレッドのスロットで受け取る。`Downloader` の生成はウィジェット構築より先に行う（`OriginalFormatPanel` がコンストラクタで受け取るため）。`_resolve_cookies() -> (cookies_path, cookies_browser)` で設定値をチェックし、ブラウザ設定を優先して返す。`_sanitize_folder_name()` でプレイリスト名をフォルダ名として安全な文字列に変換（無効文字を `_` 置換・100文字截断）。`_QueueItem` dataclassに `playlist_folder`・`remux_only`・`thumbnail_url` フィールドを保持。`_STATUS_KEY_MAP` クラス定数でキュー状態文字列 → ロケールキーのマッピングを管理（`"editing"` を含む）。`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理（`setVisible()` を使用）。`_build_format_display()` が `fmt_720p` / `fmt_mp3` のラベルを設定値から生成。`_on_format_changed` で `OriginalFormatPanel` / `_mp3_frame` を `setVisible()` で切り替え、ウィンドウ高さを `resize()` で調整。プレイリスト追加時は `_sanitize_folder_name(playlist_title)` をサブフォルダ名として各 `_QueueItem.playlist_folder` にセット。キューは `_QueueTree(QTreeWidget)` サブクラスで実装。ツールチップは `viewportEvent` で `QEvent.Type.ToolTip` を捕捉し、`QToolTip.showText(pos, text, widget, rect=self.visualItemRect(item))` で `rect` を渡すことでマウスがアイテム行にいる間は表示を持続させる（`rect` なしだとタイムアウトで消える）。サムネイルがキャッシュ済みの場合は 240×135px の `<img>` タグ（base64 data URI）をツールチップ先頭に挿入する。サムネイルはキューアイテム追加時に `_start_thumbnail_fetch` → `_run_thumbnail_fetch`（バックグラウンドスレッド・`urllib.request`）が非同期取得し、`_thumbnail_cache: dict[str, str]`（URL → data URI）にキャッシュする（`_thumbnail_lock` と `_thumbnail_fetching: set[str]` でスレッド安全に管理）。`_get_thumbnail_b64` がキャッシュ参照インタフェースを提供し `_QueueTree._get_thumbnail_b64_cb` にセットされる。コンテキストメニューは `_QueueTree.contextMenuEvent` で実装。`_context_menu_cb`（形式変更）と `_get_thumbnail_b64_cb`（サムネイル参照）の2コールバックを持つ。「URLをコピー」（複数選択時は改行区切りで `QApplication.clipboard()` へ書き込み）と「形式を変更」（編集モード移行）を提供。アイテムの色リセットは `setData(col, Qt.ItemDataRole.ForegroundRole, None)` で行う（`setForeground(col, QColor())` は黒になるためダークモードで不可）。`_check_dependencies()`: 起動時に `QTimer.singleShot(0, ...)` で ffmpeg・ffprobe・deno の存在チェックを行い、見つからないツールがあれば `QMessageBox.warning()` を表示する。`_retranslate_ui()`: 設定言語変更後に全ウィジェットテキストを現在言語に更新し、フォーマットコンボを再構築して `OriginalFormatPanel.retranslate()` を呼ぶ。`_set_original_format_enabled(enabled: bool)`: `QComboBox.model().item(idx).setFlags(...)` で「オリジナルの形式」コンボ項目を有効/無効化（複数選択編集時にグレーアウト）。`_enter_edit_mode(items)` / `_apply_edit()` / `_cancel_edit()` / `_exit_edit_mode()`: 右クリックコンテキストメニューから起動する編集モード。選択アイテムのステータスを `"editing"` に設定してワーカースレッドによる処理対象から除外し、「追加」ボタンを「変更」に差し替えて形式変更を適用する。ログ機能: `_log_entries: list[str]`（最大2000件）にセッション中の全ログを保持し、`_log(msg)` がタイムスタンプを付与して追記。ダウンローダーからのログは `log_message` シグナル経由でメインスレッドの `_log` スロットに委譲。
- **`yt_gui/__main__.py`** — エントリーポイント。`QApplication` を起動し `App` (QMainWindow) を表示。致命的エラーは `QMessageBox.critical()` で表示。
- **`yt_gui/__init__.py`** — `get_resource_base()` ユーティリティ。PyInstallerバンドル時は `sys._MEIPASS`、開発時はプロジェクトルートを返す。（変更なし）

## 新しい言語を追加する手順

1. `yt_gui/locales/xx.py` を作成し `STRINGS: dict[str, str]` を定義する
2. `yt_gui/i18n.py` の `_LANGUAGES` に `"xx": xx.STRINGS` を追加する
3. 全ロケールファイル（`ja.py`, `en.py`, ...）に `"lang_xx": "表示名"` を追加する

## バンドルするバイナリ

- `bin/deno.exe` — yt-dlpのJavaScriptランタイム（`js_runtimes`オプションで指定）
- `bin/ffmpeg/ffmpeg.exe` — 動画結合・音声変換に使用（`ffmpeg_location`で指定）
- `bin/ffmpeg/ffprobe.exe` — 動画メタデータ取得に使用（ffmpegと同じ `ffmpeg_location` から自動検索される）

`yt-gui.spec` の `binaries` でこれらをexeに同梱するよう設定済み。CookiesファイルはGUIの設定画面でユーザーが任意に指定する（ビルド成果物には含まない）。

バイナリは `scripts/download_binaries.py` で自動取得し `bin/` に配置する（`yt-gui.spec` ビルド時に自動呼び出し）。`--update` フラグを渡すと既存ファイルを強制的に再ダウンロードする。

```bash
python scripts/download_binaries.py --update
```

`yt-gui.spec` はTkinter/Tcl-Tk関連のデータ収集コードを削除し、PySide6向けに更新する。`pyinstaller-hooks-contrib` がPySide6プラグイン・データを自動検出するため追加設定は最小限。macOS向けビルドでは従来と同様に `BUNDLE` ブロックで `.app` バンドルを自動生成する。

```bash
uv run pyinstaller yt-gui.spec
```

実行時にCookiesフィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookiesなしでダウンロードを続行する。

## ダウンロード先

実行時は `~/Downloads` フォルダに保存される（設定画面で変更可能）。プレイリストの場合はその下にプレイリスト名のサブフォルダが自動作成される。
