"""`SettingsDialog` のタブレイアウトとモーダル経路の振る舞いを検証する。

ダウンロードタブは `QGridLayout` に行を積み上げる構造で、項目追加時の
行インデックスずれでウィジェットが重なる崩れが起きやすい（#108 で実際に発生）。
グリッドのセル衝突が無いことを回帰テストとして固定する。

加えて、モーダル `QMessageBox.question` / 検証警告を通る経路（アーカイブ削除確認・
保存時の検証分岐）を手段B（テスト方針 §2.5）で「操作→状態反映」まで検証する（#132）。

対応 spec: [設定ダイアログ](../docs/spec/screens/settings-dialog.md)。
対応 arch: [settings_dialog.py](../docs/arch/settings_dialog.md)。
"""

import os  # noqa: E402
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QGridLayout  # noqa: E402

from yt_gui.settings import Settings  # noqa: E402
from yt_gui.settings_dialog import SettingsDialog  # noqa: E402

pytestmark = pytest.mark.qt


def _make_dialog(qtbot, settings: Settings) -> SettingsDialog:
    return _make_dialog_with_manager(qtbot, settings)[0]


def _make_dialog_with_manager(
    qtbot, settings: Settings
) -> tuple[SettingsDialog, MagicMock]:
    manager = MagicMock()
    manager.load.return_value = settings
    dialog = SettingsDialog(None, manager)
    qtbot.addWidget(dialog)
    return dialog, manager


def _grid_cells(layout: QGridLayout) -> list[tuple[int, int]]:
    """レイアウト内の各アイテムが占有する (row, col) セルを列挙する。

    行・列スパンを展開し、同一セルを複数アイテムが占有していないか調べられる形にする。
    """
    cells: list[tuple[int, int]] = []
    for idx in range(layout.count()):
        r, c, rs, cs = layout.getItemPosition(idx)
        for dr in range(rs):
            for dc in range(cs):
                cells.append((r + dr, c + dc))
    return cells


def _download_tab_grid(dialog: SettingsDialog) -> QGridLayout:
    from PySide6.QtWidgets import QTabWidget

    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    for i in range(tabs.count()):
        page = tabs.widget(i)
        layout = page.layout()
        # ダウンロードタブは「同時ダウンロード数」スピンボックスを持つ
        if isinstance(layout, QGridLayout) and hasattr(dialog, "_max_concurrent_spin"):
            if layout.indexOf(dialog._max_concurrent_spin) != -1:
                return layout
    raise AssertionError("download tab grid not found")


@pytest.mark.parametrize("archive_enabled", [False, True])
def test_download_tab_has_no_overlapping_grid_cells(qtbot, archive_enabled):
    """ダウンロードタブのグリッドで同一セルを複数ウィジェットが占有しないこと。"""
    dialog = _make_dialog(qtbot, Settings(download_archive_enabled=archive_enabled))
    grid = _download_tab_grid(dialog)
    cells = _grid_cells(grid)
    assert len(cells) == len(set(cells)), "グリッドセルの重複（レイアウト崩れ）がある"


def test_download_tab_archive_note_at_bottom(qtbot):
    """アーカイブ注記がアーカイブ各行より下（最下段）にあること（#108 回帰）。

    行ずれで注記が「Archive file」行などと重なる崩れを固定する。
    """
    from PySide6.QtWidgets import QLabel

    from yt_gui import i18n

    dialog = _make_dialog(qtbot, Settings(download_archive_enabled=True))
    grid = _download_tab_grid(dialog)

    note_text = i18n.t("download_archive_note")
    note = next(
        w
        for w in dialog.findChildren(QLabel)
        if w.text() == note_text and grid.indexOf(w) != -1
    )
    note_row = grid.getItemPosition(grid.indexOf(note))[0]
    check_row = grid.getItemPosition(grid.indexOf(dialog._archive_check))[0]

    # 注記はアーカイブ有効化チェックより下にあり、かつグリッド最下段にある
    assert note_row > check_row
    other_rows = [
        grid.getItemPosition(idx)[0]
        for idx in range(grid.count())
        if grid.itemAt(idx).widget() is not note
    ]
    assert note_row >= max(other_rows), "注記が最下段になく、重なりの疑いがある"


def test_max_concurrent_spin_reflects_and_saves(qtbot):
    """同時ダウンロード数スピンボックスが設定値を反映し範囲内に収まること。"""
    dialog = _make_dialog(qtbot, Settings(max_concurrent_downloads=4))
    assert dialog._max_concurrent_spin.value() == 4
    assert dialog._max_concurrent_spin.minimum() == 1
    assert dialog._max_concurrent_spin.maximum() == 5


# ── アーカイブ削除確認（_clear_archive / 手段B: question 分岐） ────────────────


def _enable_archive(dialog, path, lines: int) -> None:
    """`path` に `lines` 件のアーカイブを作り、ダイアログを有効状態にする。"""
    path.write_text("".join(f"youtube id{i}\n" for i in range(lines)), encoding="utf-8")
    dialog._archive_check.setChecked(True)
    dialog._archive_path_edit.setText(str(path))


def test_clear_archive_yes_removes_file(qtbot, tmp_path, monkeypatch):
    """削除確認で Yes を選ぶとファイル削除・件数 0 更新・完了通知まで行う。"""
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    dialog = _make_dialog(qtbot, Settings())
    archive = tmp_path / "download_archive.txt"
    _enable_archive(dialog, archive, lines=3)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes
    )
    informed: list = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **kw: informed.append(a) or QMessageBox.StandardButton.Ok,
    )

    dialog._clear_archive()

    assert not archive.exists()
    assert dialog._archive_count_label.text() == t("download_archive_count").format(
        count=0
    )
    assert informed  # 完了通知（information）が発火する


def test_clear_archive_no_keeps_file(qtbot, tmp_path, monkeypatch):
    """削除確認で No（Yes 以外）を選ぶとファイルを残す。"""
    from PySide6.QtWidgets import QMessageBox

    dialog = _make_dialog(qtbot, Settings())
    archive = tmp_path / "download_archive.txt"
    _enable_archive(dialog, archive, lines=3)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.No
    )

    dialog._clear_archive()

    assert archive.exists()


def test_clear_archive_failure_warns(qtbot, tmp_path, monkeypatch):
    """削除に失敗した場合は警告を出し、ファイルは残る。"""
    from PySide6.QtWidgets import QMessageBox

    dialog = _make_dialog(qtbot, Settings())
    archive = tmp_path / "download_archive.txt"
    _enable_archive(dialog, archive, lines=3)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes
    )
    warned: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **kw: warned.append(a) or QMessageBox.StandardButton.Ok,
    )

    def _raise(_path):
        raise OSError("permission denied")

    monkeypatch.setattr(os, "remove", _raise)

    dialog._clear_archive()

    assert warned
    assert archive.exists()


# ── 保存時の検証分岐（_save / 手段B: warning + タブ切り替え） ──────────────────


def test_save_rejects_invalid_template_and_switches_tab(qtbot):
    """不正なファイル名テンプレートは保存せずファイル名タブへ切り替える。"""
    dialog, manager = _make_dialog_with_manager(qtbot, Settings())
    dialog._video_template_edit.setText("no_ext_placeholder")  # %(ext)s 欠落で不正

    dialog._save()

    manager.save.assert_not_called()
    assert dialog._tabs.currentIndex() == dialog._template_tab_index


def test_save_rejects_empty_proxy_host_and_switches_tab(qtbot):
    """プロキシ有効かつホスト未入力は保存せずプロキシタブへ切り替える。"""
    dialog, manager = _make_dialog_with_manager(qtbot, Settings())
    dialog._proxy_check.setChecked(True)
    dialog._proxy_host_edit.setText("")

    dialog._save()

    manager.save.assert_not_called()
    assert dialog._tabs.currentIndex() == dialog._proxy_tab_index


def test_save_rejects_out_of_range_proxy_port_and_switches_tab(qtbot):
    """プロキシ有効かつポートが範囲外（>65535）は保存せずプロキシタブへ切り替える。"""
    dialog, manager = _make_dialog_with_manager(qtbot, Settings())
    dialog._proxy_check.setChecked(True)
    dialog._proxy_host_edit.setText("proxy.local")
    dialog._proxy_port_edit.setText("70000")

    dialog._save()

    manager.save.assert_not_called()
    assert dialog._tabs.currentIndex() == dialog._proxy_tab_index


def test_save_persists_settings_when_valid(qtbot):
    """検証を通る入力では `SettingsManager.save` に変更が反映され accept される。"""
    from PySide6.QtWidgets import QDialog

    dialog, manager = _make_dialog_with_manager(qtbot, Settings())
    dialog._max_concurrent_spin.setValue(3)

    dialog._save()

    manager.save.assert_called_once()
    saved = manager.save.call_args[0][0]
    assert saved.max_concurrent_downloads == 3
    assert dialog.result() == QDialog.DialogCode.Accepted
