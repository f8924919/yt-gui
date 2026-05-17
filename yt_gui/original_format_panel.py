import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QWidget,
)

from .downloader import Downloader
from .i18n import t
from .utils import strip_ansi

_SUBTITLE_FORMATS = ("srt", "vtt", "best")


class _PanelSignals(QObject):
    formats_fetched = Signal(dict)
    fetch_failed = Signal(str, bool)  # (error_msg, is_playlist)
    fetch_finished = Signal()  # always emitted at end (re-enable button)


class OriginalFormatPanel(QGroupBox):
    def __init__(
        self,
        parent=None,
        *,
        downloader: Downloader,
        get_url: Callable[[], str],
        get_cookies: Callable[[], tuple[str | None, str | None]],
        update_status: Callable[[str, float], None],
    ):
        super().__init__(t("label_original_detail"), parent)
        self._downloader = downloader
        self._get_url = get_url
        self._get_cookies = get_cookies
        self._update_status = update_status

        self._video_formats: list[tuple[str, str, bool]] = []
        self._audio_formats: list[tuple[str, str]] = []
        self._subtitle_formats: list[tuple[str, str, bool]] = []
        self._fetched_title: str = ""

        self._signals = _PanelSignals()
        self._signals.formats_fetched.connect(self._on_fetch_done)
        self._signals.fetch_failed.connect(self._on_fetch_failed)
        self._signals.fetch_finished.connect(self._on_fetch_finished)

        self._build_widgets()
        self._pending_restore: dict | None = None

    def _build_widgets(self):
        layout = QGridLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)
        layout.setColumnStretch(1, 1)

        # Row 0: Video combo + fetch button
        self._video_label = QLabel(t("label_orig_video"))
        layout.addWidget(self._video_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        self._video_combo = QComboBox()
        self._video_combo.addItem(t("orig_auto"))
        self._video_combo.setEnabled(False)
        self._video_combo.currentTextChanged.connect(self._on_video_changed)
        layout.addWidget(self._video_combo, 0, 1, 1, 2)

        self._fetch_button = QPushButton(t("btn_fetch_formats"))
        self._fetch_button.clicked.connect(self._start_fetch_thread)
        layout.addWidget(self._fetch_button, 0, 3)

        # Row 1: Audio combo
        self._audio_label = QLabel(t("label_orig_audio"))
        layout.addWidget(self._audio_label, 1, 0, Qt.AlignmentFlag.AlignRight)
        self._audio_combo = QComboBox()
        self._audio_combo.addItem(t("orig_auto"))
        self._audio_combo.setEnabled(False)
        layout.addWidget(self._audio_combo, 1, 1, 1, 2)

        # Row 2: Subtitle listbox + format/embed controls
        self._subtitle_label = QLabel(t("label_orig_subtitle"))
        layout.addWidget(
            self._subtitle_label,
            2,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        self._subtitle_list = QListWidget()
        self._subtitle_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._subtitle_list.setEnabled(False)
        self._subtitle_list.setMinimumHeight(96)
        self._subtitle_list.itemSelectionChanged.connect(self._on_subtitle_changed)
        layout.addWidget(self._subtitle_list, 2, 1, 1, 2)

        sub_right = QWidget()
        sub_right_layout = QHBoxLayout(sub_right)
        sub_right_layout.setContentsMargins(0, 0, 0, 0)
        sub_right_layout.setSpacing(4)
        self._subtitle_fmt_combo = QComboBox()
        self._subtitle_fmt_combo.addItems(_SUBTITLE_FORMATS)
        self._subtitle_fmt_combo.setEnabled(False)
        self._subtitle_fmt_combo.setMaximumWidth(70)
        sub_right_layout.addWidget(self._subtitle_fmt_combo)
        self._embed_check = QCheckBox(t("orig_sub_embed"))
        self._embed_check.setEnabled(False)
        sub_right_layout.addWidget(self._embed_check)
        layout.addWidget(sub_right, 2, 3, Qt.AlignmentFlag.AlignTop)

        # Row 3: Output format radio buttons
        self._output_label = QLabel(t("label_orig_output"))
        layout.addWidget(self._output_label, 3, 0, Qt.AlignmentFlag.AlignRight)
        out_widget = QWidget()
        out_layout = QHBoxLayout(out_widget)
        out_layout.setContentsMargins(0, 0, 0, 0)
        self._remux_group = QButtonGroup(self)
        self._radio_mp4 = QRadioButton(t("orig_output_mp4").format(container="MP4"))
        self._radio_remux = QRadioButton(t("orig_output_remux"))
        self._radio_mp4.setChecked(True)
        self._remux_group.addButton(self._radio_mp4, 0)
        self._remux_group.addButton(self._radio_remux, 1)
        self._radio_mp4.toggled.connect(self._on_output_format_changed)
        out_layout.addWidget(self._radio_mp4)
        out_layout.addWidget(self._radio_remux)
        out_layout.addStretch()
        layout.addWidget(out_widget, 3, 1, 1, 3)

        # Row 4: Embed thumbnail checkbox
        self._embed_thumbnail_check = QCheckBox(t("orig_embed_thumbnail"))
        layout.addWidget(self._embed_thumbnail_check, 4, 1, 1, 3)

        # Row 5: Embed metadata checkbox
        self._embed_metadata_check = QCheckBox(t("orig_embed_metadata"))
        self._embed_metadata_check.setChecked(True)
        layout.addWidget(self._embed_metadata_check, 5, 1, 1, 3)

        # Row 6: Embed chapters checkbox
        self._embed_chapters_check = QCheckBox(t("orig_embed_chapters"))
        self._embed_chapters_check.setChecked(True)
        layout.addWidget(self._embed_chapters_check, 6, 1, 1, 3)

    # ── public interface ─────────────────────────────────────────────────────

    def trigger_fetch(self):
        self._start_fetch_thread()

    def retranslate(self, video_container: str = "mp4"):
        self.setTitle(t("label_original_detail"))
        self._video_label.setText(t("label_orig_video"))
        self._audio_label.setText(t("label_orig_audio"))
        self._subtitle_label.setText(t("label_orig_subtitle"))
        self._output_label.setText(t("label_orig_output"))

        for combo in (self._video_combo, self._audio_combo):
            combo.setItemText(0, t("orig_auto"))
            if combo.count() >= 2:
                combo.setItemText(1, t("orig_skip"))

        if self._subtitle_list.count() == 1 and not self._subtitle_formats:
            self._subtitle_list.item(0).setText(t("orig_sub_unavailable"))

        if self._fetch_button.isEnabled():
            self._fetch_button.setText(t("btn_fetch_formats"))

        self._embed_check.setText(t("orig_sub_embed"))
        self._radio_mp4.setText(
            t("orig_output_mp4").format(container=video_container.upper())
        )
        self._radio_remux.setText(t("orig_output_remux"))
        self._embed_thumbnail_check.setText(t("orig_embed_thumbnail"))
        self._embed_metadata_check.setText(t("orig_embed_metadata"))
        self._embed_chapters_check.setText(t("orig_embed_chapters"))

    def has_formats_loaded(self) -> bool:
        return self._video_combo.isEnabled() and bool(self._fetched_title)

    def get_fetched_title(self) -> str:
        return self._fetched_title

    def is_both_skipped(self) -> bool:
        skip = t("orig_skip")
        return bool(
            self._video_combo.currentText() == skip
            and self._audio_combo.currentText() == skip
        )

    def get_remux_only(self) -> bool:
        return bool(self._radio_remux.isChecked())

    def get_embed_thumbnail(self) -> bool:
        return bool(self._embed_thumbnail_check.isChecked())

    def get_embed_metadata(self) -> bool:
        return bool(self._embed_metadata_check.isChecked())

    def get_embed_chapters(self) -> bool:
        return bool(self._embed_chapters_check.isChecked())

    def get_raw_settings(self) -> dict:
        """現在の選択状態を復元可能な形式で返す。"""
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")
        video_sel = self._video_combo.currentText()
        audio_sel = self._audio_combo.currentText()

        video_skip = video_sel == skip_label
        audio_skip = audio_sel == skip_label
        video_id: str | None = None
        is_combined = False
        audio_id: str | None = None

        if video_sel not in (auto_label, skip_label) and self._video_formats:
            idx = self._format_index(self._video_combo, video_sel)
            if idx is not None and 0 <= idx < len(self._video_formats):
                _, video_id, is_combined = self._video_formats[idx]

        if not is_combined and audio_sel not in (
            auto_label,
            skip_label,
            t("orig_audio_included"),
        ):
            if self._audio_formats:
                idx = self._format_index(self._audio_combo, audio_sel)
                if idx is not None and 0 <= idx < len(self._audio_formats):
                    _, audio_id = self._audio_formats[idx]

        return {
            "video_id": video_id,
            "is_combined": is_combined,
            "video_skip": video_skip,
            "audio_id": audio_id,
            "audio_skip": audio_skip,
            "subtitle_opts": self.get_subtitle_opts(),
            "remux_only": self.get_remux_only(),
            "embed_thumbnail": self.get_embed_thumbnail(),
            "embed_metadata": self.get_embed_metadata(),
            "embed_chapters": self.get_embed_chapters(),
        }

    def restore_from_settings(self, settings: dict):
        """チェックボックス・ラジオボタンを即時復元し、映像/音声/字幕はフォーマット取得後に復元する。"""
        remux_only = settings.get("remux_only", False)
        if remux_only:
            self._radio_remux.setChecked(True)
        else:
            self._radio_mp4.setChecked(True)
            self._embed_thumbnail_check.setChecked(
                settings.get("embed_thumbnail", False)
            )
        self._embed_metadata_check.setChecked(settings.get("embed_metadata", True))
        self._embed_chapters_check.setChecked(settings.get("embed_chapters", True))

        self._pending_restore = settings
        if self.has_formats_loaded():
            self._apply_pending_restore()
            self._pending_restore = None

    def get_format_spec(self) -> str:
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")
        video_sel = self._video_combo.currentText()
        audio_sel = self._audio_combo.currentText()

        video_skip = video_sel == skip_label
        audio_skip = audio_sel == skip_label

        video_id = None
        is_combined = False
        audio_id = None

        if video_sel not in (auto_label, skip_label) and self._video_formats:
            idx = self._format_index(self._video_combo, video_sel)
            if idx is not None and 0 <= idx < len(self._video_formats):
                _, video_id, is_combined = self._video_formats[idx]

        if not is_combined and audio_sel not in (
            auto_label,
            skip_label,
            t("orig_audio_included"),
        ):
            if self._audio_formats:
                idx = self._format_index(self._audio_combo, audio_sel)
                if idx is not None and 0 <= idx < len(self._audio_formats):
                    _, audio_id = self._audio_formats[idx]

        if is_combined:
            return video_id or "bestvideo/best"
        if video_skip:
            return audio_id if audio_id else "bestaudio/best"
        if audio_skip:
            return video_id if video_id else "bestvideo/best"
        if video_id and audio_id:
            return f"{video_id}+{audio_id}"
        if video_id:
            return f"{video_id}+bestaudio"
        if audio_id:
            return f"bestvideo+{audio_id}"
        return "bestvideo+bestaudio/best"

    def get_subtitle_opts(self) -> dict | None:
        sel_items = self._subtitle_list.selectedItems()
        if not sel_items or not self._subtitle_formats:
            return None

        lang_codes: list[str] = []
        has_manual = False
        has_auto = False
        for item in sel_items:
            idx = self._subtitle_list.row(item)
            if 0 <= idx < len(self._subtitle_formats):
                _, lang_code, is_auto = self._subtitle_formats[idx]
                lang_codes.append(lang_code)
                if is_auto:
                    has_auto = True
                else:
                    has_manual = True

        if not lang_codes:
            return None

        return {
            "writesubtitles": has_manual,
            "writeautomaticsub": has_auto,
            "subtitleslangs": lang_codes,
            "subtitlesformat": self._subtitle_fmt_combo.currentText(),
            "embed": self._embed_check.isChecked(),
        }

    # ── restore helpers ──────────────────────────────────────────────────────

    def _apply_pending_restore(self):
        settings = self._pending_restore
        if settings is None:
            return

        skip_label = t("orig_skip")
        auto_label = t("orig_auto")
        video_id = settings.get("video_id")
        audio_id = settings.get("audio_id")
        is_combined = settings.get("is_combined", False)
        video_skip = settings.get("video_skip", False)
        audio_skip = settings.get("audio_skip", False)
        subtitle_opts = settings.get("subtitle_opts")

        # 映像コンボ復元（シグナルをブロックして手動で _on_video_changed を呼ぶ）
        self._video_combo.blockSignals(True)
        if video_skip:
            self._video_combo.setCurrentText(skip_label)
        elif video_id:
            matched = False
            for i, (_, fid, _) in enumerate(self._video_formats):
                if fid == video_id:
                    self._video_combo.setCurrentIndex(i + 2)  # auto/skip の分オフセット
                    matched = True
                    break
            if not matched:
                self._video_combo.setCurrentText(auto_label)
        else:
            self._video_combo.setCurrentText(auto_label)
        self._video_combo.blockSignals(False)
        self._on_video_changed(self._video_combo.currentText())

        # 音声コンボ復元（複合フォーマット選択時はスキップ）
        if not is_combined:
            if audio_skip:
                self._audio_combo.setCurrentText(skip_label)
            elif audio_id:
                matched = False
                for i, (_, fid) in enumerate(self._audio_formats):
                    if fid == audio_id:
                        self._audio_combo.setCurrentIndex(i + 2)
                        matched = True
                        break
                if not matched:
                    self._audio_combo.setCurrentText(auto_label)
            else:
                self._audio_combo.setCurrentText(auto_label)

        # 字幕復元
        if subtitle_opts and self._subtitle_formats:
            langs = set(subtitle_opts.get("subtitleslangs", []))
            fmt = subtitle_opts.get("subtitlesformat", "best")
            embed = subtitle_opts.get("embed", False)

            self._subtitle_list.blockSignals(True)
            self._subtitle_list.clearSelection()
            for i, (_, lcode, _) in enumerate(self._subtitle_formats):
                if lcode in langs:
                    item = self._subtitle_list.item(i)
                    if item:
                        item.setSelected(True)
            self._subtitle_list.blockSignals(False)
            self._on_subtitle_changed()  # 有効状態を一括更新

            fmt_idx = self._subtitle_fmt_combo.findText(fmt)
            if fmt_idx >= 0:
                self._subtitle_fmt_combo.setCurrentIndex(fmt_idx)
            self._embed_check.setChecked(embed)

    # ── internal events ──────────────────────────────────────────────────────

    def _on_video_changed(self, selected: str):
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")

        if selected in (auto_label, skip_label) or not self._video_formats:
            if self._audio_combo.currentText() == t("orig_audio_included"):
                self._audio_combo.setCurrentText(auto_label)
            if self._audio_formats:
                self._audio_combo.setEnabled(True)
            return

        idx = self._format_index(self._video_combo, selected)
        if idx is None:
            return

        if 0 <= idx < len(self._video_formats):
            _, _, is_combined = self._video_formats[idx]
            if is_combined:
                self._audio_combo.setCurrentText(t("orig_audio_included"))
                self._audio_combo.setEnabled(False)
            else:
                if self._audio_combo.currentText() == t("orig_audio_included"):
                    self._audio_combo.setCurrentText(auto_label)
                self._audio_combo.setEnabled(True)

    def _on_output_format_changed(self, mp4_checked: bool):
        if not mp4_checked:
            self._embed_thumbnail_check.setChecked(False)
        self._embed_thumbnail_check.setEnabled(mp4_checked)

    def _on_subtitle_changed(self):
        has_sub = bool(self._subtitle_list.selectedItems()) and bool(
            self._subtitle_formats
        )
        self._subtitle_fmt_combo.setEnabled(has_sub)
        self._embed_check.setEnabled(has_sub)
        if not has_sub:
            self._embed_check.setChecked(False)

    @staticmethod
    def _format_index(combo: QComboBox, selected: str) -> int | None:
        idx = combo.findText(selected)
        if idx < 0:
            return None
        return idx - 2  # offset past [auto, skip]

    # ── format fetching ──────────────────────────────────────────────────────

    def _start_fetch_thread(self):
        url = self._get_url()
        if not url:
            QMessageBox.warning(self, t("warn_title"), t("warn_no_url"))
            return

        cookies_path, cookies_browser = self._get_cookies()

        self._fetch_button.setEnabled(False)
        self._fetch_button.setText(t("btn_fetching"))
        self._video_combo.setEnabled(False)
        self._audio_combo.setEnabled(False)
        self._subtitle_list.setEnabled(False)
        self._subtitle_fmt_combo.setEnabled(False)
        self._embed_check.setEnabled(False)
        self._update_status(t("status_fetching_formats"), 0)

        threading.Thread(
            target=self._run_fetch,
            args=(url, cookies_path, cookies_browser),
            daemon=True,
        ).start()

    def _run_fetch(self, url, cookies_path, cookies_browser):
        try:
            result = self._downloader.fetch_formats(url, cookies_path, cookies_browser)
            self._signals.formats_fetched.emit(result)
        except Exception as e:
            err_str = strip_ansi(str(e))
            is_playlist = "playlist" in err_str.lower()
            self._signals.fetch_failed.emit(err_str, is_playlist)
        finally:
            self._signals.fetch_finished.emit()

    def _on_fetch_done(self, result: dict):
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")

        self._fetched_title = result.get("title", "")
        self._video_formats = result["video"]
        self._audio_formats = result["audio"]
        self._subtitle_formats = result["subtitles"]

        video_labels = [auto_label, skip_label] + [
            lbl for lbl, _, _ in self._video_formats
        ]
        audio_labels = [auto_label, skip_label] + [
            lbl for lbl, _ in self._audio_formats
        ]

        self._video_combo.blockSignals(True)
        self._video_combo.clear()
        self._video_combo.addItems(video_labels)
        self._video_combo.setCurrentText(auto_label)
        self._video_combo.setEnabled(True)
        self._video_combo.blockSignals(False)

        self._audio_combo.clear()
        self._audio_combo.addItems(audio_labels)
        self._audio_combo.setCurrentText(auto_label)
        self._audio_combo.setEnabled(True)

        self._subtitle_list.clear()
        self._subtitle_list.setEnabled(True)
        if self._subtitle_formats:
            for lbl, _, _ in self._subtitle_formats:
                self._subtitle_list.addItem(lbl)
        else:
            self._subtitle_list.addItem(t("orig_sub_unavailable"))
            self._subtitle_list.setEnabled(False)
        self._subtitle_fmt_combo.setEnabled(False)
        self._embed_check.setEnabled(False)

        if not self._video_formats and not self._audio_formats:
            self._pending_restore = None
            self._update_status(t("status_fetch_formats_no_formats"), 0)
            QMessageBox.warning(
                self, t("warn_title"), t("warn_fetch_formats_no_formats")
            )
            return

        self._update_status(
            t("status_formats_loaded").format(
                video=len(self._video_formats),
                audio=len(self._audio_formats),
                subtitle=len(self._subtitle_formats),
            ),
            0,
        )

        if self._pending_restore is not None:
            self._apply_pending_restore()
            self._pending_restore = None

    def _on_fetch_failed(self, err_str: str, is_playlist: bool):
        if is_playlist:
            self._update_status(
                f"⚠️ {t('warn_fetch_formats_playlist').splitlines()[0]}", 0
            )
            QMessageBox.warning(self, t("warn_title"), t("warn_fetch_formats_playlist"))
        else:
            self._update_status(f"❌ {err_str}", 0)
            QMessageBox.critical(
                self, t("err_title"), t("err_fetch_formats").format(error=err_str)
            )

    def _on_fetch_finished(self):
        self._fetch_button.setEnabled(True)
        self._fetch_button.setText(t("btn_fetch_formats"))
