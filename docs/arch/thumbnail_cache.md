# `thumbnail_cache.py`

動画サムネイル画像の非同期取得と base64 data URI キャッシュを担う `QObject`。

リファクタ前は `App` 内に `dict` + `threading.Lock` + 取得スレッド + 3 つのメソッドが散在していたが、独立クラスに切り出して `App` から汚染を除いた。

## クラス: `ThumbnailCache(QObject)`

### 公開 API

| メソッド | 戻り値 | 説明 |
|---|---|---|
| `get(url)` | `str \| None` | キャッシュ済みなら `data:...` URI、未取得なら `None` |
| `request(url)` | — | 未取得・取得中でなければバックグラウンド HTTP 取得を起動 |

### シグナル

| シグナル | 引数 | 用途 |
|---|---|---|
| `thumbnail_ready` | `str` (url) | 取得完了通知。ツールチップの強制再描画など。利用者が無くても安全 |

## 内部実装

- `_cache: dict[str, str]` — URL → data URI
- `_fetching: set[str]` — 取得中の URL
- `_lock: threading.Lock` — 上記 2 つの排他制御
- `_fetch(url)` — `urllib.request` 取得、Content-Type を data URI に保持。スレッド起動は [`threading_utils.run_in_thread`](threading_utils.md) に委譲し、`_on_fetched` / `_on_fetch_failed` をメインスレッドのコールバックとして受ける

## 呼び出し側 (`app.py`)

- `_QueueTree.viewportEvent` (ツールチップ生成) → `cache.get(url)`
- `App._on_queue_item_added` → `cache.request(item.thumbnail_url)` (`QueueController.item_added` シグナル経由)

## 不変条件

- 取得失敗 (HTTP エラー / タイムアウト) は例外を握り潰し、キャッシュにも入れない。次回 `request(url)` で再試行可能。
- 同一 URL に対する並行 `request(url)` は最大 1 スレッド (`_fetching` セットでガード)。
