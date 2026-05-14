import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .formats import AUDIO_FORMATS, MP3_BITRATES, VIDEO_CONTAINERS, VIDEO_RESOLUTIONS
from .i18n import AVAILABLE_LANGUAGES, t
from .settings import SettingsManager

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
        self.setFixedSize(480, 355)

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
                _BROWSER_INTERNAL.index(self._settings.cookies_browser)]
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
            if current_vc in VIDEO_CONTAINERS else 0
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
            if self._settings.audio_format in AUDIO_FORMATS else 0
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

    def _browse_download(self):
        path = QFileDialog.getExistingDirectory(self, t("dialog_select_folder"))
        if path:
            self._download_edit.setText(path)

    def _browse_cookies(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("label_cookies_file"), "",
            f"{t('filetype_text')} (*.txt);;{t('filetype_all')} (*.*)",
        )
        if path:
            self._cookies_edit.setText(path)

    def _save(self):
        lang_idx = self._lang_display.index(self._lang_combo.currentText())
        new_lang = AVAILABLE_LANGUAGES[lang_idx]

        self._settings.download_path = self._download_edit.text().strip()
        self._settings.language = new_lang
        self._settings.video_resolution = (
            self._res_combo.currentText().removesuffix("p")
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
            self._settings.mp3_bitrate = (
                self._bitrate_combo.currentText().removesuffix("kbps")
            )

        if self._radio_file.isChecked():
            self._settings.cookies_path = self._cookies_edit.text().strip()
            self._settings.cookies_browser = ""
        elif self._radio_browser.isChecked():
            disp = self._browser_combo.currentText()
            if disp in _BROWSER_DISPLAY:
                self._settings.cookies_browser = (
                    _BROWSER_INTERNAL[_BROWSER_DISPLAY.index(disp)]
                )
            else:
                self._settings.cookies_browser = ""
            self._settings.cookies_path = ""
        else:
            self._settings.cookies_path = ""
            self._settings.cookies_browser = ""

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
