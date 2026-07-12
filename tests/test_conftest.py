"""`tests/conftest.py` の共有ヘルパを検証する。

- `flush_deferred_deletes`: `deleteLater()` で積まれた `DeferredDelete` イベントを
  イベントループを回さずに強制消化する（#246）。フレーク再発の有無ではなく、
  機構自体が実際に破棄を実行することを決定論的に検証する。

対応 docs: [テスト方針](../docs/testing/policy.md) §2.5「遅延破棄の決定論化」。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from tests.conftest import flush_deferred_deletes

pytestmark = pytest.mark.qt


def test_flush_deferred_deletes_destroys_pending_qobject(qapp):
    """`deleteLater()` 済みの QObject が flush で実際に破棄されること。"""
    obj = QObject()
    destroyed: list[bool] = []
    obj.destroyed.connect(lambda *a: destroyed.append(True))

    obj.deleteLater()
    assert not destroyed  # deleteLater 単独では破棄されない（イベント未消化）

    flush_deferred_deletes()

    assert destroyed


def test_flush_deferred_deletes_cascades_to_widget_children(qapp):
    """親ウィジェットの flush 破棄が子まで連鎖すること（テスト間リークの再現形）。"""
    parent = QWidget()
    child = QWidget(parent)
    destroyed: list[bool] = []
    child.destroyed.connect(lambda *a: destroyed.append(True))

    parent.deleteLater()
    assert not destroyed

    flush_deferred_deletes()

    assert destroyed


def test_flush_deferred_deletes_is_noop_without_pending(qapp):
    """消化対象がない状態で呼んでも例外なく完了すること（毎テスト実行の前提）。"""
    flush_deferred_deletes()
