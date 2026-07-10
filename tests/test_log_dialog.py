"""`LogDialog` の表示往復を検証する。

ログエントリの読み込み（`load`）と追記（`append`）が表示テキストへ反映される
ことを、ヘッドレス（offscreen）で固定する。

対応 spec: [ログダイアログ](../docs/spec/screens/log-dialog.md)。
対応 arch: [log_dialog.py](../docs/arch/log_dialog.md)。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from yt_gui.log_dialog import LogDialog

pytestmark = pytest.mark.qt


def _make_log_dialog(qtbot) -> LogDialog:
    dialog = LogDialog(None)
    qtbot.addWidget(dialog)
    return dialog


def test_load_renders_all_entries(qtbot):
    """`load` で渡した全エントリが表示テキストに現れる。"""
    dialog = _make_log_dialog(qtbot)

    dialog.load(["1行目", "2行目"])

    text = dialog._text.toPlainText()
    assert "1行目" in text
    assert "2行目" in text


def test_append_adds_line_to_existing(qtbot):
    """`append` は既存表示を保ったまま 1 行追記する。"""
    dialog = _make_log_dialog(qtbot)
    dialog.load(["既存行"])

    dialog.append("追記行")

    text = dialog._text.toPlainText()
    assert "既存行" in text
    assert "追記行" in text
