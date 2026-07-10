"""`QueueController` の編集モード状態機械を検証する。

対応 spec: [編集モード](../docs/spec/features/queue.md) 節。
"""

import threading
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QTreeWidget

from yt_gui.job_spec import build_job_spec
from yt_gui.queue_controller import QueueController
from yt_gui.settings import Settings

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


# ── アイテム単位 Cookies ──────────────────────────────────────────────────
# 対応 spec: docs/spec/features/browser-extension.md / queue.md


def test_enqueue_single_stores_item_cookies_path(controller):
    """enqueue_single の cookies_path がアイテムに保存されること。"""
    job = build_job_spec("fmt_best_mp4", Settings())
    item = controller.enqueue_single(
        "https://example.com/v", "動画", "MP4", job, cookies_path="/tmp/c.txt"
    )
    assert item.cookies_path == "/tmp/c.txt"


def test_enqueue_single_cookies_path_defaults_none(controller):
    """cookies_path 未指定時は None（従来挙動）。"""
    item = _enqueue(controller)
    assert item.cookies_path is None


def test_enqueue_playlist_applies_cookies_to_all_entries(controller):
    """プレイリスト一括追加で全エントリに同一 cookies_path が付くこと。"""
    job = build_job_spec("fmt_best_mp4", Settings())
    entries = [
        {"url": "https://example.com/1", "title": "A"},
        {"url": "https://example.com/2", "title": "B"},
    ]
    items = controller.enqueue_playlist(
        entries, "PL", "MP4", job, cookies_path="/tmp/pl.txt"
    )
    assert [i.cookies_path for i in items] == ["/tmp/pl.txt", "/tmp/pl.txt"]


def test_worker_prefers_item_cookies_over_global(controller, qtbot, tmp_path):
    """アイテム固有 cookies_path がグローバル設定より優先されること。"""
    cookie_file = tmp_path / "item_cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n")
    job = build_job_spec("fmt_best_mp4", Settings())
    controller.enqueue_single(
        "https://example.com/v", "動画", "MP4", job, cookies_path=str(cookie_file)
    )

    captured: dict = {}

    def _dv(url, job, cookies_path, **kwargs):
        captured["cookies_path"] = cookies_path
        captured["cookies_browser"] = kwargs.get("cookies_browser")
        controller._paused = True
        return None

    controller._downloader.download_video.side_effect = _dv

    # グローバルはブラウザ取得。アイテム固有（ファイル）が勝つこと。
    assert controller.start(lambda: (None, "chrome")) is True
    qtbot.waitUntil(lambda: not controller.is_running, timeout=2000)
    assert captured["cookies_path"] == str(cookie_file)
    assert captured["cookies_browser"] is None


def test_worker_falls_back_to_global_when_item_has_no_cookies(controller, qtbot):
    """アイテムに cookies_path が無ければグローバル設定にフォールバック。"""
    _enqueue(controller)
    captured: dict = {}

    def _dv(url, job, cookies_path, **kwargs):
        captured["cookies_path"] = cookies_path
        captured["cookies_browser"] = kwargs.get("cookies_browser")
        controller._paused = True
        return None

    controller._downloader.download_video.side_effect = _dv

    assert controller.start(lambda: (None, "chrome")) is True
    qtbot.waitUntil(lambda: not controller.is_running, timeout=2000)
    assert captured["cookies_path"] is None
    assert captured["cookies_browser"] == "chrome"


def test_worker_warns_and_drops_missing_item_cookies(controller, qtbot):
    """アイテム固有 cookies のファイルが無ければ警告し、cookies なしで続行
    （グローバルにはフォールバックしない）。"""
    job = build_job_spec("fmt_best_mp4", Settings())
    controller.enqueue_single(
        "https://example.com/v",
        "動画",
        "MP4",
        job,
        cookies_path="/nonexistent/item_cookies.txt",
    )

    captured: dict = {}

    def _dv(url, job, cookies_path, **kwargs):
        captured["cookies_path"] = cookies_path
        captured["cookies_browser"] = kwargs.get("cookies_browser")
        controller._paused = True
        return None

    controller._downloader.download_video.side_effect = _dv

    with qtbot.waitSignal(controller.show_warning, timeout=2000):
        # グローバルは browser 指定でも、欠落アイテム cookies はそちらへ
        # フォールバックしないこと。
        assert controller.start(lambda: (None, "chrome")) is True
    qtbot.waitUntil(lambda: not controller.is_running, timeout=2000)
    assert captured["cookies_path"] is None
    assert captured["cookies_browser"] is None


# ── 並列ダウンロード（同時実行）・進捗表示 ──────────────────────────────────


def _make_parallel_controller(qtbot, concurrency, *, on_download=None):
    """distinct な Downloader を返すファクトリ付きのコントローラを作る。

    返り値は (controller, created_downloaders)。`on_download(*a, **k)` は
    各 worker の download_video 呼び出し時に実行される副作用。
    """
    tree = QTreeWidget()
    tree.setColumnCount(4)
    qtbot.addWidget(tree)
    created: list[MagicMock] = []

    def make_dl() -> MagicMock:
        dl = MagicMock()
        if on_download is not None:
            dl.download_video.side_effect = on_download
        created.append(dl)
        return dl

    ctrl = QueueController(
        MagicMock(),
        tree,
        make_downloader=make_dl,
        get_concurrency=lambda: concurrency,
    )
    return ctrl, created


def test_concurrent_workers_run_items_in_parallel(qtbot):
    """N>1 のとき複数アイテムが同時に downloading になること。"""
    release = threading.Event()
    started: list[int] = []
    started_lock = threading.Lock()

    def _block(*a, **k):
        with started_lock:
            started.append(1)
        release.wait(timeout=2)

    ctrl, _ = _make_parallel_controller(qtbot, 2, on_download=_block)
    a = _enqueue(ctrl, "A")
    b = _enqueue(ctrl, "B")

    assert ctrl.start(lambda: (None, None)) is True
    # 2 件が同時に download_video に入る（release 前に両方 started）
    qtbot.waitUntil(lambda: len(started) == 2, timeout=2000)
    assert sorted([a.status, b.status]) == ["downloading", "downloading"]

    release.set()
    qtbot.waitUntil(lambda: not ctrl.is_running, timeout=2000)
    assert a.status == "done" and b.status == "done"


def test_each_waiting_item_processed_exactly_once(qtbot):
    """取り出し排他: 各アイテムがちょうど 1 回ずつ処理される（二重処理なし）。"""
    counts: dict[str, int] = {}
    counts_lock = threading.Lock()

    def _count(url, job, *a, **k):
        with counts_lock:
            counts[url] = counts.get(url, 0) + 1

    tree = QTreeWidget()
    tree.setColumnCount(4)
    qtbot.addWidget(tree)

    def make_dl():
        dl = MagicMock()
        dl.download_video.side_effect = _count
        return dl

    ctrl = QueueController(
        MagicMock(), tree, make_downloader=make_dl, get_concurrency=lambda: 3
    )
    items = []
    for i in range(6):
        job = build_job_spec("fmt_best_mp4", Settings())
        items.append(
            ctrl.enqueue_single(f"https://example.com/{i}", f"V{i}", "MP4", job)
        )

    assert ctrl.start(lambda: (None, None)) is True
    qtbot.waitUntil(lambda: not ctrl.is_running, timeout=3000)
    assert all(it.status == "done" for it in items)
    assert counts == {f"https://example.com/{i}": 1 for i in range(6)}


def test_pause_cancels_all_active_downloaders(qtbot):
    """同時ダウンロード時、走行中の全 Downloader に request_cancel が呼ばれること。"""
    release = threading.Event()
    started: list[int] = []
    started_lock = threading.Lock()

    def _block(*a, **k):
        with started_lock:
            started.append(1)
        release.wait(timeout=2)

    ctrl, created = _make_parallel_controller(qtbot, 2, on_download=_block)
    _enqueue(ctrl, "A")
    _enqueue(ctrl, "B")

    assert ctrl.start(lambda: (None, None)) is True
    qtbot.waitUntil(lambda: len(started) == 2, timeout=2000)

    ctrl.pause()
    # 走行中の 2 つのワーカー Downloader それぞれに中断要求
    active = [dl for dl in created if dl.download_video.called]
    assert len(active) == 2
    for dl in active:
        dl.request_cancel.assert_called()

    release.set()
    qtbot.waitUntil(lambda: not ctrl.is_running, timeout=2000)


def test_progress_callback_routes_to_item(controller, qtbot):
    """worker が設定した status_callback で該当 item.progress が更新されること。"""

    def _dv(*a, **k):
        cb = controller._downloader.status_callback
        cb("ダウンロード中", 42.0)
        controller._paused = True  # 1 回で抜ける

    controller._downloader.download_video.side_effect = _dv
    item = _enqueue(controller, "進捗")

    assert controller.start(lambda: (None, None)) is True
    qtbot.waitUntil(lambda: not controller.is_running, timeout=2000)
    assert item.progress == 42.0


def test_refresh_tree_item_shows_progress_for_downloading(controller):
    """downloading 行のステータス列に進捗 % が表示されること。"""
    item = _enqueue(controller, "x")
    item.status = "downloading"
    item.progress = 33.3
    controller.refresh_tree_item(item)
    assert "33.3" in item.tree_item.text(3)


def test_overall_progress_reflects_finished_ratio(controller, qtbot):
    """全体進捗 = finished/total。done 1 / 全 2 → 50%。"""
    a = _enqueue(controller, "A")
    _enqueue(controller, "B")
    a.status = "done"

    with qtbot.waitSignal(controller.status_update, timeout=1000) as blocker:
        controller._emit_overall_progress()

    _, pct = blocker.args
    assert pct == 50.0


# ── アーカイブ無視（再取得） ──────────────────────────────────────────────


def test_mark_ignore_archive_sets_flag_on_waiting(controller):
    a = _enqueue(controller, "A")
    b = _enqueue(controller, "B")
    before = a.job.ignore_archive
    assert before is False

    n = controller.mark_ignore_archive([a, b])

    assert n == 2
    assert a.job.ignore_archive is True
    assert b.job.ignore_archive is True


def test_mark_ignore_archive_skips_non_waiting(controller):
    a = _enqueue(controller, "A")
    b = _enqueue(controller, "B")
    b.status = "downloading"

    n = controller.mark_ignore_archive([a, b])

    assert n == 1
    assert a.job.ignore_archive is True
    assert b.job.ignore_archive is False  # downloading は対象外


# ── 削除規則（remove_selected） ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "status, removable",
    [
        ("waiting", True),
        ("done", True),
        ("error", True),
        ("skipped", True),
        ("downloading", False),
        ("editing", False),
    ],
)
def test_remove_selected_honors_status_rules(controller, status, removable):
    """downloading / editing は削除不可、それ以外は削除可能（queue.md の削除規則）。"""
    item = _enqueue(controller, status)
    item.status = status
    item.tree_item.setSelected(True)

    controller.remove_selected()

    remaining = controller.find_item_for(item.tree_item)
    if removable:
        assert remaining is None
    else:
        assert remaining is item


def test_remove_selected_removes_only_eligible_in_mixed_selection(controller):
    waiting = _enqueue(controller, "W")
    downloading = _enqueue(controller, "D")
    downloading.status = "downloading"
    waiting.tree_item.setSelected(True)
    downloading.tree_item.setSelected(True)

    controller.remove_selected()

    assert controller.find_item_for(waiting.tree_item) is None
    assert controller.find_item_for(downloading.tree_item) is downloading
