# yt_gui/app.py

> 関連仕様: [メインウィンドウ](../spec/screens/main-window.md) ・ [ダウンロードキュー](../spec/features/queue.md)

## クラス: `App(QMainWindow)`

PySide6 メインウィンドウ。アプリケーションのエントリーポイントから生成される。

## スレッド間通信パターン

バックグラウンドスレッドから Qt ウィジェットを直接操作してはならない。必ず `Signal` / `Slot` を経由してメインスレッドにキューイングする。Qt シグナルは別スレッドから emit しても自動的に `Qt.QueuedConnection` でメインスレッドへ配送される。

## シグナル（内部クラス `_AppSignals(QObject)`）

| シグナル | 引数 | 用途 |
|----------|------|------|
| `status_update` | `str, float` | ステータスバー更新（テキスト・進捗） |
| `log_message` | `str` | ログ追記 |
| `queue_item_refresh` | `object (_QueueItem)` | キューアイテムの表示更新 |
| `add_button_reset` | — | 「追加」ボタンを通常状態に戻す |
| `fetch_for_add_done` | `object (dict)` | タイトル取得完了・エンキュー処理をメインスレッドで行う |
| `worker_done` | — | ワーカースレッド終了通知 |
| `show_error` | `str, str` | エラーダイアログ表示（title, message） |
| `show_warning` | `str, str` | 警告ダイアログ表示（title, message） |

`OriginalFormatPanel` も同様に内部クラス `_PanelSignals(QObject)` でシグナルを定義する（詳細は [original_format_panel.md](original_format_panel.md) 参照）。

## 初期化順序の注意

`Downloader` の生成はウィジェット構築より先に行う（`OriginalFormatPanel` がコンストラクタで受け取るため）。

## 内部クラス: `_QueueItem`（dataclass）

実行設定 (format_spec / embed_* / audio_codec / video_container / subtitle_opts / nico_comments 等) は `JobSpec` ([job_spec.md](job_spec.md)) に集約済みで、`_QueueItem` はキュー固有の情報のみを保持する。

| フィールド | 説明 |
|-----------|------|
| `url` | ダウンロード対象 URL |
| `title` | 動画タイトル (キューに表示) |
| `format_label` | フォーマット表示用ラベル (例: `"音声のみ → MP3 192kbps"`) |
| `job` | `JobSpec` — 実行設定一式 |
| `playlist_title` | プレイリスト名 (プレイリスト要素のみ) |
| `playlist_index` | プレイリスト内番号 (プレイリスト要素のみ) |
| `thumbnail_url` | サムネイル URL |
| `status` | `waiting` / `downloading` / `done` / `error` / `editing` |
| `tree_item` | 対応する `QTreeWidgetItem` |
| `format_id` (property) | `job.format_id` のエイリアス |

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
| `_apply_edit()` | `build_job_spec()` で新しい `JobSpec` を生成し、編集中アイテムの `item.job` を差し替える |
| `_cancel_edit()` | 編集を破棄して通常モードに戻る |
| `_exit_edit_mode()` | 共通後処理 |

単一の ORIGINAL_KEY アイテムを編集モードに入れた場合は `_original_panel.restore_from_settings(item.job.orig_settings)` で前回の設定を復元。

### キュー追加経路

- `_add_url()` で `build_job_spec()` を呼び出して `JobSpec` を組み立て、URL 取得スレッドへ渡す。`fmt_original` のときは `_original_panel.get_snapshot()` で UI 非依存の `PanelSnapshot` を作って渡す。
- `_on_fetch_for_add_done(payload)` の payload 構造は `{"result": ..., "job": JobSpec, "format_label": str}`。単発・プレイリストとも同一 `JobSpec` を全エントリで共有する。
- `_enqueue_single(url, title, format_label, job, *, thumbnail_url)` は `_QueueItem` を生成してキューへ追加するのみ。format_id 派生は build_job_spec 側で完結している。
- `_notify_container_promotion_if_needed(job)`: 複数音声で MKV 昇格が起きた場合のステータス通知。`build_job_spec` は UI 通知を行わないため UI 側で発火する。

## ログ機能

- `_log_entries: list[str]`（最大 2000 件）にセッション中の全ログを保持
- `_log(msg)` がタイムスタンプを付与して追記
- ダウンローダーからのログは `log_message` シグナル経由でメインスレッドの `_log` スロットに委譲

## キュー状態管理

`_STATUS_KEY_MAP` クラス定数でキュー状態文字列 → ロケールキーのマッピングを管理（`"editing"` を含む）。

`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理（`setVisible()` を使用）。
