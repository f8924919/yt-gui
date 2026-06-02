"""`App` 周辺の UI ロジックを検証する。

- `_QueueTree._edit_targets`: 「形式を変更」(= `edit_format_requested`) の対象判定
  （対象が `waiting` のみ、かつ編集モード中でない）
- `_refresh_format_labels`: 言語変更に追従して `format_combo` を再構築する

`contextMenuEvent` 本体はモーダル `QMenu.exec`（offscreen でヘッドレス駆動不可）を
含むため、活性判定と発火判定で共用する純粋ヘルパ `_edit_targets` を検証対象とする。

対応 spec: [メインウィンドウ](../docs/spec/screens/main-window.md)。
対応 arch: [app.py](../docs/arch/app.md)。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from yt_gui import i18n  # noqa: E402
from yt_gui.app import App, _QueueTree  # noqa: E402
from yt_gui.job_spec import build_job_spec  # noqa: E402
from yt_gui.queue_controller import _QueueItem  # noqa: E402
from yt_gui.settings import Settings  # noqa: E402

pytestmark = pytest.mark.qt


def _make_item(status: str, url: str = "https://example.com/v") -> _QueueItem:
    item = _QueueItem(
        url=url,
        title="動画",
        format_label="MP4",
        job=build_job_spec("fmt_best_mp4", Settings()),
    )
    item.status = status
    return item


@pytest.fixture
def queue_tree(qtbot):
    """`_QueueTree` を単体構築する。`is_editing` は `state["editing"]` を返す。"""
    state = {"editing": False}
    tree = _QueueTree(
        get_item=lambda ti: None,
        get_thumbnail_b64=lambda url: None,
        is_editing=lambda: state["editing"],
    )
    qtbot.addWidget(tree)
    return tree, state


def test_edit_targets_returns_waiting_subset_when_not_editing(queue_tree):
    tree, state = queue_tree
    waiting = _make_item("waiting")
    downloading = _make_item("downloading")

    assert tree._edit_targets([waiting, downloading]) == [waiting]


def test_edit_targets_empty_while_editing(queue_tree):
    tree, state = queue_tree
    state["editing"] = True

    assert tree._edit_targets([_make_item("waiting")]) == []


def test_edit_targets_empty_when_no_waiting(queue_tree):
    tree, state = queue_tree

    assert tree._edit_targets([_make_item("downloading"), _make_item("done")]) == []


@pytest.fixture
def app(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from yt_gui.downloader import Downloader

    monkeypatch.setattr(Downloader, "missing_dependencies", lambda self: [])
    window = App()
    qtbot.addWidget(window)
    return window


def test_refresh_format_labels_follows_language(app):
    combo = app.format_combo

    i18n.set_language("ja")
    app._refresh_format_labels()
    ja_texts = [combo.itemText(i) for i in range(combo.count())]

    i18n.set_language("en")
    app._refresh_format_labels()
    en_texts = [combo.itemText(i) for i in range(combo.count())]

    assert en_texts == app._build_format_display()
    assert en_texts != ja_texts


def _select_format(app, key: str) -> None:
    from yt_gui.formats import FORMAT_KEYS

    app.format_combo.setCurrentIndex(FORMAT_KEYS.index(key))


def test_original_format_shows_detail_button_hides_add(app):
    """オリジナル形式選択時は「詳細設定...」を表示し「追加」を隠す。"""
    _select_format(app, "fmt_original")
    assert not app._detail_button.isHidden()
    assert app.add_button.isHidden()


def test_non_original_format_shows_add_button_hides_detail(app):
    _select_format(app, "fmt_original")
    _select_format(app, "fmt_best_mp4")
    assert not app.add_button.isHidden()
    assert app._detail_button.isHidden()


def test_window_height_fixed_across_format_change(app):
    """詳細設定を別画面に分離したため、形式変更で高さは変わらない。"""
    _select_format(app, "fmt_best_mp4")
    h_default = app.height()
    _select_format(app, "fmt_original")
    assert app.height() == h_default


def test_open_original_dialog_warns_on_empty_url(app, monkeypatch):
    """URL 未入力で詳細設定を開こうとすると警告し、ダイアログを生成しない。"""
    warned = []
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **kw: warned.append(a) or QMessageBox.StandardButton.Ok
    )
    app.url_entry.clear()

    dialog = app._open_original_dialog()

    assert dialog is None
    assert warned
