import os

import pytest

from yt_gui import i18n

# ヘッドレス環境で Qt がウィンドウシステムを要求しないモードに固定する。
# 既に外部（CI の env など）で設定済みなら尊重する。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _restore_language():
    original = i18n._current_lang
    yield
    i18n._current_lang = original


@pytest.fixture(autouse=True)
def _silence_qt_modal_dialogs(request, monkeypatch):
    """`qt` マーカー付きテストで、モーダル `QMessageBox` を no-op 化する。

    offscreen プラットフォームでは `QMessageBox.warning/critical/information/question`
    をモーダル表示するとダイアログが返らずプロセスごとハングするため。
    Qt 非依存テストでは early return し、PySide6 を import しない。
    """
    if request.node.get_closest_marker("qt") is None:
        return
    from PySide6.QtWidgets import QMessageBox

    ok = QMessageBox.StandardButton.Ok
    for name in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **kw: ok)
