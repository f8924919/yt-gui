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
| オリジナル形式の詳細設定（別画面） | [`OriginalFormatDialog`](original_format_dialog.md)（[`OriginalFormatPanel`](original_format_panel.md) を内包） |

## スレッド間通信パターン

バックグラウンドスレッドから Qt ウィジェットを直接操作してはならない。必ず `Signal` / `Slot` を経由してメインスレッドにキューイングする。Qt シグナルは別スレッドから emit しても自動的に `Qt.QueuedConnection` でメインスレッドへ配送される。

## シグナル（内部クラス `_AppSignals(QObject)`）

ワーカーキュー由来のシグナルは `QueueController` に移管済み。URL タイトル取得スレッドは [`threading_utils.run_in_thread`](threading_utils.md) に移行したため、`_AppSignals` には汎用ハンドラだけが残る。

| シグナル | 引数 | 用途 |
|----------|------|------|
| `status_update` | `str, float` | ステータスバー更新（テキスト・進捗） |
| `log_message` | `str` | ログ追記 |
| `show_error` | `str, str` | エラーダイアログ表示（title, message） |
| `extension_enqueue` | `str, object, object` | ブラウザ拡張連携。サーバースレッドからの enqueue（url, cookies, format）をメインスレッドへ委譲 |

URL タイトル取得 (`_start_add_thread`) は `run_in_thread` の `on_done` / `on_failed` / `on_finished` コールバックでメインスレッドの UI 操作を完結させる。`on_failed` 内で `_update_status` / `_log` / `QMessageBox.critical` を直接呼び、`on_finished` で「追加」ボタンを再有効化する。

`OriginalFormatPanel` も同じパターンで `run_in_thread` を使う（詳細は [original_format_panel.md](original_format_panel.md) 参照）。

## 初期化順序

1. `Settings` 読み込み・i18n 初期化
2. `Downloader` 生成（primary。タイトル取得・アーカイブ事前フィルタ・依存チェック・オリジナル形式パネル参照に使う）
3. `ThumbnailCache` 生成
4. `_create_menu()` / `_create_widgets()` → `_queue_tree` を含むウィジェット構築
5. `QueueController` 生成（引数: `downloader`, `queue_tree`, `make_downloader=self._build_download_worker`, `get_concurrency=lambda: self._settings.max_concurrent_downloads`）
6. `_wire_queue_signals()` でコントローラのシグナルをスロットに配線

`QueueController` は `_queue_tree` 構築後にしか作れないため、`_create_widgets()` の後で生成する。`_QueueTree` への依存はコンストラクタ DI で渡し、`self.queue` 未生成の段階の参照は lambda 経由で遅延化する (`get_item=lambda ti: self.queue.find_item_for(ti)`)。

### 並列ダウンロード用 Downloader ファクトリ

`_build_download_worker() -> Downloader` は、現在の設定から `status_callback=None` / `log_callback=self._on_downloader_log` の `Downloader` を生成する（`__init__` の生成ブロックと同じ設定を共通化）。`QueueController` は各ワーカーごとにこのファクトリで**専用インスタンス**を得て使う（進捗コールバック・中断フラグの混線を避けるため。[queue_controller.md](queue_controller.md)）。primary の `self.downloader` はキュー実行には使わず、`_open_settings` でのミューテートは従来どおり維持する（メタデータ系操作・パネル参照のため）。

## 内部クラス: `_QueueTree(QTreeWidget)`

キュー表示。依存は **コンストラクタ DI** で受け取り、外部からの属性書き込みは行わない:

| パラメータ | 型 | 提供元 |
|---|---|---|
| `get_item` | `Callable[[QTreeWidgetItem], _QueueItem | None]` | `QueueController.find_item_for` |
| `get_thumbnail_b64` | `Callable[[str], str | None]` | `ThumbnailCache.get` |
| `is_editing` | `Callable[[], bool]` | `lambda: self.queue.edit_mode` |
| `is_archive_enabled` | `Callable[[], bool]` | `lambda: self._settings.download_archive_enabled` |

「形式を変更」コンテキストメニュー操作は `edit_format_requested(list)` シグナルで通知し、`App._enter_edit_mode` に接続する。「アーカイブを無視して再取得」操作は `ignore_archive_refetch_requested(list)` シグナルで通知し、`App._ignore_archive_refetch`（`QueueController.mark_ignore_archive` を呼ぶ）に接続する。

独自実装:

- **ツールチップ**: `viewportEvent` で `QEvent.Type.ToolTip` を捕捉。`QToolTip.showText()` に `rect=self.visualItemRect(item)` を渡してマウスがアイテム行にいる間は持続表示（`rect` なしだとタイムアウトで消える）。サムネイルがキャッシュ済みなら 240×135px の `<img>`（base64 data URI）をツールチップ先頭に挿入。`job.ignore_archive` が立っているアイテムは「アーカイブ無視: 有効」を 1 行追加する。
- **コンテキストメニュー**: `contextMenuEvent` で実装。「URL をコピー」（複数選択時は改行区切りで `QApplication.clipboard()` へ書き込み）と「形式を変更」を提供。「形式を変更」の対象判定は純粋ヘルパ `_edit_targets(items)` に集約し、メニュー項目の活性判定 (`setEnabled`) と `edit_format_requested.emit(targets)` の発火判定で共用する（`contextMenuEvent` はモーダル `QMenu.exec` を含みヘッドレス検証しにくいため、ロジックをヘルパへ分離してテスト可能にしている）。`_edit_targets` は編集モード中 (`is_editing()`) または `waiting` が無い場合に空リストを返す。「アーカイブを無視して再取得」は `is_archive_enabled()` が真のときだけメニューに出し、対象は `_edit_targets` と同じ `waiting` 部分集合を使う。
- **アイテム色リセット**: `setData(col, Qt.ItemDataRole.ForegroundRole, None)` を使用（`setForeground(col, QColor())` は黒固定になりダークモード非対応）。

## オリジナル形式ダイアログの配線

オリジナル形式の詳細設定は別画面（[`OriginalFormatDialog`](original_format_dialog.md)）に分離されている。`App` はダイアログを**開くたびに生成・破棄**し、生存参照を保持しない。

- 形式コンボで「オリジナルの形式」選択時、`_on_format_changed` は埋め込みパネルではなく **「詳細設定...」ボタン**を表示する（高さ変更・`resize` は行わない）。
- 「詳細設定...」クリックでダイアログを生成（URL 空なら `warn_no_url` で開かない）。ダイアログの `add_requested` / `edit_applied` / `edit_cancelled` シグナルをハンドラに配線する。
- `add_requested` ハンドラはダイアログの内包パネル（`dialog.panel`）から `get_snapshot()` 等を読み、検証通過後に下記「キュー追加経路」を実行する。検証 NG はダイアログ側で警告して開いたままにする。

## キュー追加経路

- `add_requested` ハンドラで `build_job_spec()` を呼び出して `JobSpec` を組み立てる。`fmt_original` のときはダイアログ内包パネルの `get_snapshot()` で UI 非依存の `PanelSnapshot` を作って渡す。オリジナル形式以外はメインの「追加」ボタン（`_add_url`）から従来どおり組み立てる。
- 取得済み（`has_formats_loaded()`）なら `enqueue_single(...)` に即委譲。未取得なら URL 取得スレッドへ渡す（単独動画のみ。オリジナル形式はプレイリスト非対応で、`_on_fetch_for_add_done` がプレイリスト判明時に `warn_playlist_original_fmt` で中止する）。
- `_on_fetch_for_add_done(payload)` の payload 構造は `{"result": ..., "job": JobSpec, "format_label": str, "item_cookies_path": str | None}`。単発は `self.queue.enqueue_single(..., cookies_path=item_cookies_path)`、プレイリストは `self.queue.enqueue_playlist(..., cookies_path=item_cookies_path)` に委譲。`item_cookies_path` は拡張連携で受信した一時 cookies のパス（手動追加では `None`）。
- `_on_queue_item_added(item)` スロット: `QueueController.item_added` シグナルを受けて `self._thumbnail_cache.request(item.thumbnail_url)` を起動する。
- `_notify_container_promotion_if_needed(job)`: 複数音声で MKV 昇格が起きた場合のステータス通知。`build_job_spec` は UI 通知を行わないため UI 側で発火する。

## ブラウザ拡張連携

> 関連仕様: [ブラウザ拡張連携](../spec/features/browser-extension.md)。サーバー本体は [extension_server.md](extension_server.md)。

`App` は [`ExtensionServer`](extension_server.md) を所有し、設定に応じて起動/停止する。

| メソッド / スロット | 説明 |
|---|---|
| `_sync_extension_server()` | `settings.extension_enabled` を見て起動/停止を整合させる。`__init__` 末尾・`_open_settings` 後に呼ぶ。ポート変更は再起動が必要だが MVP では次回有効化時に反映 |
| `_start_extension_server()` | トークンが空なら起動しない（`log_extension_no_token`）。`ExtensionServer.start()` で `127.0.0.1` にバインド、失敗時は `log_extension_bind_failed` |
| `_stop_extension_server()` | サーバーを停止して参照を破棄 |
| `_emit_extension_enqueue(url, cookies, fmt)` | **サーバースレッド**から呼ばれ、`extension_enqueue` シグナルでメインスレッドへ委譲（Qt ウィジェットを直接触らない） |
| `_on_extension_enqueue(url, cookies, fmt)` | **メインスレッド**。cookies を一時ファイル化し、`_extension_default_format()` の形式で `_start_add_thread(..., item_cookies_path=...)` を起動。`fmt` は MVP では無視 |
| `_extension_default_format()` | メイン画面のコンボ現在選択を使う。`fmt_original`（ダイアログ必須）のときは `fmt_best_mp4` へフォールバック |
| `_write_extension_cookies(cookies)` | `tempfile.TemporaryDirectory` 配下に 0600 で cookies.txt を書き、パスを返す（失敗時 `None`） |
| `closeEvent(event)` | サーバー停止と一時 cookies ディレクトリの掃除 |

一時 cookies ディレクトリはアプリ終了時（`closeEvent`）に一括削除する。

## 編集モード経路

| メソッド / スロット | 説明 |
|---|---|
| `_enter_edit_mode(items)` | `QueueController.enter_edit_mode(items)` を呼ぶだけ |
| `_on_edit_mode_entered(items)` | `edit_mode_entered` シグナルのスロット。URL 入力欄・フォーマットコンボ・MP3 サムネチェック・パネル復元・ボタン状態・ステータスバーなどの UI 側操作を実施 |
| `_apply_edit()` | UI から `format_label` と `JobSpec` を組み立てて `QueueController.apply_edit(...)` に渡す |
| `_cancel_edit()` | `QueueController.cancel_edit()` を呼ぶだけ |
| `_on_edit_mode_exited()` | `edit_mode_exited` シグナルのスロット。UI を通常モードに戻す |

単一 ORIGINAL_KEY アイテムを編集モードに入れた場合は、対象アイテムの `orig_settings` を渡して [`OriginalFormatDialog`](original_format_dialog.md) を**編集モードで生成**する。設定復元（`restore_from_settings`）とフォーマット取得（`trigger_fetch`）はダイアログ側で行う。`edit_applied` で `QueueController.apply_edit(...)`、`edit_cancelled` で `cancel_edit()` に委譲する。`キャンセル` ボタンはメインウィンドウ側に残る。

## 主要メソッド

### `_resolve_cookies() -> tuple[str | None, str | None]`

設定値を確認し `(cookies_path, cookies_browser)` を返す。ブラウザ設定を優先。`QueueController.start()` に渡されてワーカー内で毎イテレーション呼ばれる（生きた設定変更を反映するため）。

### `_build_format_display()`

`fmt_720p` / `fmt_mp3` / `fmt_best_mp4` のラベルを設定値から生成。`audio_format` が `"flac"` のときは `fmt_flac` キーを使用。

### `_on_format_changed()`

「詳細設定...」ボタン（オリジナル形式時）/ `_mp3_frame`（MP3 時のみ表示）/ メインの「追加」ボタン（オリジナル形式時は非表示）を `setVisible()` で切り替える。**ウィンドウ高さの `resize()` 調整は行わない**（詳細設定が別画面に分離されたため、メイン高さは固定。旧 `_WIN_H_EXPANDED` / `_resync_splitter_to_top_hint` / パネルの `on_size_hint_changed` 配線は撤去）。

### `_retranslate_ui()` / `_refresh_format_labels()`

`_refresh_format_labels()` は `video_container` / `audio_format` / `mp3_bitrate` 等の **設定変更** や **言語変更** で必要になるフォーマットコンボとオリジナルパネルの再構築をまとめたヘルパ。`_retranslate_ui` (言語切替時) と `_open_settings` (言語非変更の設定保存時) の両方から呼ばれる。

`_retranslate_ui()` は本ヘルパに加えてメニュー・ラベル・ボタンなど **言語切替時のみ更新が必要な要素** を再翻訳する。キュー行の再描画は `self.queue.refresh_all_tree_items()` に委譲。

### `_check_dependencies()`

起動時に `QTimer.singleShot(0, ...)` で ffmpeg・ffprobe・deno の存在チェック。判定は `self.downloader.missing_dependencies()` (公開 API) に委譲し、見つからないツールがあれば `QMessageBox.warning()` を表示する。バイナリパス (`_ffmpeg_path` 等) の private 属性アクセスは行わない。

### `_set_original_format_enabled(enabled: bool)`

`QComboBox.model().item(idx).setFlags(...)` で「オリジナルの形式」コンボ項目を有効/無効化（複数選択編集時にグレーアウト）。

## ログ機能

- `_log_entries: list[str]`（最大 2000 件）にセッション中の全ログを保持
- `_log(msg)` がタイムスタンプを付与して追記
- ダウンローダーからのログは `log_message` シグナル経由でメインスレッドの `_log` スロットに委譲
- `QueueController.log_message` も同じ `_log` スロットに繋がる

## キュー実行ボタン

`_set_queue_running(running: bool)` で開始/一時停止ボタンの表示切り替えを一元管理（`setVisible()` を使用）。`QueueController.worker_done` を受けて `False` に戻す。
