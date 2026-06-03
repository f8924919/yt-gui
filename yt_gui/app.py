import os
import sys
from collections.abc import Callable
from datetime import datetime
from os.path import expanduser

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
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
    QStatusBar,
    QToolTip,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from . import get_resource_base, get_version, i18n
from .downloader import Downloader
from .formats import FORMAT_KEYS
from .i18n import t
from .job_spec import JobSpec, build_job_spec
from .log_dialog import LogDialog
from .original_format_dialog import OriginalFormatDialog
from .queue_controller import QueueController, _QueueItem
from .settings import (
    SettingsManager,
    build_proxy_url,
    build_rate_limit,
    resolve_download_archive_path,
)
from .settings_dialog import SettingsDialog
from .threading_utils import run_in_thread
from .thumbnail_cache import ThumbnailCache
from .utils import strip_ansi

_ORIGINAL_KEY = "fmt_original"
_MP3_KEY = "fmt_mp3"
# オリジナル形式の詳細設定を別画面化し、メイン上段が幅を要求しなくなったため
# 既定幅を狭めた（旧 940）。最小幅は手動で更に絞れるよう既定より小さくする。
_WIN_W = 760
_WIN_MIN_W = 560
_WIN_H_DEFAULT = 480


class _AppSignals(QObject):
    """App 自身がバックグラウンドスレッドから emit する用のシグナル。

    キュー走行ワーカー由来のシグナルは `QueueController` に移管済み。
    URL タイトル取得スレッドは `threading_utils.run_in_thread` に移行し、
    `_AppSignals` には共通ハンドラ (status / log / error) のみが残る。
    """

    status_update = Signal(str, float)
    log_message = Signal(str)
    show_error = Signal(str, str)


class _QueueTree(QTreeWidget):
    """QTreeWidget with hover tooltips and a context menu for queue items.

    依存はコンストラクタで注入する。
    - `get_item`: ツリー行 → `_QueueItem` の解決 (`QueueController.find_item_for`)
    - `get_thumbnail_b64`: サムネ URL → data URI (`ThumbnailCache.get`)
    - `is_editing`: 編集モード中かを返す getter (`QueueController.edit_mode`)

    「形式を変更」コンテキストメニュー操作は `edit_format_requested(list)`
    シグナルで通知する（外部からの属性書き込みは行わない）。
    """

    edit_format_requested = Signal(list)  # list[_QueueItem]

    def __init__(
        self,
        parent=None,
        *,
        get_item: Callable[[object], _QueueItem | None],
        get_thumbnail_b64: Callable[[str], str | None],
        is_editing: Callable[[], bool],
    ):
        super().__init__(parent)
        self._get_item = get_item
        self._get_thumbnail_b64 = get_thumbnail_b64
        self._is_editing = is_editing

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

    def _edit_targets(self, items: list[_QueueItem]) -> list[_QueueItem]:
        """「形式を変更」の対象となる `waiting` アイテムの部分集合を返す。

        編集モード中、または `waiting` が無い場合は空リスト（＝編集不可）。
        メニュー項目の活性判定と `edit_format_requested` の発火判定で共用する。
        """
        if self._is_editing():
            return []
        return [qi for qi in items if qi.status == "waiting"]

    def contextMenuEvent(self, event):
        selected = self.selectedItems()
        if not selected:
            return
        items = [qi for ti in selected if (qi := self._get_item(ti)) is not None]
        targets = self._edit_targets(items)
        menu = QMenu(self)
        act_copy_url = menu.addAction(t("ctx_copy_url"))
        menu.addSeparator()
        act_edit = menu.addAction(t("ctx_edit_format"))
        act_edit.setEnabled(bool(targets))
        chosen = menu.exec(event.globalPos())
        if chosen == act_copy_url:
            urls = "\n".join(qi.url for qi in items)
            QApplication.clipboard().setText(urls)
        elif chosen == act_edit and targets:
            self.edit_format_requested.emit(targets)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            item = self.itemAt(event.pos())
            if item is not None:
                qi = self._get_item(item)
                if qi is not None:
                    lines = []
                    if qi.thumbnail_url:
                        b64 = self._get_thumbnail_b64(qi.thumbnail_url)
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
                    if qi.job.subtitle_opts:
                        langs = ", ".join(
                            qi.job.subtitle_opts.get("subtitleslangs", [])
                        )
                        fmt = qi.job.subtitle_opts.get("subtitlesformat", "")
                        embed_lbl = (
                            t("orig_sub_embed")
                            if qi.job.subtitle_opts.get("embed")
                            else t("tooltip_sub_file")
                        )
                        sub_lbl = t("tooltip_subtitle")
                        lines.append(f"<b>{sub_lbl}:</b> {langs}  {fmt}  {embed_lbl}")
                    if qi.format_id == _ORIGINAL_KEY and qi.job.format_spec:
                        lines.append(
                            f"<b>{t('tooltip_format_spec')}:</b> {qi.job.format_spec}"
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
    def __init__(self):
        super().__init__()

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()
        i18n.set_language(self._settings.language)

        self.setWindowTitle(self._window_title())
        self.resize(_WIN_W, _WIN_H_DEFAULT)
        self.setMinimumSize(_WIN_MIN_W, 380)

        icon_path = os.path.join(get_resource_base(), "assets", "icon.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        if not self._settings.cookies_path and not self._settings.cookies_browser:
            default = os.path.join(get_resource_base(), "cookies.txt")
            if os.path.isfile(default):
                self._settings.cookies_path = default

        self._showing_pause_button = False
        self._log_entries: list[str] = []
        self._log_dialog: LogDialog | None = None

        self._signals = _AppSignals()
        self._signals.status_update.connect(self._update_status)
        self._signals.log_message.connect(self._log)
        self._signals.show_error.connect(
            lambda title, msg: QMessageBox.critical(self, title, msg)
        )

        self.downloader = Downloader(
            self._resolve_download_path(),
            status_callback=self._on_status_from_thread,
            video_resolution=self._settings.video_resolution,
            mp3_bitrate=self._settings.mp3_bitrate,
            log_callback=self._on_downloader_log,
            output_template_video=self._settings.output_template_video,
            output_template_playlist=self._settings.output_template_playlist,
            proxy_url=build_proxy_url(self._settings),
            concurrent_fragments=self._settings.concurrent_fragments,
            rate_limit=build_rate_limit(self._settings),
            sponsorblock_mode=self._settings.sponsorblock_mode,
            sponsorblock_categories=self._settings.sponsorblock_categories,
            download_archive_path=resolve_download_archive_path(self._settings),
        )

        self._thumbnail_cache = ThumbnailCache(self)

        self._create_menu()
        self._create_widgets()

        # Queue controller の生成は _queue_tree 構築後でないといけないため、
        # _create_widgets の後で行う。
        self.queue = QueueController(self.downloader, self._queue_tree, self)
        self._wire_queue_signals()

        QTimer.singleShot(0, self._check_dependencies)

    def _wire_queue_signals(self) -> None:
        """QueueController のシグナルを App スロットへ配線する。"""
        self.queue.item_refresh.connect(self.queue.refresh_tree_item)
        self.queue.status_update.connect(self._update_status)
        self.queue.log_message.connect(self._log)
        self.queue.show_error.connect(
            lambda title, msg: QMessageBox.critical(self, title, msg)
        )
        self.queue.show_warning.connect(
            lambda title, msg: QMessageBox.warning(self, title, msg)
        )
        self.queue.worker_done.connect(lambda: self._set_queue_running(False))
        self.queue.item_added.connect(self._on_queue_item_added)
        self.queue.edit_mode_entered.connect(self._on_edit_mode_entered)
        self.queue.edit_mode_exited.connect(self._on_edit_mode_exited)

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
        label_keys = {
            "ffmpeg": "warn_deps_missing_ffmpeg",
            "ffprobe": "warn_deps_missing_ffprobe",
            "deno": "warn_deps_missing_deno",
        }
        missing = [
            t(label_keys[name]) for name in self.downloader.missing_dependencies()
        ]
        if missing:
            QMessageBox.warning(
                self,
                t("warn_deps_missing_title"),
                t("warn_deps_missing_body").format(tools="\n".join(missing)),
            )

    def _refresh_format_labels(self):
        """`video_container` / `audio_format` / `mp3_bitrate` 等の設定や
        言語変更に追従して、フォーマットコンボとオリジナルパネルの表示文字列を
        再構築する。`_retranslate_ui` と `_open_settings` の共通処理。"""
        old_idx = self.format_combo.currentIndex()
        self._format_display = self._build_format_display()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(self._format_display)
        self.format_combo.setCurrentIndex(old_idx)
        self.format_combo.blockSignals(False)
        if self.queue.edit_mode and len(self.queue.editing_items) > 1:
            self._set_original_format_enabled(False)
        self._on_format_changed(old_idx)
        # オリジナル形式の詳細設定は別画面（開くたびに現在の言語・設定で生成）の
        # ため、ここでの永続パネル再翻訳は不要。

    def _window_title(self) -> str:
        """ウィンドウタイトル（アプリ名 + バージョン）を返す。"""
        return f"{t('app_title')} v{get_version()}"

    def _retranslate_ui(self):
        self.setWindowTitle(self._window_title())

        self._file_menu.setTitle(t("menu_file"))
        self._act_settings.setText(t("menu_settings"))
        self._act_log.setText(t("menu_log"))
        if self._act_quit is not None:
            self._act_quit.setText(t("menu_quit"))

        self._lbl_url.setText(t("label_url"))
        self._lbl_format.setText(t("label_format"))

        self._refresh_format_labels()
        self._mp3_thumb_check.setText(t("mp3_embed_thumbnail"))

        self._lbl_queue_title.setText(f"<b>{t('queue_title')}</b>")
        self._queue_tree.setHeaderLabels(
            ["#", t("queue_col_title"), t("queue_col_format"), t("queue_col_status")]
        )

        self.add_button.setText(
            t("btn_apply_edit") if self.queue.edit_mode else t("btn_add")
        )
        self._cancel_edit_button.setText(t("btn_cancel_edit"))
        self._detail_button.setText(t("btn_open_detail"))
        self.start_queue_button.setText(t("btn_start_queue"))
        self.pause_queue_button.setText(t("btn_pause_queue"))
        self.remove_item_button.setText(t("btn_remove_item"))

        self.queue.refresh_all_tree_items()

        if not self.queue.is_running:
            self.status_label.setText(
                t("status_edit_mode") if self.queue.edit_mode else t("status_ready")
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

    def _notify_container_promotion_if_needed(self, job: JobSpec) -> None:
        """build_job_spec で複数音声 → MKV 自動昇格が発生した場合に通知する。"""
        if job.is_multi_audio and job.video_container != self._settings.video_container:
            self._update_status(t("status_multi_audio_mkv_promoted"), 0)

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
        central_layout.setSpacing(8)

        # Top container: URL / Format / detail or add button
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

        # Row 2a: 「詳細設定...」ボタン（オリジナル形式選択時のみ表示）。
        # 詳細設定は別画面 (OriginalFormatDialog) に分離されている。
        detail_frame = QWidget()
        detail_layout = QHBoxLayout(detail_frame)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_button = QPushButton(t("btn_open_detail"))
        self._detail_button.clicked.connect(self._open_original_dialog)
        self._detail_button.setVisible(False)
        detail_layout.addWidget(self._detail_button)
        detail_layout.addStretch()
        layout.addWidget(detail_frame, 2, 0, 1, 3)

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

        # 上段は sizeHint 固定。詳細設定が別画面化したため上段は伸縮せず、
        # 旧 QSplitter（上段/キューの比率調整）は不要になった。
        central_layout.addWidget(top_widget)

        # Bottom: Queue (expands)
        queue_box = QFrame()
        queue_box.setFrameShape(QFrame.Shape.StyledPanel)
        qbl = QVBoxLayout(queue_box)
        qbl.setContentsMargins(6, 6, 6, 6)
        qbl.setSpacing(4)

        self._lbl_queue_title = QLabel(f"<b>{t('queue_title')}</b>")
        qbl.addWidget(self._lbl_queue_title)

        # self.queue は _create_widgets の後で生成されるため lambda 経由で遅延参照
        self._queue_tree = _QueueTree(
            get_item=lambda ti: self.queue.find_item_for(ti),
            get_thumbnail_b64=self._thumbnail_cache.get,
            is_editing=lambda: self.queue.edit_mode,
        )
        self._queue_tree.edit_format_requested.connect(self._enter_edit_mode)
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

        # キュー領域が余った縦スペースを埋める（上段は sizeHint 固定）。
        central_layout.addWidget(queue_box, 1)

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
        """形式選択に応じてボタン・補助ウィジェットの表示を切り替える。

        オリジナル形式の詳細設定は別画面 (OriginalFormatDialog) に分離された
        ため、ウィンドウ高さは変更しない（メイン高さは固定）。オリジナル形式時は
        メインの「追加」ボタンを隠し「詳細設定...」ボタンを出す（追加/変更は
        ダイアログ内で行うため）。"""
        if index < 0 or index >= len(FORMAT_KEYS):
            return
        format_id = FORMAT_KEYS[index]
        is_original = format_id == _ORIGINAL_KEY
        self._detail_button.setVisible(is_original)
        self.add_button.setVisible(not is_original)
        if format_id == _MP3_KEY:
            self._mp3_frame.setVisible(self._settings.audio_format == "mp3")
        else:
            self._mp3_frame.setVisible(False)

    # ── queue operations ──────────────────────────────────────────────────────

    def _add_url(self):
        if self.queue.edit_mode:
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

        # オリジナル形式の追加は「詳細設定...」ダイアログ側で行う
        # （その場合この「追加」ボタンは非表示）。
        if format_id == _ORIGINAL_KEY:
            self._open_original_dialog()
            return

        mp3_thumb = bool(self._mp3_thumb_check.isChecked())
        job = build_job_spec(format_id, self._settings, mp3_thumb_check=mp3_thumb)
        self._start_add_thread(url, cookies_path, cookies_browser, job, format_label)

    # ── original format dialog ─────────────────────────────────────────────────

    def _open_original_dialog(self) -> OriginalFormatDialog | None:
        """オリジナル形式の詳細設定ダイアログを開く。

        追加モードでは URL 必須。編集モードでは対象アイテムの `orig_settings` を
        渡して編集モードのダイアログを生成する。テスト容易性のため、生成した
        ダイアログ（開けない場合は None）を返す。"""
        edit_mode = self.queue.edit_mode
        if not edit_mode and not self.url_entry.text().strip():
            QMessageBox.warning(self, t("warn_title"), t("warn_no_url"))
            return None

        restore_settings = None
        if edit_mode:
            items = self.queue.editing_items
            if len(items) == 1 and items[0].format_id == _ORIGINAL_KEY:
                restore_settings = items[0].job.orig_settings

        dialog = self._make_original_dialog(
            "edit" if edit_mode else "add", restore_settings
        )
        dialog.exec()
        return dialog

    def _make_original_dialog(
        self, mode: str, restore_settings: dict | None
    ) -> OriginalFormatDialog:
        dialog = OriginalFormatDialog(
            self,
            downloader=self.downloader,
            get_url=lambda: self.url_entry.text().strip(),
            get_cookies=self._resolve_cookies,
            update_status=lambda text, pct: self._signals.status_update.emit(text, pct),
            video_container=self._settings.video_container,
            audio_label=self._build_audio_label(),
            mode=mode,
            restore_settings=restore_settings,
        )
        dialog.add_requested.connect(lambda: self._on_dialog_add_requested(dialog))
        dialog.edit_applied.connect(lambda: self._on_dialog_edit_applied(dialog))
        dialog.edit_cancelled.connect(self._cancel_edit)
        return dialog

    def _build_original_job(self, dialog: OriginalFormatDialog) -> tuple[JobSpec, str]:
        """ダイアログ内包パネルから `JobSpec` と表示用ラベルを組み立て、
        昇格/トランケートのステータス通知を発火する。検証はダイアログ側で
        実施済みの前提。"""
        panel = dialog.panel
        format_label = self.format_combo.currentText()
        audio_only = panel.get_audio_only()
        snapshot = panel.get_snapshot()
        job = build_job_spec(_ORIGINAL_KEY, self._settings, panel=snapshot)
        self._notify_container_promotion_if_needed(job)
        self._notify_audio_only_truncated_if_needed(
            snapshot.has_multiple_audio, audio_only
        )
        if audio_only:
            format_label = f"{format_label} → {self._build_audio_label()}"
        return job, format_label

    def _on_dialog_add_requested(self, dialog: OriginalFormatDialog) -> None:
        panel = dialog.panel
        url = self.url_entry.text().strip()
        cookies_path, cookies_browser = self._resolve_cookies()
        job, format_label = self._build_original_job(dialog)
        if panel.has_formats_loaded():
            self.queue.enqueue_single(url, panel.get_fetched_title(), format_label, job)
            self.url_entry.clear()
        else:
            self._start_add_thread(
                url, cookies_path, cookies_browser, job, format_label
            )

    def _on_dialog_edit_applied(self, dialog: OriginalFormatDialog) -> None:
        job, format_label = self._build_original_job(dialog)
        self.queue.apply_edit(format_label, job)

    def _start_add_thread(
        self,
        url: str,
        cookies_path: str | None,
        cookies_browser: str | None,
        job: JobSpec,
        format_label: str,
    ):
        self.add_button.setEnabled(False)
        self.add_button.setText(t("btn_adding"))
        self._update_status(t("status_fetching_title"), 0)

        def _work():
            result = self.downloader.fetch_title_or_entries(
                url, cookies_path, cookies_browser
            )
            return {"result": result, "job": job, "format_label": format_label}

        def _on_failed(exc: Exception) -> None:
            err_msg = strip_ansi(str(exc))
            self._update_status(f"❌ {err_msg}", 0)
            self._log(f"❌ {err_msg}")
            QMessageBox.critical(
                self, t("err_title"), t("err_fetch_title").format(error=err_msg)
            )

        run_in_thread(
            _work,
            on_done=self._on_fetch_for_add_done,
            on_failed=_on_failed,
            on_finished=self._reset_add_button,
            parent=self,
        )

    def _reset_add_button(self):
        self.add_button.setEnabled(True)
        self.add_button.setText(
            t("btn_apply_edit") if self.queue.edit_mode else t("btn_add")
        )

    def _on_fetch_for_add_done(self, payload: dict):
        result = payload["result"]
        job: JobSpec = payload["job"]
        format_label: str = payload["format_label"]
        format_id = job.format_id

        if result["type"] == "single":
            self.queue.enqueue_single(
                result["url"],
                result["title"],
                format_label,
                job,
                thumbnail_url=result.get("thumbnail_url"),
            )
            self.url_entry.clear()
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

            # ダウンロードアーカイブ有効時は既 DL 分を除外（差分取得）。
            total = len(entries)
            entries = self.downloader.filter_unarchived_entries(entries)
            skipped = total - len(entries)
            if skipped:
                self._log(t("log_playlist_archived_skipped").format(count=skipped))
            if not entries:
                self.url_entry.clear()
                QMessageBox.information(
                    self, t("info_title"), t("info_playlist_all_archived")
                )
                self._signals.status_update.emit(t("status_ready"), 0)
                return

            playlist_title = result.get("title", "")
            added = self.queue.enqueue_playlist(
                entries, playlist_title, format_label, job
            )

            self.url_entry.clear()
            msg = t("status_playlist_added").format(count=len(added))
            self._signals.status_update.emit(msg, 0)
            self._log(msg)

    def _on_queue_item_added(self, item: _QueueItem) -> None:
        """QueueController から追加通知を受け、サムネ取得を起動する。"""
        self._thumbnail_cache.request(item.thumbnail_url)

    # ── edit mode ─────────────────────────────────────────────────────────────

    def _enter_edit_mode(self, items: list[_QueueItem]):
        """`_QueueTree` のコンテキストメニューから呼ばれる。"""
        self.queue.enter_edit_mode(items)

    def _on_edit_mode_entered(self, items: list[_QueueItem]) -> None:
        """QueueController からの通知を受けて UI を編集モードに整える。"""
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
            self._mp3_thumb_check.setChecked(first.job.embed_thumbnail)

        # オリジナル形式の設定復元・フォーマット取得は「詳細設定...」で開く
        # ダイアログ側で行う（編集モードのダイアログが orig_settings を受け取り
        # restore_from_settings + trigger_fetch を実行する）。

        self.add_button.setText(t("btn_apply_edit"))
        self._cancel_edit_button.setVisible(True)

        if not self.queue.is_running:
            self.start_queue_button.setEnabled(False)

        self._update_status(t("status_edit_mode"), 0)

    def _apply_edit(self):
        idx = self.format_combo.currentIndex()
        if idx < 0 or idx >= len(FORMAT_KEYS):
            return
        format_id = FORMAT_KEYS[idx]
        format_label = self.format_combo.currentText()

        if len(self.queue.editing_items) > 1 and format_id == _ORIGINAL_KEY:
            QMessageBox.warning(self, t("warn_title"), t("warn_edit_original_multi"))
            return

        # オリジナル形式の変更適用は「詳細設定...」ダイアログ側で行う
        # （その場合この「変更」ボタンは非表示）。
        if format_id == _ORIGINAL_KEY:
            self._open_original_dialog()
            return

        mp3_thumb = bool(self._mp3_thumb_check.isChecked())
        job = build_job_spec(format_id, self._settings, mp3_thumb_check=mp3_thumb)
        self.queue.apply_edit(format_label, job)

    def _cancel_edit(self):
        self.queue.cancel_edit()

    def _on_edit_mode_exited(self) -> None:
        """QueueController からの通知を受けて UI を通常モードに戻す。"""
        self.url_entry.clear()
        self.url_entry.setReadOnly(False)

        self.add_button.setText(t("btn_add"))
        self._cancel_edit_button.setVisible(False)

        self._set_original_format_enabled(True)

        if not self.queue.is_running:
            self.start_queue_button.setEnabled(True)

        self._on_format_changed(self.format_combo.currentIndex())
        self._update_status(t("status_ready"), 0)

    # ── queue control ─────────────────────────────────────────────────────────

    def _start_queue(self):
        if not self.queue.has_waiting():
            QMessageBox.warning(self, t("warn_title"), t("warn_queue_empty"))
            return
        if self.queue.is_running:
            return
        if self.queue.start(self._resolve_cookies):
            self._set_queue_running(True)

    def _pause_queue(self):
        self.queue.pause()
        self._set_queue_running(False)

    def _set_queue_running(self, running: bool):
        if running == self._showing_pause_button:
            return
        self.start_queue_button.setVisible(not running)
        self.pause_queue_button.setVisible(running)
        self._showing_pause_button = running

    def _remove_selected(self):
        self.queue.remove_selected()

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
        self.downloader.proxy_url = build_proxy_url(self._settings)
        self.downloader.concurrent_fragments = self._settings.concurrent_fragments
        self.downloader.rate_limit = build_rate_limit(self._settings)
        self.downloader.sponsorblock_mode = self._settings.sponsorblock_mode
        self.downloader.sponsorblock_categories = self._settings.sponsorblock_categories
        self.downloader.download_archive_path = resolve_download_archive_path(
            self._settings
        )

        if self._settings.language != old_lang:
            i18n.set_language(self._settings.language)
            self._retranslate_ui()
        else:
            self._refresh_format_labels()

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
