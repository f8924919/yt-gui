import re
import sys
import threading
import os
from os.path import expanduser
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QFrame,
    QCheckBox, QStatusBar, QToolTip, QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction, QIcon, QColor

from .formats import FORMAT_KEYS, build_720p_spec
from .downloader import Downloader
from .original_format_panel import OriginalFormatPanel
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from .log_dialog import LogDialog
from . import get_resource_base
from . import i18n
from .i18n import t
from .utils import strip_ansi

_ORIGINAL_KEY = "fmt_original"
_MP3_KEY = "fmt_mp3"
_WIN_W = 560
_WIN_H_DEFAULT = 480
_WIN_H_EXPANDED = 700
_INVALID_PATH_CHARS = re.compile(r'[\\/:*?"<>|]')


def _sanitize_folder_name(name: str) -> str:
    name = _INVALID_PATH_CHARS.sub('_', name)
    return name[:100].strip() or "playlist"


@dataclass
class _QueueItem:
    url: str
    format_id: str
    format_label: str
    format_spec: str | None
    subtitle_opts: dict | None
    title: str = ""
    mp3_bitrate: str | None = None
    mp3_thumbnail: bool = False
    remux_only: bool = False
    playlist_folder: str | None = None
    status: str = "waiting"
    tree_item: object = None  # QTreeWidgetItem


class _AppSignals(QObject):
    status_update = Signal(str, float)
    log_message = Signal(str)
    queue_item_refresh = Signal(object)   # _QueueItem
    add_button_reset = Signal()
    fetch_for_add_done = Signal(object)   # carries dict with result + metadata
    worker_done = Signal()
    show_error = Signal(str, str)
    show_warning = Signal(str, str)


class _QueueTree(QTreeWidget):
    """QTreeWidget that shows hover tooltips for queue items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._get_item_cb = None  # set by App: (QTreeWidgetItem) -> _QueueItem | None
        self._hovered_tree_item: QTreeWidgetItem | None = None
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        tree_item = self.itemAt(event.pos())
        if tree_item != self._hovered_tree_item:
            self._hovered_tree_item = tree_item
            if tree_item is not None and self._get_item_cb is not None:
                qi = self._get_item_cb(tree_item)
                if qi is not None:
                    lines = [
                        f"<b>{t('tooltip_title')}:</b> {qi.title or qi.url}",
                        f"<b>{t('tooltip_url')}:</b> {qi.url}",
                    ]
                    if qi.playlist_folder:
                        lines.append(f"<b>{t('tooltip_playlist')}:</b> {qi.playlist_folder}")
                    if qi.subtitle_opts:
                        langs = ", ".join(qi.subtitle_opts.get("subtitleslangs", []))
                        fmt = qi.subtitle_opts.get("subtitlesformat", "")
                        embed_lbl = (t("orig_sub_embed") if qi.subtitle_opts.get("embed")
                                     else t("tooltip_sub_file"))
                        lines.append(f"<b>{t('tooltip_subtitle')}:</b> {langs}  {fmt}  {embed_lbl}")
                    if qi.format_id == _ORIGINAL_KEY and qi.format_spec:
                        lines.append(f"<b>{t('tooltip_format_spec')}:</b> {qi.format_spec}")
                    QToolTip.showText(event.globalPosition().toPoint(), "<br>".join(lines), self)
                    super().mouseMoveEvent(event)
                    return
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_tree_item = None
        QToolTip.hideText()
        super().leaveEvent(event)


class App(QMainWindow):
    _STATUS_KEY_MAP: dict[str, str] = {
        "waiting": "queue_status_waiting",
        "downloading": "queue_status_downloading",
        "done": "queue_status_done",
        "error": "queue_status_error",
    }
    _STATUS_COLORS: dict[str, str] = {
        "downloading": "#1565c0",
        "done": "#2e7d32",
        "error": "#c62828",
    }

    def __init__(self):
        super().__init__()

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()
        i18n.set_language(self._settings.language)

        self.setWindowTitle(t("app_title"))
        self.resize(_WIN_W, _WIN_H_DEFAULT)
        self.setMinimumSize(_WIN_W, 380)

        icon_path = os.path.join(get_resource_base(), "assets", "icon.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        if not self._settings.cookies_path and not self._settings.cookies_browser:
            default = os.path.join(get_resource_base(), "cookies.txt")
            if os.path.isfile(default):
                self._settings.cookies_path = default

        self._queue_items: list[_QueueItem] = []
        self._queue_lock = threading.Lock()
        self._worker_running = False
        self._paused = False
        self._showing_pause_button = False
        self._item_counter = 0
        self._log_entries: list[str] = []
        self._log_dialog: LogDialog | None = None

        self._signals = _AppSignals()
        self._signals.status_update.connect(self._update_status)
        self._signals.log_message.connect(self._log)
        self._signals.queue_item_refresh.connect(self._refresh_tree_item)
        self._signals.add_button_reset.connect(self._reset_add_button)
        self._signals.fetch_for_add_done.connect(self._on_fetch_for_add_done)
        self._signals.worker_done.connect(lambda: self._set_queue_running(False))
        self._signals.show_error.connect(
            lambda title, msg: QMessageBox.critical(self, title, msg))
        self._signals.show_warning.connect(
            lambda title, msg: QMessageBox.warning(self, title, msg))

        self.downloader = Downloader(
            self._resolve_download_path(),
            status_callback=self._on_status_from_thread,
            video_resolution=self._settings.video_resolution,
            mp3_bitrate=self._settings.mp3_bitrate,
            log_callback=self._on_downloader_log,
        )

        self._create_menu()
        self._create_widgets()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _resolve_download_path(self) -> str:
        path = self._settings.download_path
        return path if path else os.path.join(expanduser("~"), "Downloads")

    def _resolve_cookies(self) -> tuple[str | None, str | None]:
        browser = self._settings.cookies_browser or None
        if browser:
            return None, browser
        path = self._settings.cookies_path or None
        if path and not os.path.isfile(path):
            path = None
        return path, None

    def _build_format_display(self) -> list[str]:
        result = []
        for k in FORMAT_KEYS:
            if k == "fmt_720p":
                result.append(t("fmt_720p").format(resolution=self._settings.video_resolution))
            elif k == "fmt_mp3":
                result.append(t("fmt_mp3").format(bitrate=self._settings.mp3_bitrate))
            else:
                result.append(t(k))
        return result

    # ── menu ─────────────────────────────────────────────────────────────────

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(t("menu_file"))

        act_settings = QAction(t("menu_settings"), self)
        act_settings.setShortcut("Ctrl+,")
        act_settings.triggered.connect(self._open_settings)
        file_menu.addAction(act_settings)

        act_log = QAction(t("menu_log"), self)
        act_log.triggered.connect(self._open_log_dialog)
        file_menu.addAction(act_log)

        if sys.platform != "darwin":
            file_menu.addSeparator()
            act_quit = QAction(t("menu_quit"), self)
            act_quit.triggered.connect(self.close)
            file_menu.addAction(act_quit)

    # ── widgets ───────────────────────────────────────────────────────────────

    def _create_widgets(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QGridLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setColumnStretch(1, 1)

        # Row 0: URL
        layout.addWidget(QLabel(t("label_url")), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.url_entry = QLineEdit()
        layout.addWidget(self.url_entry, 0, 1, 1, 2)

        # Row 1: Format combo
        layout.addWidget(QLabel(t("label_format")), 1, 0, Qt.AlignmentFlag.AlignRight)
        self._format_display = self._build_format_display()
        self.format_combo = QComboBox()
        self.format_combo.addItems(self._format_display)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        layout.addWidget(self.format_combo, 1, 1, 1, 2)

        # Row 2a: Original format detail panel (hidden by default)
        self._original_panel = OriginalFormatPanel(
            central,
            downloader=self.downloader,
            get_url=lambda: self.url_entry.text().strip(),
            get_cookies=self._resolve_cookies,
            update_status=lambda text, pct: self._signals.status_update.emit(text, pct),
        )
        self._original_panel.setVisible(False)
        layout.addWidget(self._original_panel, 2, 0, 1, 3)

        # Row 2b: MP3 thumbnail option (hidden by default)
        self._mp3_frame = QWidget()
        mp3_layout = QHBoxLayout(self._mp3_frame)
        mp3_layout.setContentsMargins(0, 0, 0, 0)
        self._mp3_thumb_check = QCheckBox(t("mp3_embed_thumbnail"))
        mp3_layout.addWidget(self._mp3_thumb_check)
        mp3_layout.addStretch()
        self._mp3_frame.setVisible(False)
        layout.addWidget(self._mp3_frame, 2, 1, 1, 2)

        # Row 3: Add button
        add_frame = QWidget()
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(0, 8, 0, 2)
        self.add_button = QPushButton(t("btn_add"))
        self.add_button.clicked.connect(self._add_url)
        add_layout.addWidget(self.add_button)
        add_layout.addStretch()
        layout.addWidget(add_frame, 3, 0, 1, 3)

        # Row 4: Queue (expands)
        queue_box = QFrame()
        queue_box.setFrameShape(QFrame.Shape.StyledPanel)
        qbl = QVBoxLayout(queue_box)
        qbl.setContentsMargins(6, 6, 6, 6)
        qbl.setSpacing(4)

        qbl.addWidget(QLabel(f"<b>{t('queue_title')}</b>"))

        self._queue_tree = _QueueTree()
        self._queue_tree._get_item_cb = self._get_queue_item_for_tree_item
        self._queue_tree.setColumnCount(4)
        self._queue_tree.setHeaderLabels(
            ["#", t("queue_col_title"), t("queue_col_format"), t("queue_col_status")])
        hdr = self._queue_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(0, 36)
        hdr.resizeSection(2, 140)
        hdr.resizeSection(3, 120)
        self._queue_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._queue_tree.setRootIsDecorated(False)
        self._queue_tree.setAlternatingRowColors(True)
        qbl.addWidget(self._queue_tree)

        queue_btn_frame = QWidget()
        qbfl = QHBoxLayout(queue_btn_frame)
        qbfl.setContentsMargins(0, 0, 0, 0)
        self.start_queue_button = QPushButton(t("btn_start_queue"))
        self.start_queue_button.clicked.connect(self._start_queue)
        self.pause_queue_button = QPushButton(t("btn_pause_queue"))
        self.pause_queue_button.clicked.connect(self._pause_queue)
        self.pause_queue_button.setVisible(False)
        self.remove_item_button = QPushButton(t("btn_remove_item"))
        self.remove_item_button.clicked.connect(self._remove_selected)
        qbfl.addWidget(self.start_queue_button)
        qbfl.addWidget(self.pause_queue_button)
        qbfl.addWidget(self.remove_item_button)
        qbfl.addStretch()
        qbl.addWidget(queue_btn_frame)

        layout.addWidget(queue_box, 4, 0, 1, 3)
        layout.setRowStretch(4, 1)

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_label = QLabel(t("status_ready"))
        status_bar.addWidget(self.status_label, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(160)
        self.progress_bar.setTextVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)

    # ── format / panel visibility ─────────────────────────────────────────────

    def _on_format_changed(self, index: int):
        if index < 0 or index >= len(FORMAT_KEYS):
            return
        format_id = FORMAT_KEYS[index]
        if format_id == _ORIGINAL_KEY:
            self._original_panel.setVisible(True)
            self._mp3_frame.setVisible(False)
            self.resize(_WIN_W, _WIN_H_EXPANDED)
        elif format_id == _MP3_KEY:
            self._original_panel.setVisible(False)
            self._mp3_frame.setVisible(True)
            self.resize(_WIN_W, _WIN_H_DEFAULT)
        else:
            self._original_panel.setVisible(False)
            self._mp3_frame.setVisible(False)
            self.resize(_WIN_W, _WIN_H_DEFAULT)

    # ── queue operations ──────────────────────────────────────────────────────

    def _add_url(self):
        url = self.url_entry.text().strip()
        if not url:
            QMessageBox.warning(self, t("warn_title"), t("warn_no_url"))
            return

        idx = self.format_combo.currentIndex()
        format_id = FORMAT_KEYS[idx]
        format_label = self.format_combo.currentText()
        cookies_path, cookies_browser = self._resolve_cookies()

        if format_id == _ORIGINAL_KEY:
            if self._original_panel.is_both_skipped():
                QMessageBox.warning(self, t("warn_title"), t("warn_skip_both"))
                return
            format_spec = self._original_panel.get_format_spec()
            subtitle_opts = self._original_panel.get_subtitle_opts()
            remux_only = self._original_panel.get_remux_only()
            if self._original_panel.has_formats_loaded():
                self._enqueue_single(url, format_id, format_label, format_spec, subtitle_opts,
                                     self._original_panel.get_fetched_title(), remux_only=remux_only)
                self.url_entry.clear()
                return
            self._start_add_thread(url, cookies_path, cookies_browser, format_id, format_label,
                                   format_spec, subtitle_opts, False, remux_only=remux_only)
        else:
            mp3_thumbnail = self._mp3_thumb_check.isChecked() if format_id == _MP3_KEY else False
            self._start_add_thread(url, cookies_path, cookies_browser, format_id, format_label,
                                   None, None, mp3_thumbnail)

    def _start_add_thread(self, url, cookies_path, cookies_browser, format_id, format_label,
                          format_spec, subtitle_opts, mp3_thumbnail=False, remux_only=False):
        self.add_button.setEnabled(False)
        self.add_button.setText(t("btn_adding"))
        self._signals.status_update.emit(t("status_fetching_title"), 0)
        threading.Thread(
            target=self._run_fetch_for_add,
            args=(url, cookies_path, cookies_browser, format_id, format_label,
                  format_spec, subtitle_opts, mp3_thumbnail, remux_only),
            daemon=True,
        ).start()

    def _run_fetch_for_add(self, url, cookies_path, cookies_browser, format_id, format_label,
                           format_spec, subtitle_opts, mp3_thumbnail=False, remux_only=False):
        try:
            result = self.downloader.fetch_title_or_entries(url, cookies_path, cookies_browser)
            payload = {
                'result': result,
                'format_id': format_id,
                'format_label': format_label,
                'format_spec': format_spec,
                'subtitle_opts': subtitle_opts,
                'mp3_thumbnail': mp3_thumbnail,
                'remux_only': remux_only,
            }
            self._signals.fetch_for_add_done.emit(payload)
        except Exception as e:
            err_msg = strip_ansi(str(e))
            self._signals.status_update.emit(f"❌ {err_msg}", 0)
            self._signals.log_message.emit(f"❌ {err_msg}")
            self._signals.show_error.emit(t("err_title"), t("err_fetch_title").format(error=err_msg))
        finally:
            self._signals.add_button_reset.emit()

    def _reset_add_button(self):
        self.add_button.setEnabled(True)
        self.add_button.setText(t("btn_add"))

    def _on_fetch_for_add_done(self, payload: dict):
        result = payload['result']
        format_id = payload['format_id']
        format_label = payload['format_label']
        format_spec = payload['format_spec']
        subtitle_opts = payload['subtitle_opts']
        mp3_thumbnail = payload['mp3_thumbnail']
        remux_only = payload['remux_only']

        if result['type'] == 'single':
            self._enqueue_single(
                result['url'], format_id, format_label, format_spec, subtitle_opts,
                result['title'], mp3_thumbnail, remux_only=remux_only,
            )
            self.url_entry.clear()
            self._signals.status_update.emit(t("status_title_added"), 0)
        else:
            if format_id == _ORIGINAL_KEY:
                QMessageBox.warning(self, t("warn_title"), t("warn_playlist_original_fmt"))
                self._signals.status_update.emit(t("status_ready"), 0)
                return
            entries = result['entries']
            if not entries:
                QMessageBox.warning(self, t("warn_title"), t("warn_playlist_empty"))
                self._signals.status_update.emit(t("status_ready"), 0)
                return

            playlist_folder = _sanitize_folder_name(result.get('title', ''))
            snap_spec = (build_720p_spec(self._settings.video_resolution)
                         if format_id == "fmt_720p" else None)
            snap_bitrate = self._settings.mp3_bitrate if format_id == "fmt_mp3" else None

            batch: list[tuple[int, _QueueItem]] = []
            for entry in entries:
                self._item_counter += 1
                item = _QueueItem(
                    url=entry['url'],
                    format_id=format_id,
                    format_label=format_label,
                    format_spec=snap_spec,
                    subtitle_opts=None,
                    title=entry['title'],
                    mp3_bitrate=snap_bitrate,
                    mp3_thumbnail=mp3_thumbnail,
                    playlist_folder=playlist_folder,
                )
                batch.append((self._item_counter, item))

            with self._queue_lock:
                for _, item in batch:
                    self._queue_items.append(item)

            for no, item in batch:
                short = item.title if len(item.title) <= 45 else item.title[:42] + "..."
                tree_item = QTreeWidgetItem(
                    [str(no), short, format_label, t("queue_status_waiting")])
                item.tree_item = tree_item
                self._queue_tree.addTopLevelItem(tree_item)

            self.url_entry.clear()
            msg = t("status_playlist_added").format(count=len(batch))
            self._signals.status_update.emit(msg, 0)
            self._log(msg)

    def _enqueue_single(self, url, format_id, format_label, format_spec, subtitle_opts, title,
                        mp3_thumbnail=False, remux_only=False):
        if format_id == "fmt_720p" and format_spec is None:
            format_spec = build_720p_spec(self._settings.video_resolution)
        mp3_bitrate = self._settings.mp3_bitrate if format_id == "fmt_mp3" else None

        self._item_counter += 1
        item = _QueueItem(
            url=url,
            format_id=format_id,
            format_label=format_label,
            format_spec=format_spec,
            subtitle_opts=subtitle_opts,
            title=title,
            mp3_bitrate=mp3_bitrate,
            mp3_thumbnail=mp3_thumbnail,
            remux_only=remux_only,
        )
        with self._queue_lock:
            self._queue_items.append(item)

        short = title if len(title) <= 45 else title[:42] + "..."
        tree_item = QTreeWidgetItem(
            [str(self._item_counter), short, format_label, t("queue_status_waiting")])
        item.tree_item = tree_item
        self._queue_tree.addTopLevelItem(tree_item)
        self._log(f"📥 {title}  [{format_label}]")

    def _get_queue_item_for_tree_item(self, tree_item: QTreeWidgetItem) -> '_QueueItem | None':
        with self._queue_lock:
            return next((i for i in self._queue_items if i.tree_item is tree_item), None)

    def _refresh_tree_item(self, item: _QueueItem):
        if item is None or item.tree_item is None:
            return
        tree_item: QTreeWidgetItem = item.tree_item
        status_text = (t(self._STATUS_KEY_MAP[item.status])
                       if item.status in self._STATUS_KEY_MAP else item.status)
        tree_item.setText(3, status_text)
        color_hex = self._STATUS_COLORS.get(item.status)
        if color_hex:
            c = QColor(color_hex)
            for col in range(4):
                tree_item.setForeground(col, c)
        else:
            for col in range(4):
                tree_item.setForeground(col, QColor())

    # ── queue control ─────────────────────────────────────────────────────────

    def _start_queue(self):
        with self._queue_lock:
            has_waiting = any(i.status == "waiting" for i in self._queue_items)
        if not has_waiting:
            QMessageBox.warning(self, t("warn_title"), t("warn_queue_empty"))
            return
        if self._worker_running:
            return

        self._paused = False
        self._worker_running = True
        self._set_queue_running(True)
        self._log(t("log_queue_started"))
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            with self._queue_lock:
                if self._paused:
                    self._worker_running = False
                    return
                item = next((i for i in self._queue_items if i.status == "waiting"), None)
                if item is None:
                    self._worker_running = False
                    self._signals.status_update.emit(t("status_ready"), 0)
                    self._signals.log_message.emit(t("log_queue_done"))
                    self._signals.worker_done.emit()
                    return
                item.status = "downloading"

            self._signals.queue_item_refresh.emit(item)
            self._signals.log_message.emit(f"⬇️ {item.title}  [{item.format_label}]")

            def make_cb(qi):
                def cb(text, percent):
                    self._signals.status_update.emit(text, percent)
                    self._signals.queue_item_refresh.emit(qi)
                return cb

            self.downloader.status_callback = make_cb(item)

            cookies_browser = self._settings.cookies_browser or None
            if cookies_browser:
                cookies_path = None
            else:
                cookies_path = self._settings.cookies_path or None
                if cookies_path and not os.path.isfile(cookies_path):
                    self._signals.show_warning.emit(
                        t("warn_title"), t("warn_cookies_not_found").format(path=cookies_path))
                    cookies_path = None

            try:
                output_dir_override = None
                if item.playlist_folder:
                    output_dir_override = os.path.join(
                        self._resolve_download_path(), item.playlist_folder)
                self.downloader.download_video(
                    item.url, item.format_id, cookies_path, item.format_spec, item.subtitle_opts,
                    mp3_bitrate_override=item.mp3_bitrate,
                    embed_thumbnail=item.mp3_thumbnail,
                    remux_only=item.remux_only,
                    output_dir_override=output_dir_override,
                    cookies_browser=cookies_browser,
                )
                with self._queue_lock:
                    item.status = "done"
            except Exception as e:
                with self._queue_lock:
                    item.status = "error"
                err_msg = strip_ansi(str(e))
                self._signals.log_message.emit(f"❌ {err_msg}")
                self._signals.show_error.emit(
                    t("err_title"), t("err_download").format(error=err_msg))

            self._signals.queue_item_refresh.emit(item)

    def _pause_queue(self):
        self._paused = True
        self._log(t("log_queue_paused"))
        self._set_queue_running(False)

    def _set_queue_running(self, running: bool):
        if running == self._showing_pause_button:
            return
        self.start_queue_button.setVisible(not running)
        self.pause_queue_button.setVisible(running)
        self._showing_pause_button = running

    def _remove_selected(self):
        for tree_item in self._queue_tree.selectedItems():
            with self._queue_lock:
                qi = next((i for i in self._queue_items if i.tree_item is tree_item), None)
                if qi is None or qi.status == "downloading":
                    continue
                self._queue_items.remove(qi)
            idx = self._queue_tree.indexOfTopLevelItem(tree_item)
            if idx >= 0:
                self._queue_tree.takeTopLevelItem(idx)

    # ── settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        dialog = SettingsDialog(self, self._settings_manager)
        dialog.exec()
        self._settings = self._settings_manager.load()
        self.downloader.output_dir = self._resolve_download_path()
        self.downloader.video_resolution = self._settings.video_resolution
        self.downloader.mp3_bitrate = self._settings.mp3_bitrate
        old_idx = self.format_combo.currentIndex()
        self._format_display = self._build_format_display()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(self._format_display)
        self.format_combo.setCurrentIndex(old_idx)
        self.format_combo.blockSignals(False)

    # ── status / log ──────────────────────────────────────────────────────────

    def _on_status_from_thread(self, text: str, percent: float):
        self._signals.status_update.emit(text, percent)

    def _update_status(self, text: str, percent: float):
        self.status_label.setText(text)
        self.progress_bar.setValue(int(percent))

    def _on_downloader_log(self, msg: str):
        self._signals.log_message.emit(msg)

    def _log(self, msg: str):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._log_entries.append(entry)
        if len(self._log_entries) > 2000:
            self._log_entries = self._log_entries[-2000:]
        if self._log_dialog is not None:
            self._log_dialog.append(entry)

    def _open_log_dialog(self):
        if self._log_dialog is not None and self._log_dialog.isVisible():
            self._log_dialog.raise_()
            self._log_dialog.activateWindow()
            return
        self._log_dialog = LogDialog(self, on_close=self._on_log_dialog_close)
        self._log_dialog.load(self._log_entries)
        self._log_dialog.show()

    def _on_log_dialog_close(self):
        self._log_dialog = None
