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


class _ToggleListWidget(QListWidget):
    """修飾キーなしの左クリックで選択済み項目を再クリックすると選択解除する。"""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not (
            event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        ):
            item = self.itemAt(event.position().toPoint())
            if item is not None and item.isSelected():
                item.setSelected(False)
                return
        super().mousePressEvent(event)


class _AudioListWidget(_ToggleListWidget):
    """音声トラックの multi-select リスト。

    レイアウト: [自動, ダウンロードしない, <音声ID 群>, (映像に含まれます)]
    - 「自動」を選ぶと他の全行が解除される
    - 「ダウンロードしない」を選ぶと他の全行が解除される
    - 音声 ID を選ぶと「自動」「ダウンロードしない」が解除される
    - 「映像に含まれます」(複合フォーマット時の固定行) は単独表示用で、選択操作は無効
    """

    AUTO_ROW = 0
    SKIP_ROW = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        # `_AudioListWidget` は内部状態として「現在の動作モード」を持つ:
        #   normal:   通常時。AUTO_ROW / SKIP_ROW / 音声 ID 行が並ぶ
        #   included: 複合フォーマット選択中。1 行だけ「映像に含まれます」表示
        self._mode: str = "normal"
        self.itemSelectionChanged.connect(self._enforce_exclusivity)
        self._suppress_enforce = False

    def set_included_mode(self, label: str):
        """複合フォーマット選択中の状態に切り替える。

        リスト全体を 1 行表示で無効化する。"""
        self._mode = "included"
        self._suppress_enforce = True
        self.clear()
        self.addItem(label)
        self.setEnabled(False)
        self._suppress_enforce = False

    def set_normal_mode(
        self, auto_label: str, skip_label: str, audio_labels: list[str]
    ):
        """通常モードに切り替える。フォーマット取得後やリセット時に呼ぶ。"""
        self._mode = "normal"
        self._suppress_enforce = True
        self.clear()
        self.addItem(auto_label)
        self.addItem(skip_label)
        for lbl in audio_labels:
            self.addItem(lbl)
        self._suppress_enforce = False

    def is_included_mode(self) -> bool:
        return self._mode == "included"

    def select_auto(self):
        """「自動」を単独選択。"""
        if self._mode != "normal" or self.count() <= self.AUTO_ROW:
            return
        self._suppress_enforce = True
        self.clearSelection()
        item = self.item(self.AUTO_ROW)
        if item is not None:
            item.setSelected(True)
        self._suppress_enforce = False

    def select_skip(self):
        if self._mode != "normal" or self.count() <= self.SKIP_ROW:
            return
        self._suppress_enforce = True
        self.clearSelection()
        item = self.item(self.SKIP_ROW)
        if item is not None:
            item.setSelected(True)
        self._suppress_enforce = False

    def select_audio_rows(self, rows: list[int]):
        """指定インデックスの音声行を選択。AUTO/SKIP は解除される。"""
        if self._mode != "normal":
            return
        self._suppress_enforce = True
        self.clearSelection()
        for r in rows:
            item = self.item(r)
            if item is not None:
                item.setSelected(True)
        self._suppress_enforce = False

    def get_selection(self) -> tuple[bool, bool, list[int]]:
        """(auto選択中, skip選択中, 選択された音声行インデックスのリスト) を返す。

        included モードでは (False, False, []) を返す。
        音声行インデックスは自身のインデックス
        （AUTO_ROW/SKIP_ROW を含まない範囲）を返す。
        """
        if self._mode != "normal":
            return False, False, []
        auto = False
        skip = False
        audio_rows: list[int] = []
        for i in range(self.count()):
            item = self.item(i)
            if item is None or not item.isSelected():
                continue
            if i == self.AUTO_ROW:
                auto = True
            elif i == self.SKIP_ROW:
                skip = True
            else:
                audio_rows.append(i)
        return auto, skip, audio_rows

    def _enforce_exclusivity(self):
        if self._suppress_enforce or self._mode != "normal":
            return
        sel = self.selectedItems()
        if not sel:
            return
        auto_item = self.item(self.AUTO_ROW)
        skip_item = self.item(self.SKIP_ROW)

        auto_selected = auto_item is not None and auto_item.isSelected()
        skip_selected = skip_item is not None and skip_item.isSelected()
        audio_rows = [
            i
            for i in range(self.count())
            if i not in (self.AUTO_ROW, self.SKIP_ROW)
            and (it := self.item(i)) is not None
            and it.isSelected()
        ]

        self._suppress_enforce = True
        try:
            if auto_selected and (skip_selected or audio_rows):
                # 「自動」が他と同時選択されたら自動を解除
                if len(sel) > 1:
                    if auto_item is not None:
                        auto_item.setSelected(False)
            if skip_selected and audio_rows:
                if skip_item is not None:
                    skip_item.setSelected(False)
            if skip_selected and auto_selected:
                # 上で auto を解除済みの可能性があるが念のため
                if auto_item is not None:
                    auto_item.setSelected(False)
        finally:
            self._suppress_enforce = False


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
        self._audio_label: str = "MP3"

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

        # Row 1: Audio multi-select list
        self._audio_label_widget = QLabel(t("label_orig_audio"))
        layout.addWidget(
            self._audio_label_widget,
            1,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        self._audio_list = _AudioListWidget()
        self._audio_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._audio_list.setMinimumHeight(96)
        self._audio_list.set_normal_mode(t("orig_auto"), t("orig_skip"), [])
        self._audio_list.item(0).setSelected(True)
        self._audio_list.setEnabled(False)
        layout.addWidget(self._audio_list, 1, 1, 1, 2)

        # Row 2: Subtitle listbox + format/embed controls
        self._subtitle_label = QLabel(t("label_orig_subtitle"))
        layout.addWidget(
            self._subtitle_label,
            2,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        self._subtitle_list = _ToggleListWidget()
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
        self._radio_audio = QRadioButton(
            t("orig_output_audio_only").format(label=self._audio_label)
        )
        self._radio_mp4.setChecked(True)
        self._remux_group.addButton(self._radio_mp4, 0)
        self._remux_group.addButton(self._radio_remux, 1)
        self._remux_group.addButton(self._radio_audio, 2)
        self._remux_group.buttonToggled.connect(self._on_output_format_changed)
        out_layout.addWidget(self._radio_mp4)
        out_layout.addWidget(self._radio_remux)
        out_layout.addWidget(self._radio_audio)
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

    def reset(self):
        """フォーマット取得結果と選択状態を初期状態へ戻す。"""
        self._video_formats = []
        self._audio_formats = []
        self._subtitle_formats = []
        self._fetched_title = ""
        self._pending_restore = None

        auto_label = t("orig_auto")

        self._video_combo.blockSignals(True)
        self._video_combo.clear()
        self._video_combo.addItem(auto_label)
        self._video_combo.setEnabled(False)
        self._video_combo.blockSignals(False)

        self._audio_list.blockSignals(True)
        self._audio_list.set_normal_mode(auto_label, t("orig_skip"), [])
        self._audio_list.item(0).setSelected(True)
        self._audio_list.setEnabled(False)
        self._audio_list.blockSignals(False)

        self._subtitle_list.blockSignals(True)
        self._subtitle_list.clear()
        self._subtitle_list.setEnabled(False)
        self._subtitle_list.blockSignals(False)

        self._subtitle_fmt_combo.setEnabled(False)
        self._embed_check.setEnabled(False)
        self._embed_check.setChecked(False)

        self._radio_mp4.setChecked(True)
        self._embed_thumbnail_check.setChecked(False)
        self._embed_metadata_check.setChecked(True)
        self._embed_chapters_check.setChecked(True)

    def retranslate(self, video_container: str = "mp4", audio_label: str | None = None):
        if audio_label is not None:
            self._audio_label = audio_label
        self.setTitle(t("label_original_detail"))
        self._video_label.setText(t("label_orig_video"))
        self._audio_label_widget.setText(t("label_orig_audio"))
        self._subtitle_label.setText(t("label_orig_subtitle"))
        self._output_label.setText(t("label_orig_output"))

        self._video_combo.setItemText(0, t("orig_auto"))
        if self._video_combo.count() >= 2:
            self._video_combo.setItemText(1, t("orig_skip"))

        # 音声リストのラベル更新
        if self._audio_list.is_included_mode():
            included_item = self._audio_list.item(0)
            if included_item is not None:
                included_item.setText(t("orig_audio_included"))
        else:
            auto_item = self._audio_list.item(_AudioListWidget.AUTO_ROW)
            skip_item = self._audio_list.item(_AudioListWidget.SKIP_ROW)
            if auto_item is not None:
                auto_item.setText(t("orig_auto"))
            if skip_item is not None:
                skip_item.setText(t("orig_skip"))

        if self._subtitle_list.count() == 1 and not self._subtitle_formats:
            self._subtitle_list.item(0).setText(t("orig_sub_unavailable"))

        if self._fetch_button.isEnabled():
            self._fetch_button.setText(t("btn_fetch_formats"))

        self._embed_check.setText(t("orig_sub_embed"))
        self._radio_mp4.setText(
            t("orig_output_mp4").format(container=video_container.upper())
        )
        self._radio_remux.setText(t("orig_output_remux"))
        self._radio_audio.setText(
            t("orig_output_audio_only").format(label=self._audio_label)
        )
        self._embed_thumbnail_check.setText(t("orig_embed_thumbnail"))
        self._embed_metadata_check.setText(t("orig_embed_metadata"))
        self._embed_chapters_check.setText(t("orig_embed_chapters"))

    def has_formats_loaded(self) -> bool:
        return bool(self._fetched_title) and (
            bool(self._video_formats) or bool(self._audio_formats)
        )

    def get_fetched_title(self) -> str:
        return self._fetched_title

    def is_both_skipped(self) -> bool:
        skip = t("orig_skip")
        return bool(self._video_combo.currentText() == skip and self.is_audio_skipped())

    def is_audio_skipped(self) -> bool:
        _, skip, _ = self._audio_list.get_selection()
        return bool(skip)

    def has_multiple_audio_selected(self) -> bool:
        """音声 ID が 2 件以上選択されているか（MKV 自動昇格判定用）。"""
        if self._audio_list.is_included_mode():
            return False
        _, _, rows = self._audio_list.get_selection()
        return len(rows) >= 2

    def get_remux_only(self) -> bool:
        return bool(self._radio_remux.isChecked())

    def get_audio_only(self) -> bool:
        return bool(self._radio_audio.isChecked())

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

        video_skip = video_sel == skip_label
        video_id: str | None = None
        is_combined = False

        if video_sel not in (auto_label, skip_label) and self._video_formats:
            idx = self._format_index(self._video_combo, video_sel)
            if idx is not None and 0 <= idx < len(self._video_formats):
                _, video_id, is_combined = self._video_formats[idx]

        audio_skip = False
        audio_ids: list[str] = []
        if not is_combined:
            audio_skip = self.is_audio_skipped()
            audio_ids = self._collect_selected_audio_ids()

        return {
            "video_id": video_id,
            "is_combined": is_combined,
            "video_skip": video_skip,
            "audio_ids": audio_ids,
            "audio_skip": audio_skip,
            "subtitle_opts": self.get_subtitle_opts(),
            "remux_only": self.get_remux_only(),
            "audio_only": self.get_audio_only(),
            "embed_thumbnail": self.get_embed_thumbnail(),
            "embed_metadata": self.get_embed_metadata(),
            "embed_chapters": self.get_embed_chapters(),
        }

    def _collect_selected_audio_ids(self) -> list[str]:
        """音声リストの選択行から音声 ID のみを抽出（auto/skip/included は除外）。"""
        if not self._audio_formats or self._audio_list.is_included_mode():
            return []
        _, _, rows = self._audio_list.get_selection()
        out: list[str] = []
        for row in rows:
            audio_idx = row - 2  # AUTO/SKIP の分オフセット
            if 0 <= audio_idx < len(self._audio_formats):
                _, fid = self._audio_formats[audio_idx]
                out.append(fid)
        return out

    def restore_from_settings(self, settings: dict):
        """チェックボックス・ラジオボタンを即時復元し、映像/音声/字幕はフォーマット取得後に復元する。"""
        audio_only = settings.get("audio_only", False)
        remux_only = settings.get("remux_only", False)
        if audio_only:
            self._radio_audio.setChecked(True)
            self._embed_thumbnail_check.setChecked(
                settings.get("embed_thumbnail", False)
            )
        elif remux_only:
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

        audio_ids = self._collect_selected_audio_ids()
        audio_skip = self.is_audio_skipped()

        if self.get_audio_only():
            # 音声のみモードでは先頭の 1 件のみ使用（仕様: フェーズ 1）
            if audio_ids:
                return audio_ids[0]
            return "bestaudio/best"

        video_sel = self._video_combo.currentText()
        video_skip = video_sel == skip_label

        video_id = None
        is_combined = False
        if video_sel not in (auto_label, skip_label) and self._video_formats:
            idx = self._format_index(self._video_combo, video_sel)
            if idx is not None and 0 <= idx < len(self._video_formats):
                _, video_id, is_combined = self._video_formats[idx]

        if is_combined:
            return video_id or "bestvideo/best"
        if video_skip:
            if audio_ids:
                return "+".join(audio_ids)
            return "bestaudio/best"
        if audio_skip:
            return video_id if video_id else "bestvideo/best"

        video_part = video_id if video_id else "bestvideo"
        if audio_ids:
            audio_part = "+".join(audio_ids)
            return f"{video_part}+{audio_part}"
        # 音声未選択（または「自動」のみ）
        if video_id:
            return f"{video_id}+bestaudio"
        return "bestvideo+bestaudio/best"

    def get_subtitle_opts(self) -> dict | None:
        if self.get_audio_only():
            return None
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
        # 後方互換: 旧キー audio_id (str | None) と新キー audio_ids (list[str])
        audio_ids = settings.get("audio_ids")
        if audio_ids is None:
            legacy = settings.get("audio_id")
            audio_ids = [legacy] if legacy else []
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

        # 音声リスト復元（複合フォーマット選択時はスキップ）
        if not is_combined and not self._audio_list.is_included_mode():
            if audio_skip:
                self._audio_list.select_skip()
            elif audio_ids:
                rows: list[int] = []
                for aid in audio_ids:
                    for i, (_, fid) in enumerate(self._audio_formats):
                        if fid == aid:
                            rows.append(i + 2)  # AUTO/SKIP の分オフセット
                            break
                if rows:
                    self._audio_list.select_audio_rows(rows)
                else:
                    self._audio_list.select_auto()
            else:
                self._audio_list.select_auto()

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
        if self.get_audio_only():
            return

        auto_label = t("orig_auto")
        skip_label = t("orig_skip")

        if selected in (auto_label, skip_label) or not self._video_formats:
            self._restore_audio_normal_mode()
            if self._audio_formats:
                self._audio_list.setEnabled(True)
            return

        idx = self._format_index(self._video_combo, selected)
        if idx is None:
            return

        if 0 <= idx < len(self._video_formats):
            _, _, is_combined = self._video_formats[idx]
            if is_combined:
                self._audio_list.set_included_mode(t("orig_audio_included"))
            else:
                self._restore_audio_normal_mode()
                self._audio_list.setEnabled(True)

    def _restore_audio_normal_mode(self):
        """included → normal モードに切り替え（必要時のみ）。

        リストの中身を再構築する。"""
        if not self._audio_list.is_included_mode():
            return
        audio_labels = [lbl for lbl, _ in self._audio_formats]
        self._audio_list.set_normal_mode(t("orig_auto"), t("orig_skip"), audio_labels)
        # 復元: デフォルトは「自動」
        self._audio_list.select_auto()

    def _on_output_format_changed(self, button, checked: bool):
        if not checked:
            return
        is_audio = button is self._radio_audio
        is_mp4 = button is self._radio_mp4

        self._embed_thumbnail_check.setEnabled(is_mp4 or is_audio)
        if not (is_mp4 or is_audio):
            self._embed_thumbnail_check.setChecked(False)

        formats_available = bool(self._video_formats) or bool(self._audio_formats)
        if is_audio:
            self._video_combo.setEnabled(False)
            self._restore_audio_normal_mode()
            self._audio_list.setEnabled(bool(self._audio_formats))

            self._subtitle_list.clearSelection()
            self._subtitle_list.setEnabled(False)
            self._subtitle_fmt_combo.setEnabled(False)
            self._embed_check.setEnabled(False)
            self._embed_check.setChecked(False)
        else:
            if formats_available:
                self._video_combo.setEnabled(True)
                self._on_video_changed(self._video_combo.currentText())
            if self._subtitle_formats:
                self._subtitle_list.setEnabled(True)
            self._on_subtitle_changed()

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
        self._audio_list.setEnabled(False)
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
        audio_labels = [lbl for lbl, _ in self._audio_formats]

        self._video_combo.blockSignals(True)
        self._video_combo.clear()
        self._video_combo.addItems(video_labels)
        self._video_combo.setCurrentText(auto_label)
        self._video_combo.setEnabled(True)
        self._video_combo.blockSignals(False)

        self._audio_list.blockSignals(True)
        self._audio_list.set_normal_mode(auto_label, skip_label, audio_labels)
        self._audio_list.blockSignals(False)
        self._audio_list.select_auto()
        self._audio_list.setEnabled(bool(self._audio_formats))

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

        # 音声のみモードのときは映像コンボ / 字幕を改めて無効化する
        # (取得結果反映で setEnabled(True) されたものを元に戻す)
        checked_btn = self._remux_group.checkedButton()
        if checked_btn is not None:
            self._on_output_format_changed(checked_btn, True)

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

        self._fetch_button.setText(t("btn_fetch_formats"))
