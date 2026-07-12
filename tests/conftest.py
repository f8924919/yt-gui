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


def flush_deferred_deletes() -> None:
    """`deleteLater()` で積まれた `DeferredDelete` イベントを強制消化する（#246）。

    Qt は DeferredDelete を loop-level ガードで遅延させるため、`processEvents()`
    ではネストイベントループ（`exec()`）由来の遅延破棄が消化されないことがある。
    event_type を明示した `sendPostedEvents` はこのガードを迂回して即時 flush する。
    呼び出しは 1 回で足りる: 親の C++ デストラクタは子を同期削除し、削除済み
    オブジェクト宛の残イベントは `~QObject` が自動除去する（本コードベースに
    デストラクタ内 `deleteLater` は存在しない）。
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def _flush_qt_deferred_deletes(request):
    """`qt` マーカー付きテストの終了時に遅延破棄をテスト内で消化する（#246）。

    先行テストの `deleteLater()` 積み残しが後続テストのイベントループ処理中に
    実行されると、Python GC と C++ デストラクタ連鎖の順序次第で二重解放
    （SIGABRT）を起こしうるため、破棄イベントをテスト境界を越えて漏らさない。

    順序保証: pytest-qt はウィジェットの close / `deleteLater()` を
    `pytest_runtest_teardown` フック（`wrapper=True, trylast=True`。
    pytestqt/plugin.py の `_close_widgets` は `yield` より前）で行い、fixture
    finalizer 群はその `yield` 時点で実行される。したがって本フィクスチャの
    teardown（yield 以降）は必ず qtbot の close / `deleteLater()` の後に走る。

    適用範囲は `qt` マーカー付きテスト限定（Qt 非依存テストでは early return
    し、PySide6 を import しない）。DeferredDelete が積まれていなければ no-op。
    """
    if request.node.get_closest_marker("qt") is None:
        yield
        return
    yield
    flush_deferred_deletes()


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
