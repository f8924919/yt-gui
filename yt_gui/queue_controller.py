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
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from yt_dlp.utils import DownloadCancelled

from .downloader import Downloader, DownloadSkipped
from .i18n import t
from .job_spec import JobSpec
from .settings import MAX_CONCURRENT_DOWNLOADS_MAX
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
    # アイテム固有の cookies.txt パス（ブラウザ拡張連携で付与）。None なら
    # グローバル設定の Cookies を使用する。詳細は
    # docs/spec/features/browser-extension.md。
    cookies_path: str | None = None
    status: str = "waiting"
    progress: float = 0.0  # ダウンロード進捗（0〜100）。行のステータス列に表示
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
        *,
        make_downloader: Callable[[], Downloader] | None = None,
        get_concurrency: Callable[[], int] | None = None,
    ) -> None:
        super().__init__(parent)
        self._downloader = downloader
        self._queue_tree = queue_tree
        # ワーカーごとに専用 Downloader を得るファクトリ。既定は単一インスタンスを
        # 返す（後方互換）。並列時に進捗コールバック/中断フラグの混線を避けるため、
        # App は現在の設定から distinct なインスタンスを生成するファクトリを渡す。
        self._make_downloader = make_downloader or (lambda: downloader)
        # 同時ダウンロード数（ワーカー数）を返す。既定は 1（逐次）。
        self._get_concurrency = get_concurrency or (lambda: 1)

        self._items: list[_QueueItem] = []
        self._lock = threading.Lock()
        self._active_workers = 0
        self._active_downloaders: list[Downloader] = []
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
        return self._active_workers > 0

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
        cookies_path: str | None = None,
    ) -> _QueueItem:
        self._item_counter += 1
        item = _QueueItem(
            url=url,
            title=title,
            format_label=format_label,
            job=job,
            thumbnail_url=thumbnail_url,
            cookies_path=cookies_path,
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
        if item.status == "downloading":
            status_text = t("queue_status_downloading_pct").format(
                percent=item.progress
            )
        elif item.status in _STATUS_KEY_MAP:
            status_text = t(_STATUS_KEY_MAP[item.status])
        else:
            status_text = item.status
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
        """ワーカーが起動できれば True、待機項目が無い・実行中なら False。

        設定の同時ダウンロード数だけワーカースレッドを起動する。
        """
        if not self.has_waiting():
            return False
        if self.is_running:
            return False

        n = max(1, min(self._get_concurrency(), MAX_CONCURRENT_DOWNLOADS_MAX))
        self._paused = False
        self.log_message.emit(t("log_queue_started"))
        with self._lock:
            self._active_workers = n
        for _ in range(n):
            downloader = self._make_downloader()
            threading.Thread(
                target=self._worker,
                args=(cookies_resolver, downloader),
                daemon=True,
            ).start()
        return True

    def pause(self) -> None:
        self._paused = True
        # 進行中ダウンロードを即座に中断する（DownloadCancelled 経由）。
        # 走行中の全ワーカーの Downloader に中断要求を出す（dedupe）。primary も
        # フォールバックとして含める（ワーカー未起動でも中断要求が届くように）。
        with self._lock:
            downloaders = [self._downloader, *self._active_downloaders]
        for downloader in dict.fromkeys(downloaders):
            downloader.request_cancel()
        self.log_message.emit(t("log_queue_paused"))

    def _emit_overall_progress(self) -> None:
        """キュー全体の進捗（完了数 / 総数）を status_update で通知する。"""
        with self._lock:
            statuses = [i.status for i in self._items]
        counted = [
            s
            for s in statuses
            if s in ("waiting", "downloading", "done", "error", "skipped")
        ]
        total = len(counted)
        if total == 0:
            self.status_update.emit(t("status_ready"), 0)
            return
        finished = sum(1 for s in counted if s in ("done", "error", "skipped"))
        percent = finished / total * 100
        self.status_update.emit(
            t("status_overall_progress").format(done=finished, total=total), percent
        )

    def _worker(
        self, cookies_resolver: CookiesResolver, downloader: Downloader
    ) -> None:
        with self._lock:
            self._active_downloaders.append(downloader)
        try:
            self._worker_loop(cookies_resolver, downloader)
        finally:
            with self._lock:
                if downloader in self._active_downloaders:
                    self._active_downloaders.remove(downloader)
                self._active_workers -= 1
                last = self._active_workers == 0
                paused = self._paused
            if last:
                self.worker_done.emit()
                if paused:
                    self._emit_overall_progress()
                else:
                    self.status_update.emit(t("status_ready"), 0)
                    self.log_message.emit(t("log_queue_done"))

    def _worker_loop(
        self, cookies_resolver: CookiesResolver, downloader: Downloader
    ) -> None:
        while True:
            with self._lock:
                if self._paused:
                    return
                item = next((i for i in self._items if i.status == "waiting"), None)
                if item is None:
                    return
                item.status = "downloading"
                item.progress = 0.0

            self.item_refresh.emit(item)
            self._emit_overall_progress()
            self.log_message.emit(f"⬇️ {item.title}  [{item.format_label}]")

            def make_cb(qi: _QueueItem) -> Callable[[str, float], None]:
                def cb(text: str, percent: float) -> None:
                    qi.progress = percent
                    self.item_refresh.emit(qi)
                    self._emit_overall_progress()

                return cb

            downloader.status_callback = make_cb(item)

            # アイテム固有 cookies（拡張連携）を最優先。無ければグローバル設定に
            # フォールバックする（docs/spec/features/queue.md「Cookies の解決」）。
            cookies_path: str | None
            cookies_browser: str | None
            if item.cookies_path:
                cookies_path, cookies_browser = item.cookies_path, None
            else:
                cookies_path, cookies_browser = cookies_resolver()
            if cookies_path and not os.path.isfile(cookies_path):
                self.show_warning.emit(
                    t("warn_title"),
                    t("warn_cookies_not_found").format(path=cookies_path),
                )
                cookies_path = None

            try:
                downloader.download_video(
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
            self._emit_overall_progress()

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

    # ── アーカイブ無視（再取得） ──────────────────────────────────────────

    def mark_ignore_archive(self, items: list[_QueueItem]) -> int:
        """待機中アイテムに ignore_archive フラグを立て、再取得対象にする（#76）。

        対象は `waiting` のアイテムのみ。`job` を
        `replace(job, ignore_archive=True)` で差し替え、ツリー行を再描画する。
        返り値は実際にフラグを立てた件数。
        """
        marked: list[_QueueItem] = []
        with self._lock:
            for item in items:
                if item.status != "waiting" or item.job.ignore_archive:
                    continue
                item.job = replace(item.job, ignore_archive=True)
                marked.append(item)

        for item in marked:
            self.refresh_tree_item(item)
        if marked:
            self.log_message.emit(
                t("log_ignore_archive_marked").format(count=len(marked))
            )
        return len(marked)
