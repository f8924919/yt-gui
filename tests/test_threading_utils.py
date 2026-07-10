"""`run_in_thread` のコールバック順序を検証する。

対応する spec は無いインフラヘルパのため、arch を参照:
[docs/arch/threading_utils.md](../docs/arch/threading_utils.md)。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from yt_gui.threading_utils import run_in_thread

pytestmark = pytest.mark.qt


def test_run_in_thread_calls_done_then_finished_on_success(qtbot):
    events: list[tuple] = []
    run_in_thread(
        lambda: 42,
        on_done=lambda r: events.append(("done", r)),
        on_failed=lambda e: events.append(("failed", e)),
        on_finished=lambda: events.append(("finished",)),
    )
    qtbot.waitUntil(lambda: ("finished",) in events, timeout=2000)
    assert events == [("done", 42), ("finished",)]


def test_run_in_thread_calls_failed_then_finished_on_exception(qtbot):
    boom = ValueError("boom")
    events: list[tuple] = []

    def work():
        raise boom

    run_in_thread(
        work,
        on_done=lambda r: events.append(("done", r)),
        on_failed=lambda e: events.append(("failed", e)),
        on_finished=lambda: events.append(("finished",)),
    )
    qtbot.waitUntil(lambda: ("finished",) in events, timeout=2000)
    assert events == [("failed", boom), ("finished",)]
