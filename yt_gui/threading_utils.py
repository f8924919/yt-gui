"""バックグラウンドスレッド + Qt シグナルの共通ヘルパ。

`run_in_thread(work, on_done=..., on_failed=..., on_finished=...)` で
`work()` をワーカースレッドで実行し、結果をメインスレッドの
コールバックにキューイングする。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal


class _ThreadWorker(QObject):
    """ワーカースレッドの結果をメインスレッドへ転送するための QObject。"""

    done = Signal(object)
    failed = Signal(object)
    finished = Signal()


# parent 未指定時にワーカーが GC されないよう強参照を保持する。
_live_workers: set[_ThreadWorker] = set()
_live_workers_lock = threading.Lock()


def run_in_thread(
    work: Callable[[], Any],
    *,
    on_done: Callable[[Any], None],
    on_failed: Callable[[Exception], None],
    on_finished: Callable[[], None] | None = None,
    parent: QObject | None = None,
) -> None:
    """ワーカースレッドで `work()` を実行し、結果をメインスレッドへ転送する。

    - 成功時: `on_done(result)`
    - `Exception` 発生時: `on_failed(exc)`
    - 成功・失敗いずれの場合も最後に `on_finished()` (指定時のみ)

    呼び出しは Qt シグナル経由なので、コールバックは receiver の生存
    スレッド (通常はメインスレッド) で実行される。`work()` 自身は
    ワーカースレッドで実行されるため Qt ウィジェットを直接触らない。

    `KeyboardInterrupt` / `SystemExit` は捕捉せず素通しする。
    """
    worker = _ThreadWorker(parent)
    worker.done.connect(on_done)
    worker.failed.connect(on_failed)
    if on_finished is not None:
        worker.finished.connect(on_finished)

    with _live_workers_lock:
        _live_workers.add(worker)

    def _cleanup() -> None:
        with _live_workers_lock:
            _live_workers.discard(worker)
        worker.deleteLater()

    worker.finished.connect(_cleanup)

    def _run() -> None:
        try:
            result = work()
        except Exception as exc:
            worker.failed.emit(exc)
        else:
            worker.done.emit(result)
        finally:
            worker.finished.emit()

    threading.Thread(target=_run, daemon=True).start()
