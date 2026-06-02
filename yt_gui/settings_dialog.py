import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIntValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .formats import AUDIO_FORMATS, MP3_BITRATES, VIDEO_CONTAINERS, VIDEO_RESOLUTIONS
from .i18n import AVAILABLE_LANGUAGES, t
from .output_template import (
    DEFAULT_PLAYLIST_TEMPLATE,
    DEFAULT_VIDEO_TEMPLATE,
    TEMPLATE_FIELDS,
    YTDLP_OUTPUT_TEMPLATE_DOC_URL,
    render_preview,
    validate_template,
)
from .settings import (
    CONCURRENT_FRAGMENTS_MAX,
    CONCURRENT_FRAGMENTS_MIN,
    PROXY_SCHEMES,
    RATE_LIMIT_UNITS,
    RATE_LIMIT_VALUE_MAX,
    SPONSORBLOCK_CATEGORIES,
    SettingsManager,
)

_BROWSERS = [
    ("Brave", "brave"),
    ("Chrome", "chrome"),
    ("Chromium", "chromium"),
    ("Edge", "edge"),
    ("Firefox", "firefox"),
    ("Opera", "opera"),
    ("Vivaldi", "vivaldi"),
    ("Whale", "whale"),
]
if sys.platform == "darwin":
    _BROWSERS.append(("Safari", "safari"))

_BROWSER_DISPLAY = [label for label, _ in _BROWSERS]
_BROWSER_INTERNAL = [name for _, name in _BROWSERS]


class SettingsDialog(QDialog):
    def __init__(self, parent, manager: SettingsManager):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedSize(520, 520)

        self._manager = manager
        self._settings = manager.load()

        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        general_widget = QWidget()
        self._build_general_tab(general_widget)
        self._tabs.addTab(general_widget, t("tab_general"))

        quality_widget = QWidget()
        self._build_quality_tab(quality_widget)
        self._tabs.addTab(quality_widget, t("tab_quality"))

        template_widget = QWidget()
        self._build_output_template_tab(template_widget)
        self._template_tab_index = self._tabs.addTab(
            template_widget, t("tab_output_template")
        )

        download_widget = QWidget()
        self._build_download_tab(download_widget)
        self._tabs.addTab(download_widget, t("tab_download"))

        sponsorblock_widget = QWidget()
        self._build_sponsorblock_tab(sponsorblock_widget)
        self._tabs.addTab(sponsorblock_widget, t("tab_sponsorblock"))

        proxy_widget = QWidget()
        self._build_proxy_tab(proxy_widget)
        self._proxy_tab_index = self._tabs.addTab(proxy_widget, t("tab_proxy"))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(t("btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton(t("btn_save"))
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        root.addLayout(btn_layout)

    def _build_general_tab(self, parent: QWidget):
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        # Download folder
        layout.addWidget(
            QLabel(t("label_download_folder")), 0, 0, Qt.AlignmentFlag.AlignRight
        )
        self._download_edit = QLineEdit(self._settings.download_path)
        layout.addWidget(self._download_edit, 0, 1)
        btn_browse_dl = QPushButton(t("btn_browse"))
        btn_browse_dl.clicked.connect(self._browse_download)
        layout.addWidget(btn_browse_dl, 0, 2)

        # Cookies source
        layout.addWidget(
            QLabel(t("label_cookies_source")), 1, 0, Qt.AlignmentFlag.AlignRight
        )
        radio_widget = QWidget()
        radio_layout = QHBoxLayout(radio_widget)
        radio_layout.setContentsMargins(0, 0, 0, 0)

        self._cookies_btn_group = QButtonGroup(self)
        self._radio_none = QRadioButton(t("cookies_source_none"))
        self._radio_file = QRadioButton(t("cookies_source_file"))
        self._radio_browser = QRadioButton(t("cookies_source_browser"))
        for rb in (self._radio_none, self._radio_file, self._radio_browser):
            self._cookies_btn_group.addButton(rb)
            radio_layout.addWidget(rb)
        radio_layout.addStretch()
        layout.addWidget(radio_widget, 1, 1, 1, 2)

        # File detail row
        self._file_widget = QWidget()
        file_layout = QHBoxLayout(self._file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self._cookies_edit = QLineEdit(self._settings.cookies_path)
        file_layout.addWidget(self._cookies_edit)
        btn_browse_ck = QPushButton(t("btn_browse"))
        btn_browse_ck.clicked.connect(self._browse_cookies)
        file_layout.addWidget(btn_browse_ck)
        layout.addWidget(self._file_widget, 2, 1, 1, 2)

        # Browser detail row
        self._browser_widget = QWidget()
        browser_layout = QHBoxLayout(self._browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        current_browser_display = ""
        if self._settings.cookies_browser in _BROWSER_INTERNAL:
            current_browser_display = _BROWSER_DISPLAY[
                _BROWSER_INTERNAL.index(self._settings.cookies_browser)
            ]
        self._browser_combo = QComboBox()
        self._browser_combo.addItems(_BROWSER_DISPLAY)
        if current_browser_display:
            self._browser_combo.setCurrentText(current_browser_display)
        browser_layout.addWidget(self._browser_combo)
        browser_layout.addStretch()
        layout.addWidget(self._browser_widget, 2, 1, 1, 2)

        # Language
        layout.addWidget(QLabel(t("label_language")), 3, 0, Qt.AlignmentFlag.AlignRight)
        self._lang_display = [t(f"lang_{lang}") for lang in AVAILABLE_LANGUAGES]
        current_display = t(f"lang_{self._settings.language}")
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(self._lang_display)
        self._lang_combo.setCurrentText(current_display)
        layout.addWidget(self._lang_combo, 3, 1, 1, 2)

        layout.setRowStretch(4, 1)

        # Set initial state
        if self._settings.cookies_browser:
            self._radio_browser.setChecked(True)
        elif self._settings.cookies_path:
            self._radio_file.setChecked(True)
        else:
            self._radio_none.setChecked(True)

        self._cookies_btn_group.buttonClicked.connect(self._on_cookies_source_changed)
        self._on_cookies_source_changed()

    def _on_cookies_source_changed(self):
        is_file = self._radio_file.isChecked()
        is_browser = self._radio_browser.isChecked()
        self._file_widget.setVisible(is_file)
        self._browser_widget.setVisible(is_browser)

    def _on_audio_format_changed(self, index: int):
        is_mp3 = AUDIO_FORMATS[index] == "mp3" if index < len(AUDIO_FORMATS) else True
        self._bitrate_label.setVisible(is_mp3)
        self._bitrate_combo.setVisible(is_mp3)

    def _build_quality_tab(self, parent: QWidget):
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        layout.addWidget(
            QLabel(t("label_video_resolution")), 0, 0, Qt.AlignmentFlag.AlignRight
        )
        res_values = [f"{r}p" for r in VIDEO_RESOLUTIONS]
        self._res_combo = QComboBox()
        self._res_combo.addItems(res_values)
        self._res_combo.setCurrentText(f"{self._settings.video_resolution}p")
        layout.addWidget(self._res_combo, 0, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(
            QLabel(t("label_video_container")), 1, 0, Qt.AlignmentFlag.AlignRight
        )
        self._container_combo = QComboBox()
        self._container_combo.addItems([c.upper() for c in VIDEO_CONTAINERS])
        current_vc = self._settings.video_container
        vc_idx = (
            list(VIDEO_CONTAINERS).index(current_vc)
            if current_vc in VIDEO_CONTAINERS
            else 0
        )
        self._container_combo.setCurrentIndex(vc_idx)
        layout.addWidget(self._container_combo, 1, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(
            QLabel(t("label_audio_format")), 2, 0, Qt.AlignmentFlag.AlignRight
        )
        self._audio_fmt_combo = QComboBox()
        self._audio_fmt_combo.addItems([t("audio_format_mp3"), t("audio_format_flac")])
        current_af_idx = (
            list(AUDIO_FORMATS).index(self._settings.audio_format)
            if self._settings.audio_format in AUDIO_FORMATS
            else 0
        )
        self._audio_fmt_combo.setCurrentIndex(current_af_idx)
        self._audio_fmt_combo.currentIndexChanged.connect(self._on_audio_format_changed)
        layout.addWidget(self._audio_fmt_combo, 2, 1, Qt.AlignmentFlag.AlignLeft)

        self._bitrate_label = QLabel(t("label_mp3_bitrate"))
        layout.addWidget(self._bitrate_label, 3, 0, Qt.AlignmentFlag.AlignRight)
        bitrate_values = [f"{b}kbps" for b in MP3_BITRATES]
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItems(bitrate_values)
        self._bitrate_combo.setCurrentText(f"{self._settings.mp3_bitrate}kbps")
        layout.addWidget(self._bitrate_combo, 3, 1, Qt.AlignmentFlag.AlignLeft)

        note = QLabel(t("quality_note"))
        note.setStyleSheet("color: gray;")
        note.setWordWrap(True)
        layout.addWidget(note, 4, 0, 1, 2)
        layout.setRowStretch(5, 1)

        self._on_audio_format_changed(current_af_idx)

    def _build_output_template_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Single video template
        layout.addWidget(QLabel(t("label_template_video")))
        video_row = QHBoxLayout()
        self._video_template_edit = QLineEdit(self._settings.output_template_video)
        video_row.addWidget(self._video_template_edit)
        video_insert_btn = QToolButton()
        video_insert_btn.setText(f"{t('btn_template_insert')} ▼")
        video_insert_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        video_insert_btn.setMenu(self._build_insert_menu(self._video_template_edit))
        video_row.addWidget(video_insert_btn)
        layout.addLayout(video_row)
        self._video_preview = QLabel()
        self._video_preview.setStyleSheet("color: gray;")
        self._video_template_edit.textChanged.connect(
            lambda txt: self._update_preview(self._video_preview, txt)
        )
        self._update_preview(self._video_preview, self._video_template_edit.text())
        layout.addWidget(self._video_preview)

        # Playlist template
        layout.addWidget(QLabel(t("label_template_playlist")))
        playlist_row = QHBoxLayout()
        self._playlist_template_edit = QLineEdit(
            self._settings.output_template_playlist
        )
        playlist_row.addWidget(self._playlist_template_edit)
        playlist_insert_btn = QToolButton()
        playlist_insert_btn.setText(f"{t('btn_template_insert')} ▼")
        playlist_insert_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        playlist_insert_btn.setMenu(
            self._build_insert_menu(self._playlist_template_edit)
        )
        playlist_row.addWidget(playlist_insert_btn)
        layout.addLayout(playlist_row)
        self._playlist_preview = QLabel()
        self._playlist_preview.setStyleSheet("color: gray;")
        self._playlist_template_edit.textChanged.connect(
            lambda txt: self._update_preview(self._playlist_preview, txt)
        )
        self._update_preview(
            self._playlist_preview, self._playlist_template_edit.text()
        )
        layout.addWidget(self._playlist_preview)

        # Reset button
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton(t("btn_template_reset"))
        reset_btn.clicked.connect(self._reset_templates)
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)

        # Field reference
        fields_label = QLabel(f"<b>{t('label_template_fields')}</b>")
        layout.addWidget(fields_label)
        for placeholder, key in TEMPLATE_FIELDS:
            row = QLabel(
                f"<code>{placeholder}</code> &nbsp;–&nbsp; {t(f'tmpl_field_{key}')}"
            )
            row.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(row)

        # Docs link
        docs_row = QHBoxLayout()
        docs_row.addStretch()
        docs_btn = QPushButton(t("btn_open_ytdlp_docs"))
        docs_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(YTDLP_OUTPUT_TEMPLATE_DOC_URL))
        )
        docs_row.addWidget(docs_btn)
        layout.addLayout(docs_row)

        layout.addStretch()

    def _build_download_tab(self, parent: QWidget):
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        layout.addWidget(
            QLabel(t("label_concurrent_fragments")), 0, 0, Qt.AlignmentFlag.AlignRight
        )
        self._concurrent_fragments_spin = QSpinBox()
        self._concurrent_fragments_spin.setRange(
            CONCURRENT_FRAGMENTS_MIN, CONCURRENT_FRAGMENTS_MAX
        )
        value = self._settings.concurrent_fragments
        self._concurrent_fragments_spin.setValue(
            min(max(value, CONCURRENT_FRAGMENTS_MIN), CONCURRENT_FRAGMENTS_MAX)
        )
        layout.addWidget(
            self._concurrent_fragments_spin, 0, 1, Qt.AlignmentFlag.AlignLeft
        )

        note = QLabel(t("concurrent_fragments_note"))
        note.setStyleSheet("color: gray;")
        note.setWordWrap(True)
        layout.addWidget(note, 1, 0, 1, 2)

        layout.addWidget(
            QLabel(t("label_rate_limit")), 2, 0, Qt.AlignmentFlag.AlignRight
        )
        rate_row = QHBoxLayout()
        self._rate_limit_spin = QDoubleSpinBox()
        self._rate_limit_spin.setRange(0.0, RATE_LIMIT_VALUE_MAX)
        self._rate_limit_spin.setDecimals(1)
        self._rate_limit_spin.setValue(
            min(max(self._settings.rate_limit_value, 0.0), RATE_LIMIT_VALUE_MAX)
        )
        rate_row.addWidget(self._rate_limit_spin)
        self._rate_limit_unit_combo = QComboBox()
        self._rate_limit_unit_combo.addItems(
            [t(f"rate_limit_unit_{u.lower()}") for u in RATE_LIMIT_UNITS]
        )
        unit = self._settings.rate_limit_unit
        unit_index = RATE_LIMIT_UNITS.index(unit) if unit in RATE_LIMIT_UNITS else 1
        self._rate_limit_unit_combo.setCurrentIndex(unit_index)
        rate_row.addWidget(self._rate_limit_unit_combo)
        rate_row.addStretch()
        layout.addLayout(rate_row, 2, 1, Qt.AlignmentFlag.AlignLeft)

        rate_note = QLabel(t("rate_limit_note"))
        rate_note.setStyleSheet("color: gray;")
        rate_note.setWordWrap(True)
        layout.addWidget(rate_note, 3, 0, 1, 2)

        layout.setRowStretch(4, 1)

    def _build_sponsorblock_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(QLabel(t("label_sponsorblock_mode")))
        self._sb_btn_group = QButtonGroup(self)
        self._sb_radio_off = QRadioButton(t("sponsorblock_mode_off"))
        self._sb_radio_mark = QRadioButton(t("sponsorblock_mode_mark"))
        self._sb_radio_remove = QRadioButton(t("sponsorblock_mode_remove"))
        for rb in (self._sb_radio_off, self._sb_radio_mark, self._sb_radio_remove):
            self._sb_btn_group.addButton(rb)
            layout.addWidget(rb)

        self._sb_categories_label = QLabel(t("label_sponsorblock_categories"))
        layout.addWidget(self._sb_categories_label)

        saved = set(self._settings.sponsorblock_categories)
        self._sb_category_checks: dict[str, QCheckBox] = {}
        for cat in SPONSORBLOCK_CATEGORIES:
            check = QCheckBox(t(f"sponsorblock_cat_{cat}"))
            check.setChecked(cat in saved)
            layout.addWidget(check)
            self._sb_category_checks[cat] = check

        note = QLabel(t("sponsorblock_note"))
        note.setStyleSheet("color: gray;")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

        mode = self._settings.sponsorblock_mode
        if mode == "mark":
            self._sb_radio_mark.setChecked(True)
        elif mode == "remove":
            self._sb_radio_remove.setChecked(True)
        else:
            self._sb_radio_off.setChecked(True)

        self._sb_btn_group.buttonClicked.connect(self._on_sponsorblock_mode_changed)
        self._on_sponsorblock_mode_changed()

    def _on_sponsorblock_mode_changed(self):
        enabled = not self._sb_radio_off.isChecked()
        self._sb_categories_label.setEnabled(enabled)
        for check in self._sb_category_checks.values():
            check.setEnabled(enabled)

    def _build_proxy_tab(self, parent: QWidget):
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        self._proxy_check = QCheckBox(t("label_proxy_enabled"))
        self._proxy_check.setChecked(self._settings.proxy_enabled)
        layout.addWidget(self._proxy_check, 0, 0, 1, 2)

        layout.addWidget(
            QLabel(t("label_proxy_scheme")), 1, 0, Qt.AlignmentFlag.AlignRight
        )
        self._proxy_scheme_combo = QComboBox()
        self._proxy_scheme_combo.addItems(list(PROXY_SCHEMES))
        if self._settings.proxy_scheme in PROXY_SCHEMES:
            self._proxy_scheme_combo.setCurrentText(self._settings.proxy_scheme)
        layout.addWidget(self._proxy_scheme_combo, 1, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(
            QLabel(t("label_proxy_host")), 2, 0, Qt.AlignmentFlag.AlignRight
        )
        self._proxy_host_edit = QLineEdit(self._settings.proxy_host)
        self._proxy_host_edit.setPlaceholderText("example.com")
        layout.addWidget(self._proxy_host_edit, 2, 1)

        layout.addWidget(
            QLabel(t("label_proxy_port")), 3, 0, Qt.AlignmentFlag.AlignRight
        )
        self._proxy_port_edit = QLineEdit(self._settings.proxy_port)
        self._proxy_port_edit.setPlaceholderText("8080")
        self._proxy_port_edit.setValidator(QIntValidator(1, 65535, self))
        layout.addWidget(self._proxy_port_edit, 3, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(
            QLabel(t("label_proxy_username")), 4, 0, Qt.AlignmentFlag.AlignRight
        )
        self._proxy_username_edit = QLineEdit(self._settings.proxy_username)
        layout.addWidget(self._proxy_username_edit, 4, 1)

        layout.addWidget(
            QLabel(t("label_proxy_password")), 5, 0, Qt.AlignmentFlag.AlignRight
        )
        self._proxy_password_edit = QLineEdit(self._settings.proxy_password)
        self._proxy_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._proxy_password_edit, 5, 1)

        help_label = QLabel(t("proxy_help"))
        help_label.setStyleSheet("color: gray;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label, 6, 0, 1, 2)
        layout.setRowStretch(7, 1)

        self._proxy_inputs = (
            self._proxy_scheme_combo,
            self._proxy_host_edit,
            self._proxy_port_edit,
            self._proxy_username_edit,
            self._proxy_password_edit,
        )
        self._proxy_check.toggled.connect(self._on_proxy_toggled)
        self._on_proxy_toggled(self._proxy_check.isChecked())

    def _on_proxy_toggled(self, enabled: bool):
        for widget in self._proxy_inputs:
            widget.setEnabled(enabled)

    def _build_insert_menu(self, target_edit: QLineEdit) -> QMenu:
        menu = QMenu(self)
        for placeholder, key in TEMPLATE_FIELDS:
            label = f"{placeholder} — {t(f'tmpl_field_{key}')}"
            action = QAction(label, menu)
            action.triggered.connect(
                lambda _checked=False, p=placeholder: target_edit.insert(p)
            )
            menu.addAction(action)
        return menu

    @staticmethod
    def _update_preview(label: QLabel, template: str):
        rendered = render_preview(template)
        if rendered is None:
            label.setText(
                f"{t('label_template_preview')} {t('template_preview_invalid')}"
            )
        else:
            label.setText(f"{t('label_template_preview')} {rendered}")

    def _reset_templates(self):
        self._video_template_edit.setText(DEFAULT_VIDEO_TEMPLATE)
        self._playlist_template_edit.setText(DEFAULT_PLAYLIST_TEMPLATE)

    def _browse_download(self):
        path = QFileDialog.getExistingDirectory(self, t("dialog_select_folder"))
        if path:
            self._download_edit.setText(path)

    def _browse_cookies(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("label_cookies_file"),
            "",
            f"{t('filetype_text')} (*.txt);;{t('filetype_all')} (*.*)",
        )
        if path:
            self._cookies_edit.setText(path)

    def _save(self):
        video_template = self._video_template_edit.text().strip()
        playlist_template = self._playlist_template_edit.text().strip()
        for tmpl in (video_template, playlist_template):
            err_key = validate_template(tmpl)
            if err_key is not None:
                QMessageBox.warning(self, t("warn_title"), t(err_key))
                self._tabs.setCurrentIndex(self._template_tab_index)
                return

        if self._proxy_check.isChecked():
            host = self._proxy_host_edit.text().strip()
            if not host:
                QMessageBox.warning(self, t("warn_title"), t("warn_proxy_no_host"))
                self._tabs.setCurrentIndex(self._proxy_tab_index)
                return
            port_text = self._proxy_port_edit.text().strip()
            if port_text:
                try:
                    n = int(port_text)
                    if not (1 <= n <= 65535):
                        raise ValueError
                except ValueError:
                    QMessageBox.warning(self, t("warn_title"), t("warn_proxy_bad_port"))
                    self._tabs.setCurrentIndex(self._proxy_tab_index)
                    return

        lang_idx = self._lang_display.index(self._lang_combo.currentText())
        new_lang = AVAILABLE_LANGUAGES[lang_idx]

        self._settings.output_template_video = video_template
        self._settings.output_template_playlist = playlist_template
        self._settings.download_path = self._download_edit.text().strip()
        self._settings.language = new_lang
        self._settings.video_resolution = self._res_combo.currentText().removesuffix(
            "p"
        )
        vc_idx = self._container_combo.currentIndex()
        self._settings.video_container = (
            VIDEO_CONTAINERS[vc_idx] if vc_idx < len(VIDEO_CONTAINERS) else "mp4"
        )
        af_idx = self._audio_fmt_combo.currentIndex()
        self._settings.audio_format = (
            AUDIO_FORMATS[af_idx] if af_idx < len(AUDIO_FORMATS) else "mp3"
        )
        if self._settings.audio_format == "mp3":
            self._settings.mp3_bitrate = self._bitrate_combo.currentText().removesuffix(
                "kbps"
            )

        if self._radio_file.isChecked():
            self._settings.cookies_path = self._cookies_edit.text().strip()
            self._settings.cookies_browser = ""
        elif self._radio_browser.isChecked():
            disp = self._browser_combo.currentText()
            if disp in _BROWSER_DISPLAY:
                self._settings.cookies_browser = _BROWSER_INTERNAL[
                    _BROWSER_DISPLAY.index(disp)
                ]
            else:
                self._settings.cookies_browser = ""
            self._settings.cookies_path = ""
        else:
            self._settings.cookies_path = ""
            self._settings.cookies_browser = ""

        self._settings.concurrent_fragments = self._concurrent_fragments_spin.value()
        self._settings.rate_limit_value = self._rate_limit_spin.value()
        self._settings.rate_limit_unit = RATE_LIMIT_UNITS[
            self._rate_limit_unit_combo.currentIndex()
        ]

        if self._sb_radio_mark.isChecked():
            self._settings.sponsorblock_mode = "mark"
        elif self._sb_radio_remove.isChecked():
            self._settings.sponsorblock_mode = "remove"
        else:
            self._settings.sponsorblock_mode = ""
        self._settings.sponsorblock_categories = [
            cat for cat, check in self._sb_category_checks.items() if check.isChecked()
        ]

        self._settings.proxy_enabled = self._proxy_check.isChecked()
        self._settings.proxy_scheme = self._proxy_scheme_combo.currentText()
        self._settings.proxy_host = self._proxy_host_edit.text().strip()
        self._settings.proxy_port = self._proxy_port_edit.text().strip()
        self._settings.proxy_username = self._proxy_username_edit.text()
        self._settings.proxy_password = self._proxy_password_edit.text()

        self._manager.save(self._settings)

        self.accept()

    def _center_on_parent(self, parent):
        if parent is None:
            return
        pg = parent.geometry()
        dg = self.geometry()
        x = pg.x() + (pg.width() - dg.width()) // 2
        y = pg.y() + (pg.height() - dg.height()) // 2
        self.move(x, y)
