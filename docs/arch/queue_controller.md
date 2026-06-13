# `queue_controller.py`

> 関連仕様: [ダウンロードキュー](../spec/features/queue.md)

ダウンロードキューの所有・走行・編集モード状態機械を `App` から切り出したコントローラ。

リファクタ前は `App` クラス (1,447 行) が「ウィジェット組み立て・キュー管理・サムネ取得・編集モード・設定リロード」を一手に持っていたが、本モジュールにキュー関連の責務をまとめることで `App` はウィジェット組み立てとシグナル配線に専念できる構造にした。

## 提供するクラス

| 名前 | 役割 |
|---|---|
| `_QueueItem` (`@dataclass`) | 1 キュー項目。`url` / `title` / `format_label` / `job: JobSpec` / `playlist_*` / `thumbnail_url` / `cookies_path: str \| None` / `status` / `progress: float` / `tree_item` を保持 |
| `QueueController(QObject)` | キューの所有とライフサイクル管理 |

`_QueueItem.format_id` は `job.format_id` のエイリアスプロパティ。

## `QueueController` の責務

1. `_QueueItem` のライフサイクル管理 (追加 / 削除 / ステータス更新)
2. ダウンロードワーカースレッドの起動・一時停止
3. 編集モード状態機械 (`waiting` → `editing` → `waiting`)

UI ウィジェット (URL 入力欄・フォーマットコンボ・ボタンなど) の更新は `App` 側で行う。コントローラは状態変化を **シグナル経由** で通知する。

## 公開 API

### キュー追加 / 削除 / 検索

| メソッド | 説明 |
|---|---|
| `enqueue_single(url, title, format_label, job, *, thumbnail_url=None, cookies_path=None) -> _QueueItem` | 単発追加 (`tree_item` を生成して `queue_tree.addTopLevelItem`、`item_added` シグナル emit)。`cookies_path` はアイテム固有 Cookies（拡張連携） |
| `enqueue_playlist(entries, playlist_title, format_label, job, *, cookies_path=None) -> list[_QueueItem]` | プレイリスト一括追加。`cookies_path` を渡すと全エントリへ同一値を付与（拡張連携） |
| `find_item_for(tree_item) -> _QueueItem \| None` | `QTreeWidgetItem` から対応する `_QueueItem` を検索 |
| `remove_selected() -> None` | `queue_tree.selectedItems()` のうち `downloading` / `editing` 以外を削除 |
| `has_waiting() -> bool` | 待機中アイテムがあるか |

### ワーカー走行

| メソッド | 説明 |
|---|---|
| `start(cookies_resolver) -> bool` | `get_concurrency()` を `[1, MAX_CONCURRENT_DOWNLOADS_MAX]` にクランプした数だけワーカースレッドを起動する。`cookies_resolver: () -> (cookies_path, cookies_browser)` を毎イテレーション呼ぶことで生きた設定変更を反映する。ただし**アイテム固有 `cookies_path` があればそちらを優先**し（`cookies_browser` は `None`）、無いときだけ `cookies_resolver()` にフォールバックする。起動できないとき (待機項目無し / 実行中) は `False` |
| `pause() -> None` | `_paused=True` をセットし、走行中の **全ワーカーの `Downloader`**（`_active_downloaders`、dedupe）に `request_cancel()` で中断を要求する。進行中アイテムは `DownloadCancelled` で中断され `waiting` に戻り、各ワーカーは次のイテレーション境界で停止する |
| `is_running` (property) | 走行中ワーカーが 1 つ以上あるか（`_active_workers > 0`） |

#### 並列ワーカーと Downloader プール

- 各ワーカーは `make_downloader()` で得た**専用 `Downloader` インスタンス**を使う。`Downloader` は `status_callback` と `_cancel_requested`（中断フラグ）を**インスタンス属性**で持つため（[downloader.md](downloader.md)）、単一インスタンスを並列共有すると進捗コールバックと中断が混線する。インスタンスを分けることで、`downloader.py` の中断ロジックを無改修のままアイテム間で隔離する。
- 既定の `make_downloader` は `lambda: downloader`（コンストラクタ引数の単一インスタンス）。`App` は現在の設定から distinct な `Downloader` を生成するファクトリ（`_build_download_worker`）を渡す（[app.md](app.md)）。
- `_worker(cookies_resolver, downloader)` は `finally` で自分を `_active_downloaders` / `_active_workers` から外し、**最後の 1 本**だけが全体進捗の確定・`worker_done` / `log_queue_done`（pause 時は出さない）を emit する。
- 進捗ルーティング: `make_cb(item)` が percent を `item.progress` に格納して `item_refresh.emit(item)`（該当行のみ再描画）し、`_emit_overall_progress()` で全体進捗を `status_update` に流す。全体進捗 = `finished / total`（`finished = {done,error,skipped}`、`total = {waiting,downloading,done,error,skipped}`）。

### 編集モード

| メソッド | 説明 |
|---|---|
| `enter_edit_mode(items) -> bool` | 全アイテムが `waiting` のときのみ移行。状態 → `editing`、`edit_mode_entered(items)` emit |
| `apply_edit(format_label, job) -> None` | 編集中アイテムの `format_label` / `job` を差し替え、状態 → `waiting`、`edit_mode_exited` emit |
| `cancel_edit() -> None` | 編集中アイテムを `waiting` に戻して `edit_mode_exited` emit |
| `edit_mode` (property) | 現在編集モードか |
| `editing_items` (property) | 編集中アイテムリスト (コピー) |

### アーカイブ無視（再取得）

| メソッド | 説明 |
|---|---|
| `mark_ignore_archive(items) -> int` | 引数のうち `waiting` のアイテムの `job` を `dataclasses.replace(job, ignore_archive=True)` に差し替え、ダウンロードアーカイブの照合・スキップ対象から外す。差し替えた行を再描画し、件数をログ出力して返す。`downloading` / `editing` 等は対象外。動作仕様は[アイテム単位でアーカイブを無視して再取得](../spec/features/download-behavior.md#アイテム単位でアーカイブを無視して再取得) |

「形式を変更」で編集すると `apply_edit` が `build_job_spec` 由来の新 `job` で差し替えるため、`ignore_archive` は `False` に戻る（[job_spec.md](job_spec.md)）。

### 表示更新

| メソッド | 説明 |
|---|---|
| `refresh_tree_item(item)` | 単一行を再描画 (`status` テキスト・色)。`downloading` のときはステータス列に進捗 %（`queue_status_downloading_pct` を `item.progress` で書式化）を表示する |
| `refresh_all_tree_items()` | 全行を再描画 (言語切替時用) |

## シグナル

| シグナル | 引数 | 用途 |
|---|---|---|
| `item_refresh` | `_QueueItem` | ワーカースレッドからの行再描画要求 |
| `worker_done` | — | ワーカースレッド終了通知 |
| `status_update` | `str, float` | ステータスバー更新 |
| `log_message` | `str` | ログ追記 |
| `show_error` | `str, str` | エラーダイアログ表示 |
| `show_warning` | `str, str` | 警告ダイアログ表示 |
| `item_added` | `_QueueItem` | 追加完了通知 (`App` がサムネ取得を起動するフックポイント) |
| `edit_mode_entered` | `list[_QueueItem]` | 編集モード移行通知 (UI 更新のトリガ) |
| `edit_mode_exited` | — | 編集モード終了通知 |

## ステータス遷移

```
waiting → downloading → done
            ↓   ↓   ↓
      error  waiting  skipped
        (waiting = 一時停止による中断)
        (skipped = ダウンロードアーカイブに記録済み)
waiting → editing → waiting (apply or cancel)
```

`_worker` の download 呼び出しは、`except Exception`（→`error`）より**前**で次の 2 例外を個別捕捉する。いずれも `error` 扱いにはしない。

- `DownloadCancelled`（一時停止による中断）→ アイテムを `waiting` に戻す。中断後はループ先頭の `_paused` 判定でワーカーが停止する。
- `DownloadSkipped`（ダウンロードアーカイブに記録済み・[downloader](downloader.md#ダウンロードアーカイブ)が送出）→ アイテムを `skipped` にする。実ダウンロードも記録も行われない。

`skipped` は `_STATUS_KEY_MAP` / `_STATUS_COLORS` に登録され、ラベル `queue_status_skipped`・グレー表示で再描画される。`downloading` / `editing` 以外は `remove_selected` の対象なので `skipped` は削除可能。

`downloading` / `editing` 中のアイテムは `remove_selected()` の対象外。

## 内部状態

| 属性 | 用途 |
|---|---|
| `_items: list[_QueueItem]` | キュー本体 |
| `_lock: threading.Lock` | `_items` / 各 `item.status` / `_active_workers` / `_active_downloaders` の排他制御 |
| `_active_workers: int` | 走行中ワーカー数（`is_running` の基。`0` で全停止） |
| `_active_downloaders: list[Downloader]` | 走行中ワーカーが使用中の `Downloader`（`pause()` の中断対象） |
| `_make_downloader: Callable[[], Downloader]` | ワーカー用 `Downloader` ファクトリ（既定は単一インスタンスを返す） |
| `_get_concurrency: Callable[[], int]` | 同時ダウンロード数を返す（既定 `1`） |
| `_paused: bool` | 一時停止フラグ (次イテレーションで各ワーカーが停止) |
| `_item_counter: int` | キュー追加時の連番 (表示列 `#`) |
| `_edit_mode: bool` | 編集モードフラグ |
| `_editing_items: list[_QueueItem]` | 編集中アイテム |

## 不変条件

- ワーカースレッドは **`_queue_tree` を直接操作しない**。表示更新は `item_refresh` シグナル経由でメインスレッドへ。
- `enqueue_*` / `remove_selected` / `enter_edit_mode` / `apply_edit` / `cancel_edit` はメインスレッドから呼ぶ前提 (UI 操作を含む)。
- `cookies_resolver` は毎イテレーションで呼ばれるため、生きた設定変更が反映される (queue 走行中に設定変更しても次アイテムから新値)。アイテム固有 `cookies_path` を持つアイテムは resolver を呼ばずにそちらを使う（アイテム固有 > グローバル。[browser-extension](../spec/features/browser-extension.md)）。
