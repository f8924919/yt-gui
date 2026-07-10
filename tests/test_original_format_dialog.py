"""`OriginalFormatDialog` の起動モード・検証・シグナル中継を検証する。

モーダル `QDialog.exec` は offscreen でヘッドレス駆動できないため、
`exec` を回さずに「主ボタン押下相当 (`_on_primary_clicked`) → シグナル emit /
検証分岐」を検証する。検証は内包パネルの公開 API を読むだけなので、
パネルメソッドを monkeypatch して各分岐を駆動する。

対応 spec: [オリジナル形式ダイアログ](../docs/spec/screens/original-format-dialog.md)。
対応 arch: [original_format_dialog.py](../docs/arch/original_format_dialog.md)。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QDialog

from yt_gui import i18n
from yt_gui.downloader import Downloader
from yt_gui.original_format_dialog import OriginalFormatDialog

pytestmark = pytest.mark.qt


def _make_dialog(qtbot, *, mode="add", restore_settings=None):
    dialog = OriginalFormatDialog(
        downloader=Downloader(),
        get_url=lambda: "https://example.com/watch?v=abc",
        get_cookies=lambda: (None, None),
        update_status=lambda text, pct: None,
        video_container="mp4",
        audio_label="MP3 192kbps",
        mode=mode,
        restore_settings=restore_settings,
    )
    qtbot.addWidget(dialog)
    return dialog


def test_add_mode_uses_add_to_queue_label(qtbot):
    i18n.set_language("ja")
    dialog = _make_dialog(qtbot, mode="add")
    assert dialog._primary_button.text() == i18n.t("btn_add_to_queue")


def test_edit_mode_uses_apply_edit_label(qtbot):
    i18n.set_language("ja")
    dialog = _make_dialog(qtbot, mode="edit")
    assert dialog._primary_button.text() == i18n.t("btn_apply_edit")


def test_default_add_state_is_valid(qtbot):
    """取得前のデフォルト状態（映像/音声とも自動・結合モード）は検証を通る。"""
    dialog = _make_dialog(qtbot, mode="add")
    assert dialog._validate() is None


def test_validate_rejects_skip_both(qtbot, monkeypatch):
    dialog = _make_dialog(qtbot, mode="add")
    monkeypatch.setattr(dialog.panel, "get_audio_only", lambda: False)
    monkeypatch.setattr(dialog.panel, "is_both_skipped", lambda: True)
    assert dialog._validate() == "warn_skip_both"


def test_validate_rejects_skip_audio_only(qtbot, monkeypatch):
    dialog = _make_dialog(qtbot, mode="add")
    monkeypatch.setattr(dialog.panel, "get_audio_only", lambda: True)
    monkeypatch.setattr(dialog.panel, "is_audio_skipped", lambda: True)
    assert dialog._validate() == "warn_skip_audio_only"


def test_validate_edit_requires_formats_loaded(qtbot):
    """編集モードはフォーマット未取得だと検証で弾く（追加モードは許容）。"""
    dialog = _make_dialog(qtbot, mode="edit")
    assert dialog._validate() == "warn_edit_formats_not_loaded"


def test_primary_click_emits_add_requested_and_accepts(qtbot):
    dialog = _make_dialog(qtbot, mode="add")
    fired = []
    dialog.add_requested.connect(lambda: fired.append(True))

    dialog._on_primary_clicked()

    assert fired == [True]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_primary_click_invalid_does_not_emit_or_accept(qtbot, monkeypatch):
    dialog = _make_dialog(qtbot, mode="add")
    monkeypatch.setattr(dialog.panel, "get_audio_only", lambda: True)
    monkeypatch.setattr(dialog.panel, "is_audio_skipped", lambda: True)
    fired = []
    dialog.add_requested.connect(lambda: fired.append(True))

    dialog._on_primary_clicked()

    assert fired == []
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_primary_emits_edit_applied(qtbot, monkeypatch):
    dialog = _make_dialog(qtbot, mode="edit")
    monkeypatch.setattr(dialog.panel, "has_formats_loaded", lambda: True)
    applied, added = [], []
    dialog.edit_applied.connect(lambda: applied.append(True))
    dialog.add_requested.connect(lambda: added.append(True))

    dialog._on_primary_clicked()

    assert applied == [True]
    assert added == []


def test_reject_emits_edit_cancelled_in_edit_mode(qtbot):
    dialog = _make_dialog(qtbot, mode="edit")
    cancelled = []
    dialog.edit_cancelled.connect(lambda: cancelled.append(True))

    dialog.reject()

    assert cancelled == [True]


def test_reject_does_not_emit_edit_cancelled_in_add_mode(qtbot):
    dialog = _make_dialog(qtbot, mode="add")
    cancelled = []
    dialog.edit_cancelled.connect(lambda: cancelled.append(True))

    dialog.reject()

    assert cancelled == []
