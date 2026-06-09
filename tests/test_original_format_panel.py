"""`_AudioListWidget` の音声トラック選択の排他ロジックを検証する。

対応 spec: [排他ロジック](../docs/spec/screens/original-format-panel.md) 節。
対応 arch: [_AudioListWidget](../docs/arch/original_format_panel.md)。
"""

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QAbstractItemView  # noqa: E402

from yt_gui.original_format_panel import (  # noqa: E402
    _AUTO_SENTINEL,
    _SKIP_SENTINEL,
    _AudioListWidget,
    OriginalFormatPanel,
)

pytestmark = pytest.mark.qt

# 物理行: 0=AUTO, 1=SKIP, 2.. = 音声 ID
_AUDIO_ENTRIES = [("opus (webm) [251]", "251"), ("aac (m4a) [140]", "140")]
_ROW_OPUS = 2
_ROW_AAC = 3


@pytest.fixture
def audio_list(qtbot):
    """パネル本体 (original_format_panel.py) と同じ初期化手順で構築する。"""
    widget = _AudioListWidget()
    widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    qtbot.addWidget(widget)
    widget.set_normal_mode("自動", "ダウンロードしない", _AUDIO_ENTRIES)
    return widget


def test_set_normal_mode_attaches_sentinels_and_format_ids(audio_list):
    from PySide6.QtCore import Qt

    role = Qt.ItemDataRole.UserRole
    assert audio_list.item(_AudioListWidget.AUTO_ROW).data(role) == _AUTO_SENTINEL
    assert audio_list.item(_AudioListWidget.SKIP_ROW).data(role) == _SKIP_SENTINEL
    assert audio_list.item(_ROW_OPUS).data(role) == "251"
    assert audio_list.item(_ROW_AAC).data(role) == "140"


def test_select_auto_selects_only_auto(audio_list):
    audio_list.select_audio_rows([_ROW_OPUS, _ROW_AAC])
    audio_list.select_auto()
    assert audio_list.get_selection() == (True, False, [])


def test_select_skip_selects_only_skip(audio_list):
    audio_list.select_audio_rows([_ROW_OPUS])
    audio_list.select_skip()
    assert audio_list.get_selection() == (False, True, [])


def test_select_audio_rows_clears_meta_rows(audio_list):
    audio_list.select_auto()
    audio_list.select_audio_rows([_ROW_OPUS, _ROW_AAC])
    assert audio_list.get_selection() == (False, False, [_ROW_OPUS, _ROW_AAC])


def test_enforce_exclusivity_drops_auto_when_audio_added(audio_list):
    """「自動」選択中に音声 ID を追加選択すると「自動」が解除される。"""
    audio_list.select_auto()
    audio_list.item(_ROW_OPUS).setSelected(True)
    assert audio_list.get_selection() == (False, False, [_ROW_OPUS])


def test_enforce_exclusivity_drops_skip_when_audio_added(audio_list):
    """「ダウンロードしない」選択中に音声 ID を追加選択すると skip が解除される。"""
    audio_list.select_skip()
    audio_list.item(_ROW_AAC).setSelected(True)
    assert audio_list.get_selection() == (False, False, [_ROW_AAC])


# ── 出力形式ラジオ: H.264 MP4 再変換（互換性優先） ──────────────────────────


@pytest.fixture
def panel(qtbot, tmp_path):
    from yt_gui.downloader import Downloader

    widget = OriginalFormatPanel(
        downloader=Downloader(output_dir=str(tmp_path)),
        get_url=lambda: "",
        get_cookies=lambda: (None, None),
        update_status=lambda msg, pct: None,
    )
    qtbot.addWidget(widget)
    return widget


def test_recode_radio_default_off(panel):
    """既定は「結合」で、再変換は OFF。"""
    assert panel.get_recode_video() is False
    assert panel.get_remux_only() is False
    assert panel.get_audio_only() is False


def test_recode_radio_exclusive_and_thumbnail_enabled(panel):
    """再変換を選ぶと他モードは OFF、サムネ埋め込みは有効（出力 mp4 のため）。"""
    panel._radio_recode.setChecked(True)
    assert panel.get_recode_video() is True
    assert panel.get_remux_only() is False
    assert panel.get_audio_only() is False
    assert panel._embed_thumbnail_check.isEnabled() is True


def test_recode_raw_settings_round_trip(panel):
    """get_raw_settings ↔ restore_from_settings で再変換フラグが往復する。"""
    panel._radio_recode.setChecked(True)
    settings = panel.get_raw_settings()
    assert settings["recode_video"] is True

    panel._radio_mp4.setChecked(True)
    assert panel.get_recode_video() is False

    panel.restore_from_settings(settings)
    assert panel.get_recode_video() is True
    assert panel._radio_recode.isChecked() is True
