"""`QueueController` の編集モード状態機械を検証する。

対応 spec: [編集モード](../docs/spec/features/queue.md) 節。
"""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QTreeWidget  # noqa: E402

from yt_gui.job_spec import build_job_spec  # noqa: E402
from yt_gui.queue_controller import QueueController  # noqa: E402
from yt_gui.settings import Settings  # noqa: E402

pytestmark = pytest.mark.qt


@pytest.fixture
def controller(qtbot):
    tree = QTreeWidget()
    tree.setColumnCount(4)
    qtbot.addWidget(tree)
    return QueueController(MagicMock(), tree)


def _enqueue(controller, title="動画", label="MP4 (best)"):
    job = build_job_spec("fmt_best_mp4", Settings())
    return controller.enqueue_single("https://example.com/v", title, label, job)


def test_enter_edit_mode_moves_waiting_items_to_editing(controller, qtbot):
    a = _enqueue(controller, "A")
    b = _enqueue(controller, "B")

    with qtbot.waitSignal(controller.edit_mode_entered, timeout=1000) as blocker:
        assert controller.enter_edit_mode([a, b]) is True

    assert controller.edit_mode is True
    assert [a.status, b.status] == ["editing", "editing"]
    assert controller.editing_items == [a, b]
    assert blocker.args == [[a, b]]


def test_enter_edit_mode_rejected_when_any_item_not_waiting(controller):
    a = _enqueue(controller, "A")
    b = _enqueue(controller, "B")
    b.status = "downloading"

    assert controller.enter_edit_mode([a, b]) is False
    assert controller.edit_mode is False
    assert [a.status, b.status] == ["waiting", "downloading"]


def test_apply_edit_replaces_format_and_returns_to_waiting(controller, qtbot):
    a = _enqueue(controller, "A")
    controller.enter_edit_mode([a])
    new_job = build_job_spec("fmt_mp3", Settings(audio_format="mp3"))

    with qtbot.waitSignal(controller.edit_mode_exited, timeout=1000):
        controller.apply_edit("MP3", new_job)

    assert controller.edit_mode is False
    assert a.status == "waiting"
    assert a.format_label == "MP3"
    assert a.job is new_job


def test_cancel_edit_restores_waiting_without_changing_job(controller, qtbot):
    a = _enqueue(controller, "A")
    original_job = a.job
    controller.enter_edit_mode([a])

    with qtbot.waitSignal(controller.edit_mode_exited, timeout=1000):
        controller.cancel_edit()

    assert controller.edit_mode is False
    assert a.status == "waiting"
    assert a.job is original_job


# ── 進行中ダウンロードの中断 ──────────────────────────────────────────────


def test_pause_requests_downloader_cancel(controller):
    controller.pause()
    assert controller._paused is True
    controller._downloader.request_cancel.assert_called_once()


def test_worker_returns_cancelled_item_to_waiting(controller, qtbot):
    from yt_dlp.utils import DownloadCancelled

    item = _enqueue(controller, "中断対象")

    def _cancel(*a, **k):
        # pause() が _paused を立て request_cancel した結果を模す
        controller._paused = True
        raise DownloadCancelled()

    controller._downloader.download_video.side_effect = _cancel

    assert controller.start(lambda: (None, None)) is True
    qtbot.waitUntil(
        lambda: item.status == "waiting" and not controller.is_running, timeout=2000
    )
    # 中断は error 化せず waiting に戻す
    assert item.status == "waiting"


def test_worker_real_error_still_marks_error(controller, qtbot):
    item = _enqueue(controller, "失敗対象")

    def _boom(*a, **k):
        controller._paused = True  # 1 回で確実にループを抜ける
        raise RuntimeError("boom")

    controller._downloader.download_video.side_effect = _boom

    assert controller.start(lambda: (None, None)) is True
    qtbot.waitUntil(
        lambda: item.status == "error" and not controller.is_running, timeout=2000
    )
    assert item.status == "error"


def test_worker_archived_item_marked_skipped(controller, qtbot):
    """DownloadSkipped はアイテムを skipped にし、error 化しないこと。"""
    from yt_gui.downloader import DownloadSkipped

    item = _enqueue(controller, "アーカイブ済み")

    def _skip(*a, **k):
        controller._paused = True  # 1 回で確実にループを抜ける
        raise DownloadSkipped("https://example.com/v")

    controller._downloader.download_video.side_effect = _skip

    assert controller.start(lambda: (None, None)) is True
    qtbot.waitUntil(
        lambda: item.status == "skipped" and not controller.is_running, timeout=2000
    )
    assert item.status == "skipped"
