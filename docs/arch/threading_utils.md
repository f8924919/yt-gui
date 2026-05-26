# `threading_utils.py`

バックグラウンドスレッド + Qt シグナルの共通ヘルパ。「ワーカースレッドで何かを実行 → 結果をメインスレッドのコールバックに転送」というパターンを 1 箇所に集約する。

## 公開 API

```python
def run_in_thread(
    work: Callable[[], Any],
    *,
    on_done: Callable[[Any], None],
    on_failed: Callable[[Exception], None],
    on_finished: Callable[[], None] | None = None,
    parent: QObject | None = None,
) -> None
```

| 引数 | 説明 |
|---|---|
| `work` | ワーカースレッドで実行する関数。戻り値は `on_done` の引数として渡される |
| `on_done` | 成功時のコールバック (メインスレッド)。`work()` の戻り値を受ける |
| `on_failed` | `Exception` 発生時のコールバック (メインスレッド)。例外オブジェクトを受ける |
| `on_finished` | 成功・失敗いずれの場合も最後に呼ばれるコールバック。ボタン再有効化など |
| `parent` | 内部 QObject の親。長寿命の `QObject` (例: `App` 自体) を渡しておくと整理が楽 |

`KeyboardInterrupt` / `SystemExit` は捕捉せず素通しする。

## 振る舞い

1. メインスレッドで `_ThreadWorker(QObject)` を生成し、`done` / `failed` / `finished` シグナルをコールバックへ接続する。
2. `threading.Thread(daemon=True)` で `work()` を実行。
3. `work()` の結果に応じて `done.emit(result)` か `failed.emit(exc)` を発行。
4. 成否によらず最後に `finished.emit()` を発行。
5. シグナルは Qt の自動接続 (別スレッド→`QueuedConnection`) によってメインスレッドのイベントループへキューイングされる。
6. `finished` の最後の接続スロットで内部 QObject を `deleteLater()` する。

## ライフサイクル管理

- ワーカー QObject は GC されないよう、ヘルパ内のモジュールレベル集合 `_live_workers` に強参照を保持する。`finished` 後に集合から外し `deleteLater()` する。
- `parent` を渡しても渡さなくてもライフサイクルは安全。`parent` は Qt 側のオーナーシップに紐付けたい場合のみ使う。

## 呼び出し側

| 呼び出し元 | 用途 |
|---|---|
| [`App._start_add_thread`](app.md) | 追加時の URL タイトル取得 |
| [`ThumbnailCache.request`](thumbnail_cache.md) | サムネイル HTTP 取得 |
| [`OriginalFormatPanel._start_fetch_thread`](original_format_panel.md) | yt-dlp フォーマット情報の取得 |

## 範囲外

- `QueueController._worker` のような長時間ループスレッド (1 回の `work()` という前提に合わない)
- `Downloader` 内部の `subprocess` 呼び出し (`Downloader` 自身が同期 API で完結している)

## テスト

`threading_utils.py` は Qt の `QCoreApplication` イベントループに依存するため、現行のテスト方針 ([docs/testing/policy.md](../testing/policy.md)) では Qt UI レイヤと同じく対象外 (`pytest-qt` 導入時に検討)。
