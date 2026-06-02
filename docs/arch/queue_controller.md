# `queue_controller.py`

> 関連仕様: [ダウンロードキュー](../spec/features/queue.md)

ダウンロードキューの所有・走行・編集モード状態機械を `App` から切り出したコントローラ。

リファクタ前は `App` クラス (1,447 行) が「ウィジェット組み立て・キュー管理・サムネ取得・編集モード・設定リロード」を一手に持っていたが、本モジュールにキュー関連の責務をまとめることで `App` はウィジェット組み立てとシグナル配線に専念できる構造にした。

## 提供するクラス

| 名前 | 役割 |
|---|---|
| `_QueueItem` (`@dataclass`) | 1 キュー項目。`url` / `title` / `format_label` / `job: JobSpec` / `playlist_*` / `thumbnail_url` / `status` / `tree_item` を保持 |
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
| `enqueue_single(url, title, format_label, job, *, thumbnail_url=None) -> _QueueItem` | 単発追加 (`tree_item` を生成して `queue_tree.addTopLevelItem`、`item_added` シグナル emit) |
| `enqueue_playlist(entries, playlist_title, format_label, job) -> list[_QueueItem]` | プレイリスト一括追加 |
| `find_item_for(tree_item) -> _QueueItem \| None` | `QTreeWidgetItem` から対応する `_QueueItem` を検索 |
| `remove_selected() -> None` | `queue_tree.selectedItems()` のうち `downloading` / `editing` 以外を削除 |
| `has_waiting() -> bool` | 待機中アイテムがあるか |

### ワーカー走行

| メソッド | 説明 |
|---|---|
| `start(cookies_resolver) -> bool` | ワーカースレッド起動。`cookies_resolver: () -> (cookies_path, cookies_browser)` を毎イテレーション呼ぶことで生きた設定変更を反映する。起動できないとき (待機項目無し / 実行中) は `False` |
| `pause() -> None` | `_paused=True` をセットし、`downloader.request_cancel()` で進行中ダウンロードに中断を要求する。進行中アイテムは `DownloadCancelled` で中断され `waiting` に戻り、次のイテレーション境界でワーカーが停止する |
| `is_running` (property) | ワーカースレッドが走行中か |

### 編集モード

| メソッド | 説明 |
|---|---|
| `enter_edit_mode(items) -> bool` | 全アイテムが `waiting` のときのみ移行。状態 → `editing`、`edit_mode_entered(items)` emit |
| `apply_edit(format_label, job) -> None` | 編集中アイテムの `format_label` / `job` を差し替え、状態 → `waiting`、`edit_mode_exited` emit |
| `cancel_edit() -> None` | 編集中アイテムを `waiting` に戻して `edit_mode_exited` emit |
| `edit_mode` (property) | 現在編集モードか |
| `editing_items` (property) | 編集中アイテムリスト (コピー) |

### 表示更新

| メソッド | 説明 |
|---|---|
| `refresh_tree_item(item)` | 単一行を再描画 (`status` テキスト・色) |
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
            ↓   ↓
        error   waiting (一時停止による中断)
waiting → editing → waiting (apply or cancel)
```

`_worker` の download 呼び出しは `DownloadCancelled`（一時停止による中断）を `except Exception`（→`error`）より**前**で個別捕捉し、アイテムを `waiting` に戻す。`error` 扱いにはしない。中断後はループ先頭の `_paused` 判定でワーカーが停止する。

`downloading` / `editing` 中のアイテムは `remove_selected()` の対象外。

## 内部状態

| 属性 | 用途 |
|---|---|
| `_items: list[_QueueItem]` | キュー本体 |
| `_lock: threading.Lock` | `_items` と各 `item.status` の排他制御 |
| `_worker_running: bool` | ワーカー走行中フラグ |
| `_paused: bool` | 一時停止フラグ (次イテレーションで `_worker_running=False`) |
| `_item_counter: int` | キュー追加時の連番 (表示列 `#`) |
| `_edit_mode: bool` | 編集モードフラグ |
| `_editing_items: list[_QueueItem]` | 編集中アイテム |

## 不変条件

- ワーカースレッドは **`_queue_tree` を直接操作しない**。表示更新は `item_refresh` シグナル経由でメインスレッドへ。
- `enqueue_*` / `remove_selected` / `enter_edit_mode` / `apply_edit` / `cancel_edit` はメインスレッドから呼ぶ前提 (UI 操作を含む)。
- `cookies_resolver` は毎イテレーションで呼ばれるため、生きた設定変更が反映される (queue 走行中に設定変更しても次アイテムから新値)。
