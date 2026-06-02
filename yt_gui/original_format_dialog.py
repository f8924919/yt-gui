"""オリジナル形式の詳細設定を行うモーダルダイアログ。

`OriginalFormatPanel` をコンポジションで内包し、ダイアログ自身は起動・ボタン・
シグナル中継のみを担う薄いシェル。フォーマット文字列生成・排他制御・スナップ
ショット等のロジックはパネル側に残す。

対応 spec: docs/spec/screens/original-format-dialog.md
対応 arch: docs/arch/original_format_dialog.md
"""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .downloader import Downloader
from .i18n import t
from .original_format_panel import OriginalFormatPanel


class OriginalFormatDialog(QDialog):
    """「オリジナルの形式」の詳細設定ダイアログ。

    開くたびに生成・破棄する使い捨て運用を前提とし、生存インスタンスへの
    再翻訳配線は持たない（生成時点の言語・コンテナ設定で組み立てる）。
    """

    add_requested = Signal()
    edit_applied = Signal()
    edit_cancelled = Signal()

    def __init__(
        self,
        parent=None,
        *,
        downloader: Downloader,
        get_url: Callable[[], str],
        get_cookies: Callable[[], tuple[str | None, str | None]],
        update_status: Callable[[str, float], None],
        video_container: str = "mp4",
        audio_label: str | None = None,
        mode: str = "add",
        restore_settings: dict | None = None,
    ):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle(t("label_original_detail"))
        self.setModal(True)

        layout = QVBoxLayout(self)

        # 対象 URL を読み取り専用で表示（どの動画への設定かを明示）
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(t("label_url")))
        url_field = QLineEdit(get_url())
        url_field.setReadOnly(True)
        url_row.addWidget(url_field, 1)
        layout.addLayout(url_row)

        self._panel = OriginalFormatPanel(
            self,
            downloader=downloader,
            get_url=get_url,
            get_cookies=get_cookies,
            update_status=update_status,
        )
        self._panel.retranslate(video_container, audio_label)
        self._panel.on_size_hint_changed(self._on_panel_size_hint_changed)
        layout.addWidget(self._panel)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_button = QPushButton(t("btn_cancel_edit"))
        self._cancel_button.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_button)
        primary_label = t("btn_apply_edit") if mode == "edit" else t("btn_add_to_queue")
        self._primary_button = QPushButton(primary_label)
        self._primary_button.clicked.connect(self._on_primary_clicked)
        btn_row.addWidget(self._primary_button)
        layout.addLayout(btn_row)

        # 編集モードは前回設定を復元してからフォーマットを取得する
        if mode == "edit" and restore_settings is not None:
            self._panel.restore_from_settings(restore_settings)
            self._panel.trigger_fetch()

    @property
    def panel(self) -> OriginalFormatPanel:
        return self._panel

    def _on_panel_size_hint_changed(self) -> None:
        """内包パネルの sizeHint 変化（ニコ動コメントグループ出現等）に追従する。"""
        self.adjustSize()

    def _validate(self) -> str | None:
        """検証 NG なら警告キーを、OK なら None を返す。"""
        panel = self._panel
        if self._mode == "edit" and not panel.has_formats_loaded():
            return "warn_edit_formats_not_loaded"
        audio_only = panel.get_audio_only()
        if audio_only and panel.is_audio_skipped():
            return "warn_skip_audio_only"
        if not audio_only and panel.is_both_skipped():
            return "warn_skip_both"
        return None

    def _on_primary_clicked(self) -> None:
        err = self._validate()
        if err is not None:
            QMessageBox.warning(self, t("warn_title"), t(err))
            return
        if self._mode == "edit":
            self.edit_applied.emit()
        else:
            self.add_requested.emit()
        self.accept()

    def reject(self) -> None:  # noqa: D401 - QDialog override
        if self._mode == "edit":
            self.edit_cancelled.emit()
        super().reject()
