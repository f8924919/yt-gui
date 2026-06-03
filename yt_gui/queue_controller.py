"""ダウンロードキューの所有・走行・編集モード状態機械。

`App` から切り出された責務:

- `_QueueItem` のライフサイクル管理 (追加 / 削除 / ステータス更新)
- ダウンロードワーカースレッドの起動・一時停止
- 編集モード状態機械 (waiting → editing → waiting)

UI 副作用 (URL 入力欄・フォーマットコンボ・ボタン状態など) は
`edit_mode_entered` / `edit_mode_exited` / `log_message` / `status_update`
などのシグナル経由で `App` へ通知する。`_QueueTree` への直接操作
(行追加・削除・再描画) はメインスレッドから呼び出されるメソッド内
だけで行い、ワーカースレッドからは触らない。
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from yt_dlp.utils import DownloadCancelled

from .downloader import Downloader, DownloadSkipped
from .i18n import t
from .job_spec import JobSpec
from .utils import strip_ansi


@dataclass
class _QueueItem:
    """1 つのキュー項目。実行設定は `job` に集約。"""

    url: str
    title: str
    format_label: str
    job: JobSpec
    playlist_title: str | None = None
    playlist_index: int | None = None
    thumbnail_url: str | None = None
    status: str = "waiting"
    tree_item: QTreeWidgetItem | None = None

    @property
    def format_id(self) -> str:
        return self.job.format_id


_STATUS_KEY_MAP: dict[str, str] = {
    "waiting": "queue_status_waiting",
    "downloading": "queue_status_downloading",
    "done": "queue_status_done",
    "error": "queue_status_error",
    "editing": "queue_status_editing",
    "skipped": "queue_status_skipped",
}
_STATUS_COLORS: dict[str, str] = {
    "downloading": "#1565c0",
    "done": "#2e7d32",
    "error": "#c62828",
    "editing": "#e65100",
    "skipped": "#757575",
}


# cookies_path, cookies_browser を返すコールバック
CookiesResolver = Callable[[], tuple[str | None, str | None]]


class QueueController(QObject):
    """キューの所有とワーカースレッド管理。"""

    # ワーカースレッド → メインスレッド (QueuedConnection 経由で配送される)
    item_refresh = Signal(object)  # _QueueItem
    worker_done = Signal()
    status_update = Signal(str, float)
    log_message = Signal(str)
    show_error = Signal(str, str)
    show_warning = Signal(str, str)

    # メインスレッド内 (UI 側に委譲する操作通知)
    item_added = Signal(object)  # _QueueItem (サムネ取得などのフックポイント)
    edit_mode_entered = Signal(list)  # list[_QueueItem]
    edit_mode_exited = Signal()

    def __init__(
        self,
        downloader: Downloader,
        queue_tree: QTreeWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._downloader = downloader
        self._queue_tree = queue_tree

        self._items: list[_QueueItem] = []
        self._lock = threading.Lock()
        self._worker_running = False
        self._paused = False
        self._item_counter = 0

        self._edit_mode = False
        self._editing_items: list[_QueueItem] = []

    # ── 公開プロパティ ────────────────────────────────────────────────────

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    @property
    def editing_items(self) -> list[_QueueItem]:
        return list(self._editing_items)

    @property
    def is_running(self) -> bool:
        return self._worker_running

    def has_waiting(self) -> bool:
        with self._lock:
            return any(i.status == "waiting" for i in self._items)

    # ── キュー追加 ────────────────────────────────────────────────────────

    def enqueue_single(
        self,
        url: str,
        title: str,
        format_label: str,
        job: JobSpec,
        *,
        thumbnail_url: str | None = None,
    ) -> _QueueItem:
        self._item_counter += 1
        item = _QueueItem(
            url=url,
            title=title,
            format_label=format_label,
            job=job,
            thumbnail_url=thumbnail_url,
        )
        with self._lock:
            self._items.append(item)

        self._attach_tree_row(item, self._item_counter)
        self.item_added.emit(item)
        self.log_message.emit(f"📥 {title}  [{format_label}]")
        return item

    def enqueue_playlist(
        self,
        entries: list[dict],
        playlist_title: str,
        format_label: str,
        job: JobSpec,
    ) -> list[_QueueItem]:
        batch: list[tuple[int, _QueueItem]] = []
        for idx, entry in enumerate(entries, start=1):
            self._item_counter += 1
            item = _QueueItem(
                url=entry["url"],
                title=entry["title"],
                format_label=format_label,
                job=job,
                playlist_title=playlist_title,
                playlist_index=idx,
                thumbnail_url=entry.get("thumbnail_url"),
            )
            batch.append((self._item_counter, item))

        with self._lock:
            for _, item in batch:
                self._items.append(item)

        for no, item in batch:
            self._attach_tree_row(item, no)
        for _, item in batch:
            self.item_added.emit(item)
        return [item for _, item in batch]

    def _attach_tree_row(self, item: _QueueItem, counter: int) -> None:
        short = item.title if len(item.title) <= 45 else item.title[:42] + "..."
        tree_item = QTreeWidgetItem(
            [
                str(counter),
                short,
                item.format_label,
                t("queue_status_waiting"),
            ]
        )
        item.tree_item = tree_item
        self._queue_tree.addTopLevelItem(tree_item)

    # ── 検索 / 削除 ───────────────────────────────────────────────────────

    def find_item_for(self, tree_item: QTreeWidgetItem) -> _QueueItem | None:
        with self._lock:
            return next((i for i in self._items if i.tree_item is tree_item), None)

    def remove_selected(self) -> None:
        for tree_item in self._queue_tree.selectedItems():
            with self._lock:
                qi = next((i for i in self._items if i.tree_item is tree_item), None)
                if qi is None or qi.status in ("downloading", "editing"):
                    continue
                self._items.remove(qi)
            idx = self._queue_tree.indexOfTopLevelItem(tree_item)
            if idx >= 0:
                self._queue_tree.takeTopLevelItem(idx)

    # ── 行の表示更新 ──────────────────────────────────────────────────────

    def refresh_tree_item(self, item: _QueueItem) -> None:
        if item is None or item.tree_item is None:
            return
        tree_item = item.tree_item
        status_text = (
            t(_STATUS_KEY_MAP[item.status])
            if item.status in _STATUS_KEY_MAP
            else item.status
        )
        tree_item.setText(3, status_text)
        color_hex = _STATUS_COLORS.get(item.status)
        if color_hex:
            c = QColor(color_hex)
            for col in range(4):
                tree_item.setForeground(col, c)
        else:
            for col in range(4):
                tree_item.setData(col, Qt.ItemDataRole.ForegroundRole, None)

    def refresh_all_tree_items(self) -> None:
        """言語切替時など、全行を再描画する。"""
        with self._lock:
            items = list(self._items)
        for item in items:
            self.refresh_tree_item(item)

    # ── ワーカースレッド ─────────────────────────────────────────────────

    def start(self, cookies_resolver: CookiesResolver) -> bool:
        """ワーカーが起動できれば True、待機項目が無い・実行中なら False。"""
        if not self.has_waiting():
            return False
        if self._worker_running:
            return False

        self._paused = False
        self._worker_running = True
        self.log_message.emit(t("log_queue_started"))
        threading.Thread(
            target=self._worker, args=(cookies_resolver,), daemon=True
        ).start()
        return True

    def pause(self) -> None:
        self._paused = True
        # 進行中ダウンロードを即座に中断する（DownloadCancelled 経由）。
        # 中断されたアイテムは _worker 側で waiting に戻る。
        self._downloader.request_cancel()
        self.log_message.emit(t("log_queue_paused"))

    def _worker(self, cookies_resolver: CookiesResolver) -> None:
        while True:
            with self._lock:
                if self._paused:
                    self._worker_running = False
                    return
                item = next((i for i in self._items if i.status == "waiting"), None)
                if item is None:
                    self._worker_running = False
                    self.status_update.emit(t("status_ready"), 0)
                    self.log_message.emit(t("log_queue_done"))
                    self.worker_done.emit()
                    return
                item.status = "downloading"

            self.item_refresh.emit(item)
            self.log_message.emit(f"⬇️ {item.title}  [{item.format_label}]")

            def make_cb(qi: _QueueItem) -> Callable[[str, float], None]:
                def cb(text: str, percent: float) -> None:
                    self.status_update.emit(text, percent)
                    self.item_refresh.emit(qi)

                return cb

            self._downloader.status_callback = make_cb(item)

            cookies_path, cookies_browser = cookies_resolver()
            if cookies_path and not os.path.isfile(cookies_path):
                self.show_warning.emit(
                    t("warn_title"),
                    t("warn_cookies_not_found").format(path=cookies_path),
                )
                cookies_path = None

            try:
                self._downloader.download_video(
                    item.url,
                    item.job,
                    cookies_path,
                    cookies_browser=cookies_browser,
                    playlist_title=item.playlist_title,
                    playlist_index=item.playlist_index,
                )
                with self._lock:
                    item.status = "done"
            except DownloadCancelled:
                # 一時停止による中断。error 化せず waiting に戻して再開可能にする。
                with self._lock:
                    item.status = "waiting"
                self.log_message.emit(
                    t("log_download_cancelled").format(title=item.title)
                )
            except DownloadSkipped:
                # ダウンロードアーカイブに記録済み。error 化せず skipped にする。
                with self._lock:
                    item.status = "skipped"
                self.log_message.emit(
                    t("log_download_skipped").format(title=item.title)
                )
            except Exception as e:
                with self._lock:
                    item.status = "error"
                err_msg = strip_ansi(str(e))
                self.log_message.emit(f"❌ {err_msg}")
                self.show_error.emit(
                    t("err_title"), t("err_download").format(error=err_msg)
                )

            self.item_refresh.emit(item)

    # ── 編集モード ────────────────────────────────────────────────────────

    def enter_edit_mode(self, items: list[_QueueItem]) -> bool:
        """全アイテムが waiting なら編集モードへ移行。

        UI 側 (URL 入力欄・コンボ・ボタン・パネル) の更新は
        `edit_mode_entered` シグナルを受けた `App` 側で行う。
        """
        with self._lock:
            for item in items:
                if item.status != "waiting":
                    return False
            for item in items:
                item.status = "editing"

        self._edit_mode = True
        self._editing_items = items
        for item in items:
            self.refresh_tree_item(item)
        self.edit_mode_entered.emit(items)
        return True

    def apply_edit(self, format_label: str, job: JobSpec) -> None:
        """編集中アイテムの format_label と job を差し替えて waiting に戻す。"""
        with self._lock:
            for item in self._editing_items:
                item.format_label = format_label
                item.job = job
                item.status = "waiting"

        editing_count = len(self._editing_items)
        for item in self._editing_items:
            if item.tree_item is not None:
                item.tree_item.setText(2, format_label)
            self.refresh_tree_item(item)

        self.log_message.emit(
            t("log_edit_applied").format(count=editing_count, fmt=format_label)
        )
        self._exit_edit_mode()

    def cancel_edit(self) -> None:
        with self._lock:
            for item in self._editing_items:
                if item.status == "editing":
                    item.status = "waiting"
        for item in self._editing_items:
            self.refresh_tree_item(item)
        self._exit_edit_mode()

    def _exit_edit_mode(self) -> None:
        self._edit_mode = False
        self._editing_items = []
        self.edit_mode_exited.emit()
