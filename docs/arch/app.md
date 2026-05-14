# yt_gui/app.py

## クラス: `App(QMainWindow)`

PySide6 メインウィンドウ。アプリケーションのエントリーポイントから生成される。

## シグナル（内部クラス `_AppSignals(QObject)`）

| シグナル | 引数 | 用途 |
|----------|------|------|
| `status_update` | `str, float` | ステータスバー更新 |
| `log_message` | `str` | ログ追記 |
| `queue_item_refresh` | `object` | キューアイテムの表示更新 |

バックグラウンドスレッドからこれらを emit し、メインスレッドのスロットで受け取る。

## 初期化順序の注意

`Downloader` の生成はウィジェット構築より先に行う（`OriginalFormatPanel` がコンストラクタで受け取るため）。

## 内部クラス: `_QueueItem`（dataclass）

| フィールド | 説明 |
|-----------|------|
| `playlist_folder` | プレイリスト用サブフォルダ名 |
| `remux_only` | リマックスのみフラグ |
| `thumbnail_url` | サムネイル URL |
| `audio_codec` | 音声コーデック |
| `video_container` | 映像コンテナ |
| `embed_metadata` | メタデータ埋め込みフラグ |
| `embed_chapters` | チャプター埋め込みフラグ |
| `orig_settings` | エンキュー時のスナップショット（編集モード復元用） |

## 内部クラス: `_QueueTree(QTreeWidget)`

キュー表示。以下を独自実装:

- **ツールチップ**: `viewportEvent` で `QEvent.Type.ToolTip` を捕捉。`QToolTip.showText()` に `rect=self.visualItemRect(item)` を渡してマウスがアイテム行にいる間は持続表示（`rect` なしだとタイムアウトで消える）。サムネイルがキャッシュ済みなら 240×135px の `<img>`（base64 data URI）をツールチップ先頭に挿入。
- **コンテキストメニュー**: `contextMenuEvent` で実装。「URL をコピー」（複数選択時は改行区切りで `QApplication.clipboard()` へ書き込み）と「形式を変更」（編集モード移行）を提供。
- **アイテム色リセット**: `setData(col, Qt.ItemDataRole.ForegroundRole, None)` を使用（`setForeground(col, QColor())` は黒固定になりダークモード非対応）。

## サムネイル非同期取得

`_start_thumbnail_fetch` → `_run_thumbnail_fetch`（バックグラウンドスレッド・`urllib.request`）で非同期取得し、`_thumbnail_cache: dict[str, str]`（URL → base64 data URI）にキャッシュ。`_thumbnail_lock` と `_thumbnail_fetching: set[str]` でスレッド安全に管理。

## 主要メソッド

### `_resolve_cookies() -> tuple[str, str]`

設定値を確認し `(cookies_path, cookies_browser)` を返す。ブラウザ設定を優先。

### `_sanitize_folder_name(name: str) -> str`

プレイリスト名をフォルダ名として安全な文字列に変換（無効文字を `_` 置換・100文字截断）。

### `_build_format_display()`

`fmt_720p` / `fmt_mp3` / `fmt_best_mp4` のラベルを設定値から生成。`audio_format` が `"flac"` のときは `fmt_flac` キーを使用。

### `_on_format_changed()`

`OriginalFormatPanel` / `_mp3_frame`（MP3 時のみ表示）を `setVisible()` で切り替え、ウィンドウ高さを `resize()` で調整（オリジナル形式選択時は `_WIN_H_EXPANDED`）。

### `_retranslate_ui()`

フォーマットコンボ更新後に `_on_format_changed()` を呼んで表示を同期。言語切り替え時に `SettingsDialog` から呼ばれる。

### `_check_dependencies()`

起動時に `QTimer.singleShot(0, ...)` で ffmpeg・ffprobe・deno の存在チェック。見つからないツールがあれば `QMessageBox.warning()` を表示。

### `_set_original_format_enabled(enabled: bool)`

`QComboBox.model().item(idx).setFlags(...)` で「オリジナルの形式」コンボ項目を有効/無効化（複数選択編集時にグレーアウト）。

### 編集モード関連

| メソッド | 説明 |
|----------|------|
| `_enter_edit_mode(items)` | ステータスを `"editing"` にしてワーカー対象から除外、「追加」ボタンを「変更」に差し替え |
| `_apply_edit()` | 各形式に応じて `embed_metadata`・`embed_chapters`・`video_container`・`orig_settings` を書き込む |
| `_cancel_edit()` | 編集を破棄して通常モードに戻る |
| `_exit_edit_mode()` | 共通後処理 |

単一の ORIGINAL_KEY アイテムを編集モードに入れた場合は `_original_panel.restore_from_settings(item.orig_settings)` で前回の設定を復元。

## ログ機能

- `_log_entries: list[str]`（最大 2000 件）にセッション中の全ログを保持
- `_log(msg)` がタイムスタンプを付与して追記
- ダウンローダーからのログは `log_message` シグナル経由でメインスレッドの `_log` スロットに委譲

## キュー状態管理

`_STATUS_KEY_MAP` クラス定数でキュー状態文字列 → ロケールキーのマッピングを管理（`"editing"` を含む）。

`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理（`setVisible()` を使用）。
