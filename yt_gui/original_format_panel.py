from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .downloader import Downloader
from .i18n import t
from .job_spec import PanelSnapshot
from .threading_utils import run_in_thread
from .utils import strip_ansi

_SUBTITLE_FORMATS = ("srt", "vtt", "best")
_COMMENTS_LANG = "comments"
_DANMAKU_LANG = "danmaku"
# ニコニコ comments・ビリビリ danmaku の双方をコメント・弾幕グループの対象とする。
_COMMENT_DANMAKU_LANGS = (_COMMENTS_LANG, _DANMAKU_LANG)

# コンボ・リストの「自動」「ダウンロードしない」項目を翻訳済み文字列ではなく
# `userData` のセンチネルで識別するための定数。
# 表示文字列 (`t("orig_auto")` 等) と論理状態を完全分離する。
_AUTO_SENTINEL = "__auto__"
_SKIP_SENTINEL = "__skip__"

# ニコニコ動画コメント → ASS 変換のデフォルト値
_NICO_DEFAULT_WIDTH = 1280
_NICO_DEFAULT_HEIGHT = 720
_NICO_DEFAULT_DURATION = 8.0
_NICO_DEFAULT_OPACITY = 0.8
_NICO_DEFAULT_FONT_SIZE = 32


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

    AUTO/SKIP の物理行オフセット (+2) は内部に閉じ込め、外部からは
    `audio_row(i)` / `audio_index_from_row(row)` 経由でアクセスする。
    """

    AUTO_ROW = 0
    SKIP_ROW = 1
    _AUDIO_OFFSET = 2

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
        self,
        auto_label: str,
        skip_label: str,
        audio_entries: list[tuple[str, str]],
    ):
        """通常モードに切り替える。フォーマット取得後やリセット時に呼ぶ。

        `audio_entries` は `(表示ラベル, 音声ID)` のリスト。
        AUTO/SKIP 行には sentinel を userData にセットし、音声行には
        音声 ID を userData にセットすることで「翻訳済み文字列と論理状態の
        分離」と「呼び出し側からのオフセット隠蔽」を両立する。
        """
        self._mode = "normal"
        self._suppress_enforce = True
        self.clear()
        self.addItem(auto_label)
        self.item(self.AUTO_ROW).setData(Qt.ItemDataRole.UserRole, _AUTO_SENTINEL)
        self.addItem(skip_label)
        self.item(self.SKIP_ROW).setData(Qt.ItemDataRole.UserRole, _SKIP_SENTINEL)
        for lbl, fid in audio_entries:
            self.addItem(lbl)
            self.item(self.count() - 1).setData(Qt.ItemDataRole.UserRole, fid)
        self._suppress_enforce = False

    def is_included_mode(self) -> bool:
        return self._mode == "included"

    def audio_row(self, audio_index: int) -> int:
        """音声フォーマットの 0-based インデックスをリストの物理行に変換。"""
        return audio_index + self._AUDIO_OFFSET

    def audio_index_from_row(self, row: int) -> int | None:
        """リスト物理行を音声フォーマットの 0-based インデックスに変換。
        AUTO/SKIP 行のときは `None`。"""
        if row < self._AUDIO_OFFSET:
            return None
        return row - self._AUDIO_OFFSET

    def is_meta_row(self, row: int) -> bool:
        return row < self._AUDIO_OFFSET

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
            if (
                auto_selected
                and (skip_selected or audio_rows)
                # 「自動」が他と同時選択されたら自動を解除
                and len(sel) > 1
                and auto_item is not None
            ):
                auto_item.setSelected(False)
            if skip_selected and audio_rows and skip_item is not None:
                skip_item.setSelected(False)
            # 上で auto を解除済みの可能性があるが念のため
            if skip_selected and auto_selected and auto_item is not None:
                auto_item.setSelected(False)
        finally:
            self._suppress_enforce = False


class _NicoCommentsGroup(QGroupBox):
    """ニコニコ動画コメント (ASS 変換 / MKV 統合) 設定グループ。

    `comments` lang が字幕リストに含まれるときだけ親パネルから可視化される。
    親パネル (OriginalFormatPanel) は以下を委譲する:
      - 出力モード (audio_only / remux_only) の変化 → `update_output_mode`
      - 選択中映像の解像度 (`auto_resolution` 用) → コンストラクタの callback
      - ASS 変換 ON 時に字幕リストの `comments` lang を自動選択する処理
        → `request_select_comments` シグナルを親が捕捉
    """

    request_select_comments = Signal()

    def __init__(
        self,
        parent=None,
        *,
        get_video_resolution: Callable[[], tuple[int, int] | None],
    ):
        super().__init__(t("nico_group_title"), parent)
        self._get_video_resolution = get_video_resolution
        self._output_audio_only = False
        self._output_remux_only = False
        self.setVisible(False)
        # 内部の SpinBox が潰れないよう vertical SizePolicy を Fixed にする
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._build()
        self._set_controls_enabled(False)

    def _build(self):
        # チェック行 + パラメータグリッド（2 列 × 2 行）。詳細設定が別画面化して
        # 高さに余裕が出たため、横一列をやめて折り返し横幅を抑える。
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        check_row = QHBoxLayout()
        check_row.setSpacing(12)
        self._convert_check = QCheckBox(t("nico_convert_ass"))
        self._convert_check.toggled.connect(self._on_convert_toggled)
        check_row.addWidget(self._convert_check)
        self._embed_mkv_check = QCheckBox(t("nico_embed_mkv"))
        self._embed_mkv_check.toggled.connect(self._on_embed_mkv_toggled)
        check_row.addWidget(self._embed_mkv_check)
        self._hardsub_check = QCheckBox(t("nico_burn_in"))
        self._hardsub_check.setToolTip(t("nico_burn_in_tooltip"))
        self._hardsub_check.toggled.connect(self._on_hardsub_toggled)
        check_row.addWidget(self._hardsub_check)
        check_row.addStretch()
        layout.addLayout(check_row)

        self._auto_res_check = QCheckBox(t("nico_auto_resolution"))
        self._auto_res_check.setChecked(True)
        self._auto_res_check.toggled.connect(self._on_auto_res_toggled)
        layout.addWidget(self._auto_res_check)

        params = QGridLayout()
        params.setHorizontalSpacing(8)
        params.setVerticalSpacing(4)

        # 行1: 解像度 (幅 × 高さ) | 表示時間
        self._resolution_label = QLabel(t("nico_resolution"))
        params.addWidget(self._resolution_label, 0, 0)
        res_widget = QWidget()
        res_row = QHBoxLayout(res_widget)
        res_row.setContentsMargins(0, 0, 0, 0)
        res_row.setSpacing(4)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(320, 7680)
        self._width_spin.setSingleStep(2)
        self._width_spin.setValue(_NICO_DEFAULT_WIDTH)
        self._width_spin.setSuffix(" px")
        res_row.addWidget(self._width_spin)
        res_row.addWidget(QLabel("×"))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(240, 4320)
        self._height_spin.setSingleStep(2)
        self._height_spin.setValue(_NICO_DEFAULT_HEIGHT)
        self._height_spin.setSuffix(" px")
        res_row.addWidget(self._height_spin)
        params.addWidget(res_widget, 0, 1)

        self._duration_label = QLabel(t("nico_duration"))
        params.addWidget(self._duration_label, 0, 2)
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(1.0, 60.0)
        self._duration_spin.setSingleStep(0.5)
        self._duration_spin.setValue(_NICO_DEFAULT_DURATION)
        params.addWidget(self._duration_spin, 0, 3)

        # 行2: 不透明度 | フォントサイズ
        self._opacity_label = QLabel(t("nico_opacity"))
        params.addWidget(self._opacity_label, 1, 0)
        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setRange(0.1, 1.0)
        self._opacity_spin.setSingleStep(0.1)
        self._opacity_spin.setValue(_NICO_DEFAULT_OPACITY)
        params.addWidget(self._opacity_spin, 1, 1)

        self._font_label = QLabel(t("nico_font_size"))
        params.addWidget(self._font_label, 1, 2)
        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 128)
        self._font_spin.setValue(_NICO_DEFAULT_FONT_SIZE)
        self._font_spin.setSuffix(" px")
        params.addWidget(self._font_spin, 1, 3)

        params.setColumnStretch(4, 1)  # 余白を右に逃がして左寄せ
        layout.addLayout(params)

        self.setLayout(layout)

    def reset(self):
        """初期状態へ戻す。"""
        self.setVisible(False)
        self._convert_check.setChecked(False)
        self._embed_mkv_check.setChecked(False)
        self._hardsub_check.setChecked(False)
        self._auto_res_check.setChecked(True)
        self._width_spin.setValue(_NICO_DEFAULT_WIDTH)
        self._height_spin.setValue(_NICO_DEFAULT_HEIGHT)
        self._duration_spin.setValue(_NICO_DEFAULT_DURATION)
        self._opacity_spin.setValue(_NICO_DEFAULT_OPACITY)
        self._font_spin.setValue(_NICO_DEFAULT_FONT_SIZE)
        self._set_controls_enabled(False)

    def retranslate(self):
        self.setTitle(t("nico_group_title"))
        self._convert_check.setText(t("nico_convert_ass"))
        self._embed_mkv_check.setText(t("nico_embed_mkv"))
        self._hardsub_check.setText(t("nico_burn_in"))
        self._hardsub_check.setToolTip(t("nico_burn_in_tooltip"))
        self._auto_res_check.setText(t("nico_auto_resolution"))
        self._resolution_label.setText(t("nico_resolution"))
        self._duration_label.setText(t("nico_duration"))
        self._opacity_label.setText(t("nico_opacity"))
        self._font_label.setText(t("nico_font_size"))

    def get_opts(self) -> dict:
        """ニコニコ動画コメント → ASS 変換オプションを返す。

        `auto_resolution=True` かつ親から解像度情報が取得できれば、
        スピンボックスの値ではなく動画の実解像度を採用する。
        """
        auto_res = bool(self._auto_res_check.isChecked())
        w = int(self._width_spin.value())
        h = int(self._height_spin.value())
        if auto_res:
            detected = self._get_video_resolution()
            if detected is not None:
                w, h = detected
        return {
            "convert_to_ass": bool(self._convert_check.isChecked()),
            "embed_to_mkv": bool(self._embed_mkv_check.isChecked()),
            "burn_in": bool(self._hardsub_check.isChecked()),
            "auto_resolution": auto_res,
            "resolution_w": w,
            "resolution_h": h,
            "duration_sec": float(self._duration_spin.value()),
            "opacity": float(self._opacity_spin.value()),
            "font_size": int(self._font_spin.value()),
        }

    def restore_from(self, settings: dict):
        """`settings["nico_comments"]` から状態を復元する。

        欠如時はデフォルト値を用いる。"""
        nico = settings.get("nico_comments") or {}
        self._auto_res_check.setChecked(bool(nico.get("auto_resolution", True)))
        self._width_spin.setValue(int(nico.get("resolution_w", _NICO_DEFAULT_WIDTH)))
        self._height_spin.setValue(int(nico.get("resolution_h", _NICO_DEFAULT_HEIGHT)))
        self._duration_spin.setValue(
            float(nico.get("duration_sec", _NICO_DEFAULT_DURATION))
        )
        self._opacity_spin.setValue(float(nico.get("opacity", _NICO_DEFAULT_OPACITY)))
        self._font_spin.setValue(int(nico.get("font_size", _NICO_DEFAULT_FONT_SIZE)))
        self._convert_check.setChecked(bool(nico.get("convert_to_ass", False)))
        self._embed_mkv_check.setChecked(bool(nico.get("embed_to_mkv", False)))
        self._hardsub_check.setChecked(bool(nico.get("burn_in", False)))

    def update_output_mode(self, *, audio_only: bool, remux_only: bool):
        """出力モードに応じて MKV 統合 / 焼きこみチェックの利用可否を更新する。"""
        self._output_audio_only = audio_only
        self._output_remux_only = remux_only
        self._refresh_integration_enabled()

    def _on_convert_toggled(self, checked: bool):
        """ASS 変換チェック切替: 子コントロールを enable/disable し、
        ON 時には親に `comments` lang 自動選択を要求する。OFF にしたとき
        は MKV 統合 / 焼きこみチェックも連動して OFF にする (どちらも ASS
        変換に依存するため)。"""
        self._set_controls_enabled(checked)
        if not checked:
            for check in (self._embed_mkv_check, self._hardsub_check):
                if check.isChecked():
                    check.blockSignals(True)
                    check.setChecked(False)
                    check.blockSignals(False)
        if checked:
            self.request_select_comments.emit()

    def _on_embed_mkv_toggled(self, checked: bool):
        """MKV 統合チェック切替: ON 時は ASS 変換チェックを強制 ON にする。"""
        if checked and not self._convert_check.isChecked():
            self._convert_check.setChecked(True)

    def _on_hardsub_toggled(self, checked: bool):
        """焼きこみチェック切替: ON 時は ASS 変換チェックを強制 ON にする
        (焼きこみは ASS 変換に依存するため)。"""
        if checked and not self._convert_check.isChecked():
            self._convert_check.setChecked(True)

    def _on_auto_res_toggled(self, checked: bool):
        """解像度自動追従チェック切替: ON 時は手動解像度入力を無効化する
        (フォールバック値として残す)。"""
        self._width_spin.setEnabled((not checked) and self._convert_check.isChecked())
        self._height_spin.setEnabled((not checked) and self._convert_check.isChecked())

    def _set_controls_enabled(self, enabled: bool):
        for w in (
            self._duration_spin,
            self._opacity_spin,
            self._font_spin,
            self._auto_res_check,
        ):
            w.setEnabled(enabled)
        manual_res_enabled = enabled and not self._auto_res_check.isChecked()
        self._width_spin.setEnabled(manual_res_enabled)
        self._height_spin.setEnabled(manual_res_enabled)
        self._refresh_integration_enabled()

    def _refresh_integration_enabled(self):
        """MKV 統合 / 焼きこみチェックの enabled 状態を再評価する。

        ASS 変換 ON かつ出力モードが動画を生成するモード（音声のみ /
        remux のみ以外）のときだけ操作可能。disable 化したときに ON だった
        場合はシグナルを止めて OFF に戻す（動画統合の対象外）。
        """
        usable = (
            self._convert_check.isChecked()
            and not self._output_audio_only
            and not self._output_remux_only
        )
        for check in (self._embed_mkv_check, self._hardsub_check):
            check.setEnabled(usable)
            if not usable and check.isChecked():
                check.blockSignals(True)
                check.setChecked(False)
                check.blockSignals(False)


class _PanelSignals(QObject):
    """フォーマット取得スレッドは `threading_utils.run_in_thread` に移行したため、
    パネル内部のレイアウト通知用シグナルだけが残る。"""

    size_hint_changed = Signal()  # 内部レイアウトの sizeHint が変わったとき


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
        # 映像 ID → (width, height) — フェーズ 3: コメント ASS 解像度の自動追従用
        self._video_resolutions: dict[str, tuple[int, int]] = {}
        self._fetched_title: str = ""
        self._audio_label: str = "MP3"

        self._signals = _PanelSignals()

        self._build_widgets()
        self._pending_restore: dict | None = None

    def _build_widgets(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(6)

        # Row 0: Video combo + fetch button
        video_row = QHBoxLayout()
        video_row.setSpacing(6)
        self._video_label = QLabel(t("label_orig_video"))
        video_row.addWidget(self._video_label)
        self._video_combo = QComboBox()
        self._video_combo.addItem(t("orig_auto"), _AUTO_SENTINEL)
        self._video_combo.setEnabled(False)
        self._video_combo.currentIndexChanged.connect(self._on_video_changed)
        video_row.addWidget(self._video_combo, 1)

        self._fetch_button = QPushButton(t("btn_fetch_formats"))
        self._fetch_button.clicked.connect(self._start_fetch_thread)
        video_row.addWidget(self._fetch_button)
        outer.addLayout(video_row)

        # Row 1: Audio (left) + Subtitle (right) side-by-side
        lists_row = QHBoxLayout()
        lists_row.setSpacing(8)

        audio_col = QVBoxLayout()
        audio_col.setSpacing(2)
        self._audio_label_widget = QLabel(t("label_orig_audio"))
        audio_col.addWidget(self._audio_label_widget)
        self._audio_list = _AudioListWidget()
        self._audio_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._audio_list.setMinimumHeight(96)
        self._audio_list.set_normal_mode(t("orig_auto"), t("orig_skip"), [])
        self._audio_list.item(_AudioListWidget.AUTO_ROW).setSelected(True)
        self._audio_list.setEnabled(False)
        audio_col.addWidget(self._audio_list)
        lists_row.addLayout(audio_col, 1)

        subtitle_col = QVBoxLayout()
        subtitle_col.setSpacing(2)
        self._subtitle_label = QLabel(t("label_orig_subtitle"))
        subtitle_col.addWidget(self._subtitle_label)
        self._subtitle_list = _ToggleListWidget()
        self._subtitle_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._subtitle_list.setEnabled(False)
        self._subtitle_list.setMinimumHeight(96)
        self._subtitle_list.itemSelectionChanged.connect(self._on_subtitle_changed)
        subtitle_col.addWidget(self._subtitle_list)

        sub_ctrl_row = QHBoxLayout()
        sub_ctrl_row.setContentsMargins(0, 0, 0, 0)
        sub_ctrl_row.setSpacing(4)
        self._subtitle_fmt_combo = QComboBox()
        self._subtitle_fmt_combo.addItems(_SUBTITLE_FORMATS)
        self._subtitle_fmt_combo.setEnabled(False)
        self._subtitle_fmt_combo.setMaximumWidth(70)
        sub_ctrl_row.addWidget(self._subtitle_fmt_combo)
        self._embed_check = QCheckBox(t("orig_sub_embed"))
        self._embed_check.setEnabled(False)
        sub_ctrl_row.addWidget(self._embed_check)
        sub_ctrl_row.addStretch()
        subtitle_col.addLayout(sub_ctrl_row)
        lists_row.addLayout(subtitle_col, 1)
        outer.addLayout(lists_row)

        # Row 2: Output format radio buttons
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self._output_label = QLabel(t("label_orig_output"))
        out_row.addWidget(self._output_label)
        self._remux_group = QButtonGroup(self)
        self._radio_mp4 = QRadioButton(t("orig_output_mp4").format(container="MP4"))
        self._radio_remux = QRadioButton(t("orig_output_remux"))
        self._radio_recode = QRadioButton(t("orig_output_recode"))
        self._radio_recode.setToolTip(t("orig_output_recode_tooltip"))
        self._radio_audio = QRadioButton(
            t("orig_output_audio_only").format(label=self._audio_label)
        )
        self._radio_mp4.setChecked(True)
        self._remux_group.addButton(self._radio_mp4, 0)
        self._remux_group.addButton(self._radio_remux, 1)
        self._remux_group.addButton(self._radio_recode, 2)
        self._remux_group.addButton(self._radio_audio, 3)
        self._remux_group.buttonToggled.connect(self._on_output_format_changed)
        out_row.addWidget(self._radio_mp4)
        out_row.addWidget(self._radio_remux)
        out_row.addWidget(self._radio_recode)
        out_row.addWidget(self._radio_audio)
        out_row.addStretch()
        outer.addLayout(out_row)

        # Row 3: Embed checkboxes (thumbnail / metadata / chapters) in one row
        embed_row = QHBoxLayout()
        embed_row.setSpacing(12)
        self._embed_thumbnail_check = QCheckBox(t("orig_embed_thumbnail"))
        embed_row.addWidget(self._embed_thumbnail_check)
        self._embed_metadata_check = QCheckBox(t("orig_embed_metadata"))
        self._embed_metadata_check.setChecked(True)
        embed_row.addWidget(self._embed_metadata_check)
        self._embed_chapters_check = QCheckBox(t("orig_embed_chapters"))
        self._embed_chapters_check.setChecked(True)
        embed_row.addWidget(self._embed_chapters_check)
        embed_row.addStretch()
        outer.addLayout(embed_row)

        # ニコニコ動画コメント (ASS 変換) グループ。
        # `comments` lang が字幕リストに含まれるときだけ可視化する。
        self._nico_group: _NicoCommentsGroup = _NicoCommentsGroup(
            get_video_resolution=self._get_selected_video_resolution,
        )
        self._nico_group.request_select_comments.connect(
            self._on_request_select_comments
        )
        outer.addWidget(self._nico_group)

    # ── public interface ─────────────────────────────────────────────────────

    def trigger_fetch(self):
        self._start_fetch_thread()

    def reset(self):
        """フォーマット取得結果と選択状態を初期状態へ戻す。"""
        self._video_formats = []
        self._audio_formats = []
        self._subtitle_formats = []
        self._video_resolutions = {}
        self._fetched_title = ""
        self._pending_restore = None

        self._video_combo.blockSignals(True)
        self._video_combo.clear()
        self._video_combo.addItem(t("orig_auto"), _AUTO_SENTINEL)
        self._video_combo.setEnabled(False)
        self._video_combo.blockSignals(False)

        self._audio_list.blockSignals(True)
        self._audio_list.set_normal_mode(t("orig_auto"), t("orig_skip"), [])
        self._audio_list.item(_AudioListWidget.AUTO_ROW).setSelected(True)
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

        self._nico_group.reset()

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
        self._radio_recode.setText(t("orig_output_recode"))
        self._radio_recode.setToolTip(t("orig_output_recode_tooltip"))
        self._radio_audio.setText(
            t("orig_output_audio_only").format(label=self._audio_label)
        )
        self._embed_thumbnail_check.setText(t("orig_embed_thumbnail"))
        self._embed_metadata_check.setText(t("orig_embed_metadata"))
        self._embed_chapters_check.setText(t("orig_embed_chapters"))
        self._nico_group.retranslate()

    def has_formats_loaded(self) -> bool:
        return bool(self._fetched_title) and (
            bool(self._video_formats) or bool(self._audio_formats)
        )

    def get_fetched_title(self) -> str:
        return self._fetched_title

    def is_both_skipped(self) -> bool:
        return bool(
            self._video_combo.currentData() == _SKIP_SENTINEL
            and self.is_audio_skipped()
        )

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

    def get_recode_video(self) -> bool:
        return bool(self._radio_recode.isChecked())

    def get_embed_thumbnail(self) -> bool:
        return bool(self._embed_thumbnail_check.isChecked())

    def get_embed_metadata(self) -> bool:
        return bool(self._embed_metadata_check.isChecked())

    def get_embed_chapters(self) -> bool:
        return bool(self._embed_chapters_check.isChecked())

    def on_size_hint_changed(self, callback: Callable[[], None]) -> None:
        """パネル内部のレイアウトが変わって sizeHint が変化したときに呼ばれる
        コールバックを登録する（例: 内包する OriginalFormatDialog の再フィット用）。"""
        self._signals.size_hint_changed.connect(callback)

    def get_nico_comments_opts(self) -> dict:
        return self._nico_group.get_opts()

    def _get_selected_video_resolution(self) -> tuple[int, int] | None:
        """選択中の映像フォーマット ID に対応する (width, height) を返す。
        「自動」「ダウンロードしない」または解像度未知のときは None。"""
        fid = self._current_video_format_id()
        if fid is None:
            return None
        return self._video_resolutions.get(fid)

    def _current_video_format_id(self) -> str | None:
        """映像コンボの現在選択値。AUTO/SKIP のときは None。"""
        data = self._video_combo.currentData()
        if data in (_AUTO_SENTINEL, _SKIP_SENTINEL, None):
            return None
        return str(data)

    def _has_nico_comments_lang(self) -> bool:
        """字幕フォーマットにコメント/弾幕 lang（`comments` または `danmaku`）が
        含まれるか。"""
        return any(
            lang in _COMMENT_DANMAKU_LANGS for _, lang, _ in self._subtitle_formats
        )

    def _on_request_select_comments(self):
        """`_NicoCommentsGroup` から ASS 変換 ON 通知を受けたとき、
        字幕リストのコメント/弾幕 lang（`comments` または `danmaku`）を
        自動選択する。"""
        if not self._subtitle_formats:
            return
        for i, (_, lang, _) in enumerate(self._subtitle_formats):
            if lang not in _COMMENT_DANMAKU_LANGS:
                continue
            item = self._subtitle_list.item(i)
            if item is not None and not item.isSelected():
                self._subtitle_list.blockSignals(True)
                item.setSelected(True)
                self._subtitle_list.blockSignals(False)
                self._on_subtitle_changed()
            break

    def get_snapshot(self) -> PanelSnapshot:
        """build_job_spec に渡す UI 非依存スナップショットを返す。"""
        return PanelSnapshot(
            format_spec=self.get_format_spec(),
            subtitle_opts=self.get_subtitle_opts(),
            remux_only=self.get_remux_only(),
            audio_only=self.get_audio_only(),
            recode_video=self.get_recode_video(),
            embed_thumbnail=self.get_embed_thumbnail(),
            embed_metadata=self.get_embed_metadata(),
            embed_chapters=self.get_embed_chapters(),
            has_multiple_audio=self.has_multiple_audio_selected(),
            raw_settings=self.get_raw_settings(),
        )

    def get_raw_settings(self) -> dict:
        """現在の選択状態を復元可能な形式で返す。"""
        current_data = self._video_combo.currentData()
        video_skip = current_data == _SKIP_SENTINEL
        video_id: str | None = None
        is_combined = False

        fid = self._current_video_format_id()
        if fid is not None and self._video_formats:
            for _, vid, combined in self._video_formats:
                if vid == fid:
                    video_id = vid
                    is_combined = combined
                    break

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
            "recode_video": self.get_recode_video(),
            "embed_thumbnail": self.get_embed_thumbnail(),
            "embed_metadata": self.get_embed_metadata(),
            "embed_chapters": self.get_embed_chapters(),
            "nico_comments": self.get_nico_comments_opts(),
        }

    def _collect_selected_audio_ids(self) -> list[str]:
        """音声リストの選択行から音声 ID のみを抽出（auto/skip/included は除外）。"""
        if not self._audio_formats or self._audio_list.is_included_mode():
            return []
        _, _, rows = self._audio_list.get_selection()
        out: list[str] = []
        for row in rows:
            audio_idx = self._audio_list.audio_index_from_row(row)
            if audio_idx is not None and 0 <= audio_idx < len(self._audio_formats):
                _, fid = self._audio_formats[audio_idx]
                out.append(fid)
        return out

    def restore_from_settings(self, settings: dict):
        """チェックボックス・ラジオボタンを即時復元し、映像/音声/字幕はフォーマット取得後に復元する。"""
        audio_only = settings.get("audio_only", False)
        remux_only = settings.get("remux_only", False)
        recode_video = settings.get("recode_video", False)
        if audio_only:
            self._radio_audio.setChecked(True)
            self._embed_thumbnail_check.setChecked(
                settings.get("embed_thumbnail", False)
            )
        elif remux_only:
            self._radio_remux.setChecked(True)
        elif recode_video:
            self._radio_recode.setChecked(True)
            self._embed_thumbnail_check.setChecked(
                settings.get("embed_thumbnail", False)
            )
        else:
            self._radio_mp4.setChecked(True)
            self._embed_thumbnail_check.setChecked(
                settings.get("embed_thumbnail", False)
            )
        self._embed_metadata_check.setChecked(settings.get("embed_metadata", True))
        self._embed_chapters_check.setChecked(settings.get("embed_chapters", True))

        self._nico_group.restore_from(settings)

        self._pending_restore = settings
        if self.has_formats_loaded():
            self._apply_pending_restore()
            self._pending_restore = None

    def get_format_spec(self) -> str:
        audio_ids = self._collect_selected_audio_ids()
        audio_skip = self.is_audio_skipped()

        if self.get_audio_only():
            # 音声のみモードでは先頭の 1 件のみ使用（仕様: フェーズ 1）
            if audio_ids:
                return audio_ids[0]
            return "bestaudio/best"

        current_data = self._video_combo.currentData()
        video_skip = current_data == _SKIP_SENTINEL

        video_id: str | None = None
        is_combined = False
        fid = self._current_video_format_id()
        if fid is not None and self._video_formats:
            for _, vid, combined in self._video_formats:
                if vid == fid:
                    video_id = vid
                    is_combined = combined
                    break

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
            self._video_combo.setCurrentIndex(
                self._video_combo.findData(_SKIP_SENTINEL)
            )
        elif video_id:
            idx = self._video_combo.findData(video_id)
            if idx >= 0:
                self._video_combo.setCurrentIndex(idx)
            else:
                self._video_combo.setCurrentIndex(
                    self._video_combo.findData(_AUTO_SENTINEL)
                )
        else:
            self._video_combo.setCurrentIndex(
                self._video_combo.findData(_AUTO_SENTINEL)
            )
        self._video_combo.blockSignals(False)
        self._on_video_changed()

        # 音声リスト復元（複合フォーマット選択時はスキップ）
        if not is_combined and not self._audio_list.is_included_mode():
            if audio_skip:
                self._audio_list.select_skip()
            elif audio_ids:
                rows: list[int] = []
                for aid in audio_ids:
                    for i, (_, fid) in enumerate(self._audio_formats):
                        if fid == aid:
                            rows.append(self._audio_list.audio_row(i))
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

    def _on_video_changed(self, *_args):
        """映像コンボ選択変更ハンドラ。
        Qt から `currentIndexChanged(int)` 経由で呼ばれるほか、復元処理から
        引数なしでも呼ばれるので、シグネチャは可変長で受ける。"""
        if self.get_audio_only():
            return

        if not self._video_formats:
            self._restore_audio_normal_mode()
            if self._audio_formats:
                self._audio_list.setEnabled(True)
            return

        fid = self._current_video_format_id()
        if fid is None:
            self._restore_audio_normal_mode()
            if self._audio_formats:
                self._audio_list.setEnabled(True)
            return

        is_combined = False
        for _, vid, combined in self._video_formats:
            if vid == fid:
                is_combined = combined
                break

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
        self._audio_list.set_normal_mode(
            t("orig_auto"), t("orig_skip"), list(self._audio_formats)
        )
        # 復元: デフォルトは「自動」
        self._audio_list.select_auto()

    def _on_output_format_changed(self, button, checked: bool):
        if not checked:
            return
        is_audio = button is self._radio_audio
        is_mp4 = button is self._radio_mp4
        is_recode = button is self._radio_recode

        # 再エンコードも出力は mp4 なのでサムネイル埋め込み可（remux のみ不可）
        thumb_ok = is_mp4 or is_recode or is_audio
        self._embed_thumbnail_check.setEnabled(thumb_ok)
        if not thumb_ok:
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
                self._on_video_changed()
            if self._subtitle_formats:
                self._subtitle_list.setEnabled(True)
            self._on_subtitle_changed()
        # 出力モードに応じて MKV 統合チェックの利用可否を更新
        self._nico_group.update_output_mode(
            audio_only=self._radio_audio.isChecked(),
            remux_only=self._radio_remux.isChecked(),
        )

    def _on_subtitle_changed(self):
        has_sub = bool(self._subtitle_list.selectedItems()) and bool(
            self._subtitle_formats
        )
        self._subtitle_fmt_combo.setEnabled(has_sub)
        self._embed_check.setEnabled(has_sub)
        if not has_sub:
            self._embed_check.setChecked(False)

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

        def _on_failed(exc: Exception) -> None:
            err_str = strip_ansi(str(exc))
            is_playlist = "playlist" in err_str.lower()
            self._on_fetch_failed(err_str, is_playlist)

        run_in_thread(
            lambda: self._downloader.fetch_formats(url, cookies_path, cookies_browser),
            on_done=self._on_fetch_done,
            on_failed=_on_failed,
            on_finished=self._on_fetch_finished,
            parent=self,
        )

    def _on_fetch_done(self, result: dict):
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")

        self._fetched_title = result.get("title", "")
        self._video_formats = result["video"]
        self._audio_formats = result["audio"]
        self._subtitle_formats = result["subtitles"]
        self._video_resolutions = result.get("video_resolutions", {}) or {}

        self._video_combo.blockSignals(True)
        self._video_combo.clear()
        self._video_combo.addItem(auto_label, _AUTO_SENTINEL)
        self._video_combo.addItem(skip_label, _SKIP_SENTINEL)
        for lbl, fid, _ in self._video_formats:
            self._video_combo.addItem(lbl, fid)
        self._video_combo.setCurrentIndex(0)
        self._video_combo.setEnabled(True)
        self._video_combo.blockSignals(False)

        self._audio_list.blockSignals(True)
        self._audio_list.set_normal_mode(
            auto_label, skip_label, list(self._audio_formats)
        )
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

        # `comments` lang (ニコニコ動画) が含まれるときだけグループを可視化
        # 可視化前後でパネルの sizeHint が変わるので親 (ダイアログ) に通知する
        self._nico_group.setVisible(self._has_nico_comments_lang())
        self.updateGeometry()
        self._signals.size_hint_changed.emit()

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
