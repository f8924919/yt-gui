"""`SettingsDialog` のタブレイアウトとモーダル経路の振る舞いを検証する。

ダウンロードタブは `QGridLayout` に行を積み上げる構造で、項目追加時の
行インデックスずれでウィジェットが重なる崩れが起きやすい（#108 で実際に発生）。
グリッドのセル衝突が無いことを回帰テストとして固定する。

加えて、モーダル `QMessageBox.question` / 検証警告を通る経路（アーカイブ削除確認・
保存時の検証分岐）を手段B（テスト方針 §2.5）で「操作→状態反映」まで検証する（#132）。

対応 spec: [設定ダイアログ](../docs/spec/screens/settings-dialog.md)。
対応 arch: [settings_dialog.py](../docs/arch/settings_dialog.md)。
"""

import os
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QGridLayout

from yt_gui.settings import Settings
from yt_gui.settings_dialog import SettingsDialog

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
        pos = layout.getItemPosition(idx)
        assert isinstance(pos, tuple)  # PySide6 スタブは object を返す型のため絞り込む
        r, c, rs, cs = pos
        for dr in range(rs):
            for dc in range(cs):
                cells.append((r + dr, c + dc))
    return cells


def _grid_row(grid: QGridLayout, index: int) -> int:
    """`getItemPosition` の行番号を返す（スタブは object 型なので絞り込む）。"""
    pos = grid.getItemPosition(index)
    assert isinstance(pos, tuple)
    return int(pos[0])


def _grid_item_widget(grid: QGridLayout, index: int):
    """グリッド `index` のアイテムが保持するウィジェットを返す。"""
    item = grid.itemAt(index)
    assert item is not None
    return item.widget()


def _download_tab_grid(dialog: SettingsDialog) -> QGridLayout:
    tabs = dialog._tabs
    assert tabs is not None
    for i in range(tabs.count()):
        page = tabs.widget(i)
        assert page is not None
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
    note_row = _grid_row(grid, grid.indexOf(note))
    check_row = _grid_row(grid, grid.indexOf(dialog._archive_check))

    # 注記はアーカイブ有効化チェックより下にあり、かつグリッド最下段にある
    assert note_row > check_row
    other_rows = [
        _grid_row(grid, idx)
        for idx in range(grid.count())
        if _grid_item_widget(grid, idx) is not note
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

    def _inform(*a, **kw):
        informed.append(a)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", _inform)

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

    def _warn(*a, **kw):
        warned.append(a)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)

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


# ── ファイル選択（_browse_* / 手段A: QFileDialog 静的メソッド固定） ────────────


def test_browse_download_sets_field(qtbot, monkeypatch):
    """フォルダ選択で得たパスをダウンロード先フィールドへ反映する。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **kw: "/picked/dir"
    )

    dialog._browse_download()

    assert dialog._download_edit.text() == "/picked/dir"


def test_browse_download_keeps_field_on_cancel(qtbot, monkeypatch):
    """選択をキャンセル（空文字）した場合はフィールドを変更しない。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    dialog._download_edit.setText("/orig")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: "")

    dialog._browse_download()

    assert dialog._download_edit.text() == "/orig"


def test_browse_cookies_sets_field(qtbot, monkeypatch):
    """Cookies ファイル選択で得たパスを Cookies フィールドへ反映する。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **kw: ("/picked/cookies.txt", "")
    )

    dialog._browse_cookies()

    assert dialog._cookies_edit.text() == "/picked/cookies.txt"


def test_browse_cookies_keeps_field_on_cancel(qtbot, monkeypatch):
    """Cookies 選択をキャンセルした場合はフィールドを変更しない。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    dialog._cookies_edit.setText("/orig/cookies.txt")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **kw: ("", ""))

    dialog._browse_cookies()

    assert dialog._cookies_edit.text() == "/orig/cookies.txt"


def test_browse_archive_sets_field(qtbot, monkeypatch):
    """アーカイブ保存先選択で得たパスをアーカイブパスフィールドへ反映する。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **kw: ("/picked/archive.txt", "")
    )

    dialog._browse_archive()

    assert dialog._archive_path_edit.text() == "/picked/archive.txt"


def test_browse_archive_keeps_field_on_cancel(qtbot, monkeypatch):
    """アーカイブ保存先選択をキャンセルした場合はフィールドを変更しない。"""
    from PySide6.QtWidgets import QFileDialog

    dialog = _make_dialog(qtbot, Settings())
    dialog._archive_path_edit.setText("/orig/archive.txt")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: ("", ""))

    dialog._browse_archive()

    assert dialog._archive_path_edit.text() == "/orig/archive.txt"


# ── アーカイブ有効化トグル（_on_archive_toggled） ─────────────────────────────


def test_archive_toggle_enables_and_disables_controls(qtbot):
    """アーカイブ有効化チェックに応じてパス入力・参照・クリアボタンが連動する。"""
    dialog = _make_dialog(qtbot, Settings(download_archive_enabled=False))

    dialog._archive_check.setChecked(True)
    assert dialog._archive_path_edit.isEnabled()
    assert dialog._archive_browse_btn.isEnabled()
    assert dialog._archive_clear_btn.isEnabled()

    dialog._archive_check.setChecked(False)
    assert not dialog._archive_path_edit.isEnabled()
    assert not dialog._archive_browse_btn.isEnabled()
    assert not dialog._archive_clear_btn.isEnabled()


# ── ブラウザ拡張連携タブ ────────────────────────────────────────────────────
# 対応 spec: docs/spec/features/browser-extension.md


def test_extension_enable_autogenerates_token(qtbot):
    """有効化時にトークンが空なら自動生成される。"""
    dialog = _make_dialog(qtbot, Settings())
    assert dialog._extension_token_edit.text() == ""
    dialog._extension_check.setChecked(True)
    assert dialog._extension_token_edit.text() != ""


def test_extension_regenerate_changes_token(qtbot):
    dialog = _make_dialog(
        qtbot, Settings(extension_enabled=True, extension_token="old")
    )
    dialog._regenerate_extension_token()
    assert dialog._extension_token_edit.text() != "old"
    assert dialog._extension_token_edit.text() != ""


def test_extension_inputs_disabled_when_off(qtbot):
    dialog = _make_dialog(qtbot, Settings(extension_enabled=False))
    assert dialog._extension_port_spin.isEnabled() is False
    assert dialog._extension_token_edit.isEnabled() is False


def test_save_persists_extension_settings(qtbot):
    dialog, manager = _make_dialog_with_manager(qtbot, Settings())
    dialog._extension_check.setChecked(True)
    dialog._extension_port_spin.setValue(8719)

    dialog._save()

    saved = manager.save.call_args[0][0]
    assert saved.extension_enabled is True
    assert saved.extension_port == 8719
    assert saved.extension_token != ""  # 有効時はトークンが入る


# ── サイドバー型ナビゲーション（#157） ──────────────────────────────


def test_settings_uses_sidebar_navigation_not_tabwidget(qtbot):
    """設定画面は上部横並びタブ（QTabWidget）ではなくサイドバー型で構成する。"""
    from PySide6.QtWidgets import QListWidget, QStackedWidget, QTabWidget

    dialog = _make_dialog(qtbot, Settings())

    # macOS でタブが窮屈になる根因の QTabWidget は使わない
    assert dialog.findChild(QTabWidget) is None
    # 左ナビ（QListWidget）＋ 右ページ（QStackedWidget）で構成する
    assert dialog.findChild(QListWidget) is not None
    assert dialog.findChild(QStackedWidget) is not None


def test_sidebar_has_seven_pages_with_locale_labels(qtbot):
    """7 ページが定義順に並び、ナビ項目ラベルがロケール文言と一致する。"""
    from PySide6.QtWidgets import QListWidget, QStackedWidget

    from yt_gui.i18n import t

    dialog = _make_dialog(qtbot, Settings())

    expected_labels = [
        t("tab_general"),
        t("tab_quality"),
        t("tab_output_template"),
        t("tab_download"),
        t("tab_sponsorblock"),
        t("tab_proxy"),
        t("tab_extension"),
    ]

    nav = dialog.findChild(QListWidget)
    stack = dialog.findChild(QStackedWidget)
    assert nav is not None and stack is not None
    assert dialog._tabs.count() == 7
    assert nav.count() == 7
    assert stack.count() == 7
    assert [nav.item(i).text() for i in range(nav.count())] == expected_labels


def test_sidebar_selection_switches_page(qtbot):
    """ナビ項目の選択で右ページが対応するインデックスへ切り替わる。"""
    from PySide6.QtWidgets import QListWidget, QStackedWidget

    dialog = _make_dialog(qtbot, Settings())
    nav = dialog.findChild(QListWidget)
    stack = dialog.findChild(QStackedWidget)
    assert nav is not None and stack is not None

    nav.setCurrentRow(dialog._proxy_tab_index)

    assert stack.currentIndex() == dialog._proxy_tab_index
    assert dialog._tabs.currentIndex() == dialog._proxy_tab_index


def test_set_current_index_syncs_nav_and_page(qtbot):
    """`_tabs.setCurrentIndex` がナビ選択行と表示ページの両方を同期する。"""
    from PySide6.QtWidgets import QListWidget, QStackedWidget

    dialog = _make_dialog(qtbot, Settings())
    nav = dialog.findChild(QListWidget)
    stack = dialog.findChild(QStackedWidget)
    assert nav is not None and stack is not None

    dialog._tabs.setCurrentIndex(dialog._template_tab_index)

    assert nav.currentRow() == dialog._template_tab_index
    assert stack.currentIndex() == dialog._template_tab_index


def test_dialog_widened_for_sidebar(qtbot):
    """サイドバー分だけ横幅を広げた固定サイズ（700×520）にする。"""
    dialog = _make_dialog(qtbot, Settings())

    assert dialog.minimumWidth() == 700
    assert dialog.maximumWidth() == 700
    assert dialog.minimumHeight() == 520
    assert dialog.maximumHeight() == 520
