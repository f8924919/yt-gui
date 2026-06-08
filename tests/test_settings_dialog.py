"""`SettingsDialog` のタブレイアウトを検証する。

特にダウンロードタブは `QGridLayout` に行を積み上げる構造で、項目追加時の
行インデックスずれでウィジェットが重なる崩れが起きやすい（#108 で実際に発生）。
グリッドのセル衝突が無いことを回帰テストとして固定する。

対応 spec: [設定ダイアログ](../docs/spec/screens/settings-dialog.md)。
対応 arch: [settings_dialog.py](../docs/arch/settings_dialog.md)。
"""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QGridLayout  # noqa: E402

from yt_gui.settings import Settings  # noqa: E402
from yt_gui.settings_dialog import SettingsDialog  # noqa: E402

pytestmark = pytest.mark.qt


def _make_dialog(qtbot, settings: Settings) -> SettingsDialog:
    manager = MagicMock()
    manager.load.return_value = settings
    dialog = SettingsDialog(None, manager)
    qtbot.addWidget(dialog)
    return dialog


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
