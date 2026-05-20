import base64
import os
import sys
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from os.path import expanduser

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import get_resource_base, i18n
from .downloader import Downloader
from .formats import FORMAT_KEYS, build_720p_spec
from .i18n import t
from .log_dialog import LogDialog
from .original_format_panel import OriginalFormatPanel
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from .utils import strip_ansi

_ORIGINAL_KEY = "fmt_original"
_MP3_KEY = "fmt_mp3"
_WIN_W = 560
_WIN_H_DEFAULT = 480
_WIN_H_EXPANDED = 700


@dataclass
class _QueueItem:
    url: str
    format_id: str
    format_label: str
    format_spec: str | None
    subtitle_opts: dict | None
    title: str = ""
    mp3_bitrate: str | None = None
    embed_thumbnail: bool = False
    embed_metadata: bool = True
    embed_chapters: bool = True
    audio_codec: str = "mp3"
    video_container: str = "mp4"
    orig_settings: dict | None = None
    remux_only: bool = False
    audio_only: bool = False
    playlist_title: str | None = None
    playlist_index: int | None = None
    thumbnail_url: str | None = None
    status: str = "waiting"
    tree_item: QTreeWidgetItem | None = None


class _AppSignals(QObject):
    status_update = Signal(str, float)
    log_message = Signal(str)
    queue_item_refresh = Signal(object)  # _QueueItem
    add_button_reset = Signal()
    fetch_for_add_done = Signal(object)  # carries dict with result + metadata
    worker_done = Signal()
    show_error = Signal(str, str)
    show_warning = Signal(str, str)


class _QueueTree(QTreeWidget):
    """QTreeWidget with hover tooltips and a context menu for queue items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._get_item_cb = None  # (QTreeWidgetItem) -> _QueueItem | None
        self._context_menu_cb = None  # (items: list[_QueueItem]) -> None
        self._get_thumbnail_b64_cb = None  # (url: str) -> str | None
        self._is_editing = False

    def mousePressEvent(self, event):
        # 修飾キーなしの左クリックで選択済みアイテムを再クリックした場合は解除する
        if event.button() == Qt.MouseButton.LeftButton and not (
            event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        ):
            item = self.itemAt(event.position().toPoint())
            if item is not None and item.isSelected():
                item.setSelected(False)
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if self._context_menu_cb is None or self._get_item_cb is None:
            return
        selected = self.selectedItems()
        if not selected:
            return
        items = [qi for ti in selected if (qi := self._get_item_cb(ti)) is not None]
        waiting = [qi for qi in items if qi.status == "waiting"]
        menu = QMenu(self)
        act_copy_url = menu.addAction(t("ctx_copy_url"))
        menu.addSeparator()
        act_edit = menu.addAction(t("ctx_edit_format"))
        act_edit.setEnabled(bool(waiting) and not self._is_editing)
        chosen = menu.exec(event.globalPos())
        if chosen == act_copy_url:
            urls = "\n".join(qi.url for qi in items)
            QApplication.clipboard().setText(urls)
        elif chosen == act_edit and waiting and not self._is_editing:
            self._context_menu_cb(waiting)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            item = self.itemAt(event.pos())
            if item is not None and self._get_item_cb is not None:
                qi = self._get_item_cb(item)
                if qi is not None:
                    lines = []
                    if qi.thumbnail_url and self._get_thumbnail_b64_cb is not None:
                        b64 = self._get_thumbnail_b64_cb(qi.thumbnail_url)
                        if b64:
                            lines.append(f'<img src="{b64}" width="240" height="135">')
                    lines += [
                        f"<b>{t('tooltip_title')}:</b> {qi.title or qi.url}",
                        f"<b>{t('tooltip_url')}:</b> {qi.url}",
                    ]
                    if qi.playlist_title:
                        lines.append(
                            f"<b>{t('tooltip_playlist')}:</b> {qi.playlist_title}"
                        )
                    if qi.subtitle_opts:
                        langs = ", ".join(qi.subtitle_opts.get("subtitleslangs", []))
                        fmt = qi.subtitle_opts.get("subtitlesformat", "")
                        embed_lbl = (
                            t("orig_sub_embed")
                            if qi.subtitle_opts.get("embed")
                            else t("tooltip_sub_file")
                        )
                        sub_lbl = t("tooltip_subtitle")
                        lines.append(f"<b>{sub_lbl}:</b> {langs}  {fmt}  {embed_lbl}")
                    if qi.format_id == _ORIGINAL_KEY and qi.format_spec:
                        lines.append(
                            f"<b>{t('tooltip_format_spec')}:</b> {qi.format_spec}"
                        )
                    QToolTip.showText(
                        event.globalPos(),
                        "<br>".join(lines),
                        self.viewport(),
                        self.visualItemRect(item),
                    )
                    return True
            QToolTip.hideText()
            return True
        return super().viewportEvent(event)


class App(QMainWindow):
    _STATUS_KEY_MAP: dict[str, str] = {
        "waiting": "queue_status_waiting",
        "downloading": "queue_status_downloading",
        "done": "queue_status_done",
        "error": "queue_status_error",
        "editing": "queue_status_editing",
    }
    _STATUS_COLORS: dict[str, str] = {
        "downloading": "#1565c0",
        "done": "#2e7d32",
        "error": "#c62828",
        "editing": "#e65100",
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
        self._thumbnail_cache: dict[str, str] = {}  # thumbnail_url -> data URI
        self._thumbnail_fetching: set[str] = set()
        self._thumbnail_lock = threading.Lock()
        self._worker_running = False
        self._paused = False
        self._showing_pause_button = False
        self._item_counter = 0
        self._log_entries: list[str] = []
        self._log_dialog: LogDialog | None = None
        self._edit_mode = False
        self._editing_items: list[_QueueItem] = []

        self._signals = _AppSignals()
        self._signals.status_update.connect(self._update_status)
        self._signals.log_message.connect(self._log)
        self._signals.queue_item_refresh.connect(self._refresh_tree_item)
        self._signals.add_button_reset.connect(self._reset_add_button)
        self._signals.fetch_for_add_done.connect(self._on_fetch_for_add_done)
        self._signals.worker_done.connect(lambda: self._set_queue_running(False))
        self._signals.show_error.connect(
            lambda title, msg: QMessageBox.critical(self, title, msg)
        )
        self._signals.show_warning.connect(
            lambda title, msg: QMessageBox.warning(self, title, msg)
        )

        self.downloader = Downloader(
            self._resolve_download_path(),
            status_callback=self._on_status_from_thread,
            video_resolution=self._settings.video_resolution,
            mp3_bitrate=self._settings.mp3_bitrate,
            log_callback=self._on_downloader_log,
            output_template_video=self._settings.output_template_video,
            output_template_playlist=self._settings.output_template_playlist,
        )

        self._create_menu()
        self._create_widgets()
        QTimer.singleShot(0, self._check_dependencies)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _set_original_format_enabled(self, enabled: bool):
        if _ORIGINAL_KEY not in FORMAT_KEYS:
            return
        item = self.format_combo.model().item(FORMAT_KEYS.index(_ORIGINAL_KEY))
        if item is None:
            return
        if enabled:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _check_dependencies(self):
        missing = []
        if not os.path.isfile(self.downloader._ffmpeg_path):
            missing.append(t("warn_deps_missing_ffmpeg"))
        if not os.path.isfile(self.downloader._ffprobe_path):
            missing.append(t("warn_deps_missing_ffprobe"))
        if not os.path.isfile(self.downloader._deno_path):
            missing.append(t("warn_deps_missing_deno"))
        if missing:
            QMessageBox.warning(
                self,
                t("warn_deps_missing_title"),
                t("warn_deps_missing_body").format(tools="\n".join(missing)),
            )

    def _retranslate_ui(self):
        self.setWindowTitle(t("app_title"))

        self._file_menu.setTitle(t("menu_file"))
        self._act_settings.setText(t("menu_settings"))
        self._act_log.setText(t("menu_log"))
        if self._act_quit is not None:
            self._act_quit.setText(t("menu_quit"))

        self._lbl_url.setText(t("label_url"))
        self._lbl_format.setText(t("label_format"))

        old_idx = self.format_combo.currentIndex()
        self._format_display = self._build_format_display()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(self._format_display)
        self.format_combo.setCurrentIndex(old_idx)
        self.format_combo.blockSignals(False)
        if self._edit_mode and len(self._editing_items) > 1:
            self._set_original_format_enabled(False)
        self._on_format_changed(old_idx)

        self._original_panel.retranslate(
            self._settings.video_container, self._build_audio_label()
        )
        self._mp3_thumb_check.setText(t("mp3_embed_thumbnail"))

        self._lbl_queue_title.setText(f"<b>{t('queue_title')}</b>")
        self._queue_tree.setHeaderLabels(
            ["#", t("queue_col_title"), t("queue_col_format"), t("queue_col_status")]
        )

        self.add_button.setText(
            t("btn_apply_edit") if self._edit_mode else t("btn_add")
        )
        self._cancel_edit_button.setText(t("btn_cancel_edit"))
        self.start_queue_button.setText(t("btn_start_queue"))
        self.pause_queue_button.setText(t("btn_pause_queue"))
        self.remove_item_button.setText(t("btn_remove_item"))

        with self._queue_lock:
            items = list(self._queue_items)
        for item in items:
            self._refresh_tree_item(item)

        if not self._worker_running:
            self.status_label.setText(
                t("status_edit_mode") if self._edit_mode else t("status_ready")
            )

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
        container = self._settings.video_container.upper()
        result = []
        for k in FORMAT_KEYS:
            if k == "fmt_best_mp4":
                result.append(t("fmt_best_mp4").format(container=container))
            elif k == "fmt_720p":
                result.append(
                    t("fmt_720p").format(
                        resolution=self._settings.video_resolution,
                        container=container,
                    )
                )
            elif k == "fmt_mp3":
                if self._settings.audio_format == "flac":
                    result.append(t("fmt_flac"))
                else:
                    result.append(
                        t("fmt_mp3").format(bitrate=self._settings.mp3_bitrate)
                    )
            else:
                result.append(t(k))
        return result

    def _build_audio_label(self) -> str:
        if self._settings.audio_format == "flac":
            return "FLAC"
        return f"MP3 {self._settings.mp3_bitrate}kbps"

    def _adjust_video_container_for_multi_audio(
        self,
        video_container: str,
        multi_audio: bool,
        *,
        remux_only: bool,
        audio_only: bool,
    ) -> str:
        """複数音声選択時に動画コンテナを MKV へ自動昇格する。

        対象: 通常の結合モード (remux_only / audio_only ではない) で multi_audio=True、
        かつ現在のコンテナが mkv 以外のときのみ昇格する。
        昇格時はステータスバーへ通知メッセージを表示する。
        """
        if not multi_audio or remux_only or audio_only:
            return video_container
        if video_container == "mkv":
            return video_container
        self._update_status(t("status_multi_audio_mkv_promoted"), 0)
        return "mkv"

    def _notify_audio_only_truncated_if_needed(
        self, multi_audio: bool, audio_only: bool
    ) -> None:
        if multi_audio and audio_only:
            self._update_status(t("status_multi_audio_audio_only_truncated"), 0)

    # ── menu ─────────────────────────────────────────────────────────────────

    def _create_menu(self):
        menubar = self.menuBar()
        self._file_menu = menubar.addMenu(t("menu_file"))

        self._act_settings = QAction(t("menu_settings"), self)
        self._act_settings.setShortcut("Ctrl+,")
        self._act_settings.triggered.connect(self._open_settings)
        self._file_menu.addAction(self._act_settings)

        self._act_log = QAction(t("menu_log"), self)
        self._act_log.triggered.connect(self._open_log_dialog)
        self._file_menu.addAction(self._act_log)

        self._act_quit: QAction | None = None
        if sys.platform != "darwin":
            self._file_menu.addSeparator()
            self._act_quit = QAction(t("menu_quit"), self)
            self._act_quit.triggered.connect(self.close)
            self._file_menu.addAction(self._act_quit)

    # ── widgets ───────────────────────────────────────────────────────────────

    def _create_widgets(self):
        central = QWidget()
        self.setCentralWidget(central)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(10, 10, 10, 10)
        central_layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Vertical, central)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(6)

        # Top container: URL / Format / Original panel / Add button
        top_widget = QWidget()
        layout = QGridLayout(top_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setColumnStretch(1, 1)

        # Row 0: URL
        self._lbl_url = QLabel(t("label_url"))
        layout.addWidget(self._lbl_url, 0, 0, Qt.AlignmentFlag.AlignRight)
        self.url_entry = QLineEdit()
        layout.addWidget(self.url_entry, 0, 1, 1, 2)

        # Row 1: Format combo
        self._lbl_format = QLabel(t("label_format"))
        layout.addWidget(self._lbl_format, 1, 0, Qt.AlignmentFlag.AlignRight)
        self._format_display = self._build_format_display()
        self.format_combo = QComboBox()
        self.format_combo.addItems(self._format_display)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        layout.addWidget(self.format_combo, 1, 1, 1, 2)

        # Row 2a: Original format detail panel (hidden by default)
        self._original_panel = OriginalFormatPanel(
            top_widget,
            downloader=self.downloader,
            get_url=lambda: self.url_entry.text().strip(),
            get_cookies=self._resolve_cookies,
            update_status=lambda text, pct: self._signals.status_update.emit(text, pct),
        )
        self._original_panel.setVisible(False)
        self._original_panel.retranslate(
            self._settings.video_container, self._build_audio_label()
        )
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

        # Row 3: Add / Apply-edit button + Cancel-edit button
        add_frame = QWidget()
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(0, 8, 0, 2)
        self.add_button = QPushButton(t("btn_add"))
        self.add_button.clicked.connect(self._add_url)
        add_layout.addWidget(self.add_button)
        self._cancel_edit_button = QPushButton(t("btn_cancel_edit"))
        self._cancel_edit_button.clicked.connect(self._cancel_edit)
        self._cancel_edit_button.setVisible(False)
        add_layout.addWidget(self._cancel_edit_button)
        add_layout.addStretch()
        layout.addWidget(add_frame, 3, 0, 1, 3)

        self._splitter.addWidget(top_widget)

        # Bottom: Queue (expands)
        queue_box = QFrame()
        queue_box.setFrameShape(QFrame.Shape.StyledPanel)
        qbl = QVBoxLayout(queue_box)
        qbl.setContentsMargins(6, 6, 6, 6)
        qbl.setSpacing(4)

        self._lbl_queue_title = QLabel(f"<b>{t('queue_title')}</b>")
        qbl.addWidget(self._lbl_queue_title)

        self._queue_tree = _QueueTree()
        self._queue_tree._get_item_cb = self._get_queue_item_for_tree_item
        self._queue_tree._context_menu_cb = self._enter_edit_mode
        self._queue_tree._get_thumbnail_b64_cb = self._get_thumbnail_b64
        self._queue_tree.setColumnCount(4)
        self._queue_tree.setHeaderLabels(
            ["#", t("queue_col_title"), t("queue_col_format"), t("queue_col_status")]
        )
        hdr = self._queue_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(0, 36)
        hdr.resizeSection(2, 140)
        hdr.resizeSection(3, 120)
        self._queue_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
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

        self._splitter.addWidget(queue_box)
        # Top stays at sizeHint, queue stretches to fill extra space
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        central_layout.addWidget(self._splitter)

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
            self._mp3_frame.setVisible(self._settings.audio_format == "mp3")
            self.resize(_WIN_W, _WIN_H_DEFAULT)
        else:
            self._original_panel.setVisible(False)
            self._mp3_frame.setVisible(False)
            self.resize(_WIN_W, _WIN_H_DEFAULT)

    # ── queue operations ──────────────────────────────────────────────────────

    def _add_url(self):
        if self._edit_mode:
            self._apply_edit()
            return
        url = self.url_entry.text().strip()
        if not url:
            QMessageBox.warning(self, t("warn_title"), t("warn_no_url"))
            return

        idx = self.format_combo.currentIndex()
        format_id = FORMAT_KEYS[idx]
        format_label = self.format_combo.currentText()
        cookies_path, cookies_browser = self._resolve_cookies()

        if format_id == _ORIGINAL_KEY:
            audio_only = self._original_panel.get_audio_only()
            if audio_only and self._original_panel.is_audio_skipped():
                QMessageBox.warning(self, t("warn_title"), t("warn_skip_audio_only"))
                return
            if not audio_only and self._original_panel.is_both_skipped():
                QMessageBox.warning(self, t("warn_title"), t("warn_skip_both"))
                return
            format_spec = self._original_panel.get_format_spec()
            subtitle_opts = self._original_panel.get_subtitle_opts()
            remux_only = self._original_panel.get_remux_only()
            embed_thumbnail = self._original_panel.get_embed_thumbnail()
            embed_metadata = self._original_panel.get_embed_metadata()
            embed_chapters = self._original_panel.get_embed_chapters()
            orig_settings = self._original_panel.get_raw_settings()
            video_container = self._adjust_video_container_for_multi_audio(
                self._settings.video_container,
                self._original_panel.has_multiple_audio_selected(),
                remux_only=remux_only,
                audio_only=audio_only,
            )
            audio_codec = self._settings.audio_format if audio_only else "mp3"
            self._notify_audio_only_truncated_if_needed(
                self._original_panel.has_multiple_audio_selected(), audio_only
            )
            if audio_only:
                format_label = f"{format_label} → {self._build_audio_label()}"
            if self._original_panel.has_formats_loaded():
                self._enqueue_single(
                    url,
                    format_id,
                    format_label,
                    format_spec,
                    subtitle_opts,
                    self._original_panel.get_fetched_title(),
                    remux_only=remux_only,
                    embed_thumbnail=embed_thumbnail,
                    embed_metadata=embed_metadata,
                    embed_chapters=embed_chapters,
                    orig_settings=orig_settings,
                    video_container=video_container,
                    audio_codec=audio_codec,
                    audio_only=audio_only,
                )
                self.url_entry.clear()
                self._original_panel.reset()
                return
            self._start_add_thread(
                url,
                cookies_path,
                cookies_browser,
                format_id,
                format_label,
                format_spec,
                subtitle_opts,
                embed_thumbnail,
                remux_only=remux_only,
                embed_metadata=embed_metadata,
                embed_chapters=embed_chapters,
                orig_settings=orig_settings,
                video_container=video_container,
                audio_codec=audio_codec,
                audio_only=audio_only,
            )
        else:
            audio_codec = (
                self._settings.audio_format if format_id == _MP3_KEY else "mp3"
            )
            if format_id == _MP3_KEY:
                embed_thumbnail = (
                    bool(self._mp3_thumb_check.isChecked())
                    if audio_codec == "mp3"
                    else False
                )
            elif format_id in ("fmt_best_mp4", "fmt_720p"):
                embed_thumbnail = True
            else:
                embed_thumbnail = False
            self._start_add_thread(
                url,
                cookies_path,
                cookies_browser,
                format_id,
                format_label,
                None,
                None,
                embed_thumbnail,
                audio_codec=audio_codec,
                embed_metadata=True,
                embed_chapters=True,
                video_container=self._settings.video_container,
            )

    def _start_add_thread(
        self,
        url,
        cookies_path,
        cookies_browser,
        format_id,
        format_label,
        format_spec,
        subtitle_opts,
        embed_thumbnail=False,
        remux_only=False,
        audio_codec: str = "mp3",
        embed_metadata: bool = True,
        embed_chapters: bool = True,
        orig_settings: dict | None = None,
        video_container: str = "mp4",
        audio_only: bool = False,
    ):
        self.add_button.setEnabled(False)
        self.add_button.setText(t("btn_adding"))
        self._signals.status_update.emit(t("status_fetching_title"), 0)
        threading.Thread(
            target=self._run_fetch_for_add,
            args=(
                url,
                cookies_path,
                cookies_browser,
                format_id,
                format_label,
                format_spec,
                subtitle_opts,
                embed_thumbnail,
                remux_only,
                audio_codec,
                embed_metadata,
                embed_chapters,
                orig_settings,
                video_container,
                audio_only,
            ),
            daemon=True,
        ).start()

    def _run_fetch_for_add(
        self,
        url,
        cookies_path,
        cookies_browser,
        format_id,
        format_label,
        format_spec,
        subtitle_opts,
        embed_thumbnail=False,
        remux_only=False,
        audio_codec: str = "mp3",
        embed_metadata: bool = True,
        embed_chapters: bool = True,
        orig_settings: dict | None = None,
        video_container: str = "mp4",
        audio_only: bool = False,
    ):
        try:
            result = self.downloader.fetch_title_or_entries(
                url, cookies_path, cookies_browser
            )
            payload = {
                "result": result,
                "format_id": format_id,
                "format_label": format_label,
                "format_spec": format_spec,
                "subtitle_opts": subtitle_opts,
                "embed_thumbnail": embed_thumbnail,
                "remux_only": remux_only,
                "audio_codec": audio_codec,
                "embed_metadata": embed_metadata,
                "embed_chapters": embed_chapters,
                "orig_settings": orig_settings,
                "video_container": video_container,
                "audio_only": audio_only,
            }
            self._signals.fetch_for_add_done.emit(payload)
        except Exception as e:
            err_msg = strip_ansi(str(e))
            self._signals.status_update.emit(f"❌ {err_msg}", 0)
            self._signals.log_message.emit(f"❌ {err_msg}")
            self._signals.show_error.emit(
                t("err_title"), t("err_fetch_title").format(error=err_msg)
            )
        finally:
            self._signals.add_button_reset.emit()

    def _reset_add_button(self):
        self.add_button.setEnabled(True)
        self.add_button.setText(
            t("btn_apply_edit") if self._edit_mode else t("btn_add")
        )

    def _on_fetch_for_add_done(self, payload: dict):
        result = payload["result"]
        format_id = payload["format_id"]
        format_label = payload["format_label"]
        format_spec = payload["format_spec"]
        subtitle_opts = payload["subtitle_opts"]
        embed_thumbnail = payload["embed_thumbnail"]
        remux_only = payload["remux_only"]
        audio_codec = payload.get("audio_codec", "mp3")
        embed_metadata = payload.get("embed_metadata", True)
        embed_chapters = payload.get("embed_chapters", True)
        orig_settings = payload.get("orig_settings")
        video_container = payload.get("video_container", "mp4")
        audio_only = payload.get("audio_only", False)

        if result["type"] == "single":
            self._enqueue_single(
                result["url"],
                format_id,
                format_label,
                format_spec,
                subtitle_opts,
                result["title"],
                embed_thumbnail=embed_thumbnail,
                remux_only=remux_only,
                thumbnail_url=result.get("thumbnail_url"),
                audio_codec=audio_codec,
                embed_metadata=embed_metadata,
                embed_chapters=embed_chapters,
                orig_settings=orig_settings,
                video_container=video_container,
                audio_only=audio_only,
            )
            self.url_entry.clear()
            if format_id == _ORIGINAL_KEY:
                self._original_panel.reset()
            self._signals.status_update.emit(t("status_title_added"), 0)
        else:
            if format_id == _ORIGINAL_KEY:
                QMessageBox.warning(
                    self, t("warn_title"), t("warn_playlist_original_fmt")
                )
                self._signals.status_update.emit(t("status_ready"), 0)
                return
            entries = result["entries"]
            if not entries:
                QMessageBox.warning(self, t("warn_title"), t("warn_playlist_empty"))
                self._signals.status_update.emit(t("status_ready"), 0)
                return

            playlist_title = result.get("title", "")
            snap_spec = (
                build_720p_spec(self._settings.video_resolution, video_container)
                if format_id == "fmt_720p"
                else None
            )
            snap_bitrate = (
                self._settings.mp3_bitrate
                if format_id == "fmt_mp3" and audio_codec == "mp3"
                else None
            )

            batch: list[tuple[int, _QueueItem]] = []
            for idx, entry in enumerate(entries, start=1):
                self._item_counter += 1
                item = _QueueItem(
                    url=entry["url"],
                    format_id=format_id,
                    format_label=format_label,
                    format_spec=snap_spec,
                    subtitle_opts=None,
                    title=entry["title"],
                    mp3_bitrate=snap_bitrate,
                    embed_thumbnail=embed_thumbnail,
                    embed_metadata=embed_metadata,
                    embed_chapters=embed_chapters,
                    audio_codec=audio_codec,
                    video_container=video_container,
                    playlist_title=playlist_title,
                    playlist_index=idx,
                    thumbnail_url=entry.get("thumbnail_url"),
                )
                batch.append((self._item_counter, item))

            with self._queue_lock:
                for _, item in batch:
                    self._queue_items.append(item)

            for no, item in batch:
                short = item.title if len(item.title) <= 45 else item.title[:42] + "..."
                tree_item = QTreeWidgetItem(
                    [str(no), short, format_label, t("queue_status_waiting")]
                )
                item.tree_item = tree_item
                self._queue_tree.addTopLevelItem(tree_item)

            for _, item in batch:
                self._start_thumbnail_fetch(item.thumbnail_url)

            self.url_entry.clear()
            msg = t("status_playlist_added").format(count=len(batch))
            self._signals.status_update.emit(msg, 0)
            self._log(msg)

    def _enqueue_single(
        self,
        url,
        format_id,
        format_label,
        format_spec,
        subtitle_opts,
        title,
        embed_thumbnail=False,
        remux_only=False,
        thumbnail_url=None,
        audio_codec: str = "mp3",
        embed_metadata: bool = True,
        embed_chapters: bool = True,
        orig_settings: dict | None = None,
        video_container: str = "mp4",
        audio_only: bool = False,
    ):
        if format_id == "fmt_720p" and format_spec is None:
            format_spec = build_720p_spec(
                self._settings.video_resolution, video_container
            )
        is_audio_extraction = format_id == "fmt_mp3" or (
            format_id == _ORIGINAL_KEY and audio_only
        )
        mp3_bitrate = (
            self._settings.mp3_bitrate
            if is_audio_extraction and audio_codec == "mp3"
            else None
        )

        self._item_counter += 1
        item = _QueueItem(
            url=url,
            format_id=format_id,
            format_label=format_label,
            format_spec=format_spec,
            subtitle_opts=subtitle_opts,
            title=title,
            mp3_bitrate=mp3_bitrate,
            embed_thumbnail=embed_thumbnail,
            embed_metadata=embed_metadata,
            embed_chapters=embed_chapters,
            audio_codec=audio_codec,
            video_container=video_container,
            remux_only=remux_only,
            audio_only=audio_only,
            thumbnail_url=thumbnail_url,
            orig_settings=orig_settings,
        )
        with self._queue_lock:
            self._queue_items.append(item)

        short = title if len(title) <= 45 else title[:42] + "..."
        tree_item = QTreeWidgetItem(
            [str(self._item_counter), short, format_label, t("queue_status_waiting")]
        )
        item.tree_item = tree_item
        self._queue_tree.addTopLevelItem(tree_item)
        self._start_thumbnail_fetch(thumbnail_url)
        self._log(f"📥 {title}  [{format_label}]")

    def _get_queue_item_for_tree_item(
        self, tree_item: QTreeWidgetItem
    ) -> _QueueItem | None:
        with self._queue_lock:
            return next(
                (i for i in self._queue_items if i.tree_item is tree_item), None
            )

    # ── thumbnail cache ───────────────────────────────────────────────────────

    def _get_thumbnail_b64(self, thumbnail_url: str) -> str | None:
        with self._thumbnail_lock:
            return self._thumbnail_cache.get(thumbnail_url)

    def _start_thumbnail_fetch(self, thumbnail_url: str | None):
        if not thumbnail_url:
            return
        with self._thumbnail_lock:
            if (
                thumbnail_url in self._thumbnail_cache
                or thumbnail_url in self._thumbnail_fetching
            ):
                return
            self._thumbnail_fetching.add(thumbnail_url)
        threading.Thread(
            target=self._run_thumbnail_fetch,
            args=(thumbnail_url,),
            daemon=True,
        ).start()

    def _run_thumbnail_fetch(self, thumbnail_url: str):
        try:
            req = urllib.request.Request(
                thumbnail_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                ct = resp.headers.get("Content-Type", "image/jpeg")
                content_type = ct.split(";")[0].strip() if ct else "image/jpeg"
            b64 = base64.b64encode(data).decode("ascii")
            data_uri = f"data:{content_type};base64,{b64}"
            with self._thumbnail_lock:
                self._thumbnail_cache[thumbnail_url] = data_uri
                self._thumbnail_fetching.discard(thumbnail_url)
        except Exception:
            with self._thumbnail_lock:
                self._thumbnail_fetching.discard(thumbnail_url)

    def _refresh_tree_item(self, item: _QueueItem):
        if item is None or item.tree_item is None:
            return
        tree_item: QTreeWidgetItem = item.tree_item
        status_text = (
            t(self._STATUS_KEY_MAP[item.status])
            if item.status in self._STATUS_KEY_MAP
            else item.status
        )
        tree_item.setText(3, status_text)
        color_hex = self._STATUS_COLORS.get(item.status)
        if color_hex:
            c = QColor(color_hex)
            for col in range(4):
                tree_item.setForeground(col, c)
        else:
            for col in range(4):
                tree_item.setData(col, Qt.ItemDataRole.ForegroundRole, None)

    # ── edit mode ─────────────────────────────────────────────────────────────

    def _enter_edit_mode(self, items: list[_QueueItem]):
        with self._queue_lock:
            for item in items:
                if item.status != "waiting":
                    return
            for item in items:
                item.status = "editing"

        self._edit_mode = True
        self._editing_items = items
        self._queue_tree._is_editing = True

        for item in items:
            self._refresh_tree_item(item)

        if len(items) == 1:
            self.url_entry.setText(items[0].url)
        else:
            self.url_entry.setText(t("edit_multiple_selected").format(count=len(items)))
        self.url_entry.setReadOnly(True)

        first = items[0]
        target_format_id = first.format_id
        if len(items) > 1:
            self._set_original_format_enabled(False)
            if target_format_id == _ORIGINAL_KEY:
                target_format_id = FORMAT_KEYS[0]

        if target_format_id in FORMAT_KEYS:
            idx = FORMAT_KEYS.index(target_format_id)
            self.format_combo.blockSignals(True)
            self.format_combo.setCurrentIndex(idx)
            self.format_combo.blockSignals(False)
            self._on_format_changed(idx)

        if target_format_id == _MP3_KEY:
            self._mp3_thumb_check.setChecked(first.embed_thumbnail)

        if (
            target_format_id == _ORIGINAL_KEY
            and len(items) == 1
            and first.orig_settings
        ):
            self._original_panel.restore_from_settings(first.orig_settings)

        self.add_button.setText(t("btn_apply_edit"))
        self._cancel_edit_button.setVisible(True)

        if not self._worker_running:
            self.start_queue_button.setEnabled(False)

        self._update_status(t("status_edit_mode"), 0)

        if len(items) == 1 and first.format_id == _ORIGINAL_KEY:
            self._original_panel.trigger_fetch()

    def _apply_edit(self):
        idx = self.format_combo.currentIndex()
        if idx < 0 or idx >= len(FORMAT_KEYS):
            return
        format_id = FORMAT_KEYS[idx]
        format_label = self.format_combo.currentText()

        if len(self._editing_items) > 1 and format_id == _ORIGINAL_KEY:
            QMessageBox.warning(self, t("warn_title"), t("warn_edit_original_multi"))
            return

        if format_id == _ORIGINAL_KEY:
            if not self._original_panel.has_formats_loaded():
                QMessageBox.warning(
                    self, t("warn_title"), t("warn_edit_formats_not_loaded")
                )
                return
            audio_only = self._original_panel.get_audio_only()
            if audio_only and self._original_panel.is_audio_skipped():
                QMessageBox.warning(self, t("warn_title"), t("warn_skip_audio_only"))
                return
            if not audio_only and self._original_panel.is_both_skipped():
                QMessageBox.warning(self, t("warn_title"), t("warn_skip_both"))
                return
            format_spec = self._original_panel.get_format_spec()
            subtitle_opts = self._original_panel.get_subtitle_opts()
            remux_only = self._original_panel.get_remux_only()
            embed_thumbnail = self._original_panel.get_embed_thumbnail()
            embed_metadata = self._original_panel.get_embed_metadata()
            embed_chapters = self._original_panel.get_embed_chapters()
            orig_settings = self._original_panel.get_raw_settings()
            video_container = self._adjust_video_container_for_multi_audio(
                self._settings.video_container,
                self._original_panel.has_multiple_audio_selected(),
                remux_only=remux_only,
                audio_only=audio_only,
            )
            audio_codec = self._settings.audio_format if audio_only else "mp3"
            mp3_bitrate = (
                self._settings.mp3_bitrate
                if audio_only and audio_codec == "mp3"
                else None
            )
            self._notify_audio_only_truncated_if_needed(
                self._original_panel.has_multiple_audio_selected(), audio_only
            )
            if audio_only:
                format_label = f"{format_label} → {self._build_audio_label()}"
        elif format_id == _MP3_KEY:
            format_spec = None
            subtitle_opts = None
            remux_only = False
            audio_only = False
            audio_codec = self._settings.audio_format
            mp3_bitrate = self._settings.mp3_bitrate if audio_codec == "mp3" else None
            embed_thumbnail = (
                bool(self._mp3_thumb_check.isChecked())
                if audio_codec == "mp3"
                else False
            )
            embed_metadata = True
            embed_chapters = True
            orig_settings = None
            video_container = self._settings.video_container
        elif format_id in ("fmt_720p", "fmt_best_mp4"):
            format_spec = (
                build_720p_spec(
                    self._settings.video_resolution,
                    self._settings.video_container,
                )
                if format_id == "fmt_720p"
                else None
            )
            subtitle_opts = None
            remux_only = False
            audio_only = False
            audio_codec = "mp3"
            mp3_bitrate = None
            embed_thumbnail = True
            embed_metadata = True
            embed_chapters = True
            orig_settings = None
            video_container = self._settings.video_container
        else:
            format_spec = None
            subtitle_opts = None
            remux_only = False
            audio_only = False
            audio_codec = "mp3"
            mp3_bitrate = None
            embed_thumbnail = False
            embed_metadata = True
            embed_chapters = True
            orig_settings = None
            video_container = self._settings.video_container

        with self._queue_lock:
            for item in self._editing_items:
                item.format_id = format_id
                item.format_label = format_label
                item.format_spec = format_spec
                item.subtitle_opts = subtitle_opts
                item.remux_only = remux_only
                item.audio_only = audio_only
                item.audio_codec = audio_codec
                item.mp3_bitrate = mp3_bitrate
                item.embed_thumbnail = embed_thumbnail
                item.embed_metadata = embed_metadata
                item.embed_chapters = embed_chapters
                item.orig_settings = orig_settings
                item.video_container = video_container
                item.status = "waiting"

        for item in self._editing_items:
            if item.tree_item is not None:
                item.tree_item.setText(2, format_label)
            self._refresh_tree_item(item)

        self._log(
            t("log_edit_applied").format(
                count=len(self._editing_items), fmt=format_label
            )
        )
        self._exit_edit_mode()

    def _cancel_edit(self):
        with self._queue_lock:
            for item in self._editing_items:
                if item.status == "editing":
                    item.status = "waiting"
        for item in self._editing_items:
            self._refresh_tree_item(item)
        self._exit_edit_mode()

    def _exit_edit_mode(self):
        self._edit_mode = False
        self._editing_items = []
        self._queue_tree._is_editing = False

        self.url_entry.clear()
        self.url_entry.setReadOnly(False)

        self.add_button.setText(t("btn_add"))
        self._cancel_edit_button.setVisible(False)

        self._set_original_format_enabled(True)

        if not self._worker_running:
            self.start_queue_button.setEnabled(True)

        self._original_panel.reset()

        self._on_format_changed(self.format_combo.currentIndex())
        self._update_status(t("status_ready"), 0)

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
                item = next(
                    (i for i in self._queue_items if i.status == "waiting"), None
                )
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
                        t("warn_title"),
                        t("warn_cookies_not_found").format(path=cookies_path),
                    )
                    cookies_path = None

            try:
                self.downloader.download_video(
                    item.url,
                    item.format_id,
                    cookies_path,
                    item.format_spec,
                    item.subtitle_opts,
                    mp3_bitrate_override=item.mp3_bitrate,
                    embed_thumbnail=item.embed_thumbnail,
                    remux_only=item.remux_only,
                    cookies_browser=cookies_browser,
                    audio_codec=item.audio_codec,
                    embed_metadata=item.embed_metadata,
                    embed_chapters=item.embed_chapters,
                    video_container=item.video_container,
                    playlist_title=item.playlist_title,
                    playlist_index=item.playlist_index,
                    audio_only=item.audio_only,
                )
                with self._queue_lock:
                    item.status = "done"
            except Exception as e:
                with self._queue_lock:
                    item.status = "error"
                err_msg = strip_ansi(str(e))
                self._signals.log_message.emit(f"❌ {err_msg}")
                self._signals.show_error.emit(
                    t("err_title"), t("err_download").format(error=err_msg)
                )

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
                qi = next(
                    (i for i in self._queue_items if i.tree_item is tree_item), None
                )
                if qi is None or qi.status in ("downloading", "editing"):
                    continue
                self._queue_items.remove(qi)
            idx = self._queue_tree.indexOfTopLevelItem(tree_item)
            if idx >= 0:
                self._queue_tree.takeTopLevelItem(idx)

    # ── settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        old_lang = self._settings.language
        dialog = SettingsDialog(self, self._settings_manager)
        dialog.exec()
        self._settings = self._settings_manager.load()
        self.downloader.output_dir = self._resolve_download_path()
        self.downloader.video_resolution = self._settings.video_resolution
        self.downloader.mp3_bitrate = self._settings.mp3_bitrate
        self.downloader.output_template_video = self._settings.output_template_video
        self.downloader.output_template_playlist = (
            self._settings.output_template_playlist
        )

        if self._settings.language != old_lang:
            i18n.set_language(self._settings.language)
            self._retranslate_ui()
        else:
            old_idx = self.format_combo.currentIndex()
            self._format_display = self._build_format_display()
            self.format_combo.blockSignals(True)
            self.format_combo.clear()
            self.format_combo.addItems(self._format_display)
            self.format_combo.setCurrentIndex(old_idx)
            self.format_combo.blockSignals(False)
            self._original_panel.retranslate(
                self._settings.video_container, self._build_audio_label()
            )
            self._on_format_changed(old_idx)
            if self._edit_mode and len(self._editing_items) > 1:
                self._set_original_format_enabled(False)

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
