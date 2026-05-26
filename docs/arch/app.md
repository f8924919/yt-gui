# yt_gui/app.py

> 関連仕様: [メインウィンドウ](../spec/screens/main-window.md) ・ [ダウンロードキュー](../spec/features/queue.md)

## クラス: `App(QMainWindow)`

PySide6 メインウィンドウ。アプリケーションのエントリーポイントから生成される。

リファクタリング後の責務は **ウィジェット組み立てとシグナル配線** に絞られている。具体的な振る舞いは以下の専用クラスに移譲する。

| 責務 | 移譲先 |
|---|---|
| キュー所有・ワーカースレッド・編集モード状態機械 | [`QueueController`](queue_controller.md) |
| サムネイル画像の非同期取得・キャッシュ | [`ThumbnailCache`](thumbnail_cache.md) |
| `format_id` 派生ロジック | [`build_job_spec`](job_spec.md) |
| yt-dlp 呼び出し | [`Downloader`](downloader.md) |
| オリジナル形式パネル | [`OriginalFormatPanel`](original_format_panel.md) |

## スレッド間通信パターン

バックグラウンドスレッドから Qt ウィジェットを直接操作してはならない。必ず `Signal` / `Slot` を経由してメインスレッドにキューイングする。Qt シグナルは別スレッドから emit しても自動的に `Qt.QueuedConnection` でメインスレッドへ配送される。

## シグナル（内部クラス `_AppSignals(QObject)`）

ワーカーキュー由来のシグナルは `QueueController` に移管済み。URL タイトル取得スレッドは [`threading_utils.run_in_thread`](threading_utils.md) に移行したため、`_AppSignals` には汎用ハンドラだけが残る。

| シグナル | 引数 | 用途 |
|----------|------|------|
| `status_update` | `str, float` | ステータスバー更新（テキスト・進捗） |
| `log_message` | `str` | ログ追記 |
| `show_error` | `str, str` | エラーダイアログ表示（title, message） |

URL タイトル取得 (`_start_add_thread`) は `run_in_thread` の `on_done` / `on_failed` / `on_finished` コールバックでメインスレッドの UI 操作を完結させる。`on_failed` 内で `_update_status` / `_log` / `QMessageBox.critical` を直接呼び、`on_finished` で「追加」ボタンを再有効化する。

`OriginalFormatPanel` も同じパターンで `run_in_thread` を使う（詳細は [original_format_panel.md](original_format_panel.md) 参照）。

## 初期化順序

1. `Settings` 読み込み・i18n 初期化
2. `Downloader` 生成
3. `ThumbnailCache` 生成
4. `_create_menu()` / `_create_widgets()` → `_queue_tree` を含むウィジェット構築
5. `QueueController` 生成（引数: `downloader`, `queue_tree`）
6. `_wire_queue_signals()` でコントローラのシグナルをスロットに配線

`QueueController` は `_queue_tree` 構築後にしか作れないため、`_create_widgets()` の後で生成する。`_QueueTree` の `_get_item_cb` などのコールバックには `lambda ti: self.queue.find_item_for(ti)` の形で遅延参照を仕込んである。

## 内部クラス: `_QueueTree(QTreeWidget)`

キュー表示。以下を独自実装:

- **ツールチップ**: `viewportEvent` で `QEvent.Type.ToolTip` を捕捉。`QToolTip.showText()` に `rect=self.visualItemRect(item)` を渡してマウスがアイテム行にいる間は持続表示（`rect` なしだとタイムアウトで消える）。サムネイルがキャッシュ済みなら 240×135px の `<img>`（base64 data URI）をツールチップ先頭に挿入。`_get_thumbnail_b64_cb` には `ThumbnailCache.get` を直接バインドする。
- **コンテキストメニュー**: `contextMenuEvent` で実装。「URL をコピー」（複数選択時は改行区切りで `QApplication.clipboard()` へ書き込み）と「形式を変更」（編集モード移行）を提供。「形式を変更」は `_context_menu_cb = self._enter_edit_mode` に紐付き、`QueueController.enter_edit_mode(items)` を呼ぶ。
- **アイテム色リセット**: `setData(col, Qt.ItemDataRole.ForegroundRole, None)` を使用（`setForeground(col, QColor())` は黒固定になりダークモード非対応）。

## キュー追加経路

- `_add_url()` で `build_job_spec()` を呼び出して `JobSpec` を組み立て、URL 取得スレッドへ渡す。`fmt_original` のときは `_original_panel.get_snapshot()` で UI 非依存の `PanelSnapshot` を作って渡す。
- `_on_fetch_for_add_done(payload)` の payload 構造は `{"result": ..., "job": JobSpec, "format_label": str}`。単発は `self.queue.enqueue_single(...)`、プレイリストは `self.queue.enqueue_playlist(...)` に委譲。
- `_on_queue_item_added(item)` スロット: `QueueController.item_added` シグナルを受けて `self._thumbnail_cache.request(item.thumbnail_url)` を起動する。
- `_notify_container_promotion_if_needed(job)`: 複数音声で MKV 昇格が起きた場合のステータス通知。`build_job_spec` は UI 通知を行わないため UI 側で発火する。

## 編集モード経路

| メソッド / スロット | 説明 |
|---|---|
| `_enter_edit_mode(items)` | `QueueController.enter_edit_mode(items)` を呼ぶだけ |
| `_on_edit_mode_entered(items)` | `edit_mode_entered` シグナルのスロット。URL 入力欄・フォーマットコンボ・MP3 サムネチェック・パネル復元・ボタン状態・ステータスバーなどの UI 側操作を実施 |
| `_apply_edit()` | UI から `format_label` と `JobSpec` を組み立てて `QueueController.apply_edit(...)` に渡す |
| `_cancel_edit()` | `QueueController.cancel_edit()` を呼ぶだけ |
| `_on_edit_mode_exited()` | `edit_mode_exited` シグナルのスロット。UI を通常モードに戻す |

単一 ORIGINAL_KEY アイテムを編集モードに入れた場合は `_original_panel.restore_from_settings(item.job.orig_settings)` で前回の設定を復元する。

## 主要メソッド

### `_resolve_cookies() -> tuple[str | None, str | None]`

設定値を確認し `(cookies_path, cookies_browser)` を返す。ブラウザ設定を優先。`QueueController.start()` に渡されてワーカー内で毎イテレーション呼ばれる（生きた設定変更を反映するため）。

### `_build_format_display()`

`fmt_720p` / `fmt_mp3` / `fmt_best_mp4` のラベルを設定値から生成。`audio_format` が `"flac"` のときは `fmt_flac` キーを使用。

### `_on_format_changed()`

`OriginalFormatPanel` / `_mp3_frame`（MP3 時のみ表示）を `setVisible()` で切り替え、ウィンドウ高さを `resize()` で調整（オリジナル形式選択時は `_WIN_H_EXPANDED`）。

### `_retranslate_ui()`

フォーマットコンボ更新後に `_on_format_changed()` を呼んで表示を同期。言語切り替え時に `SettingsDialog` から呼ばれる。キュー行の再描画は `self.queue.refresh_all_tree_items()` に委譲。

### `_check_dependencies()`

起動時に `QTimer.singleShot(0, ...)` で ffmpeg・ffprobe・deno の存在チェック。見つからないツールがあれば `QMessageBox.warning()` を表示。

### `_set_original_format_enabled(enabled: bool)`

`QComboBox.model().item(idx).setFlags(...)` で「オリジナルの形式」コンボ項目を有効/無効化（複数選択編集時にグレーアウト）。

## ログ機能

- `_log_entries: list[str]`（最大 2000 件）にセッション中の全ログを保持
- `_log(msg)` がタイムスタンプを付与して追記
- ダウンローダーからのログは `log_message` シグナル経由でメインスレッドの `_log` スロットに委譲
- `QueueController.log_message` も同じ `_log` スロットに繋がる

## キュー実行ボタン

`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理（`setVisible()` を使用）。`QueueController.worker_done` を受けて `False` に戻す。
