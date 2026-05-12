from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .i18n import t


class LogDialog(QDialog):
    def __init__(self, parent=None, on_close=None):
        super().__init__(parent)
        self.setWindowTitle(t("log_dialog_title"))
        self.resize(640, 420)
        self.setMinimumSize(400, 200)
        self._on_close_cb = on_close

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Courier New", 9))
        palette = self._text.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
        self._text.setPalette(palette)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._text)

        btn_layout = QHBoxLayout()
        btn_clear = QPushButton(t("btn_clear_log"))
        btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_close = QPushButton(t("btn_close"))
        btn_close.clicked.connect(self._on_close)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def load(self, entries: list[str]):
        self._text.setPlainText("\n".join(entries) + ("\n" if entries else ""))
        self._text.verticalScrollBar().setValue(self._text.verticalScrollBar().maximum())

    def append(self, text: str):
        sb = self._text.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum()
        self._text.appendPlainText(text)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _clear(self):
        self._text.clear()

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.close()

    def closeEvent(self, event):
        if self._on_close_cb:
            self._on_close_cb()
        super().closeEvent(event)
