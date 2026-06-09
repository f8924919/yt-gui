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
from yt_gui.job_spec import PanelSnapshot, build_job_spec  # noqa: E402
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
    state = {"editing": False, "archive_enabled": False}
    tree = _QueueTree(
        get_item=lambda ti: None,
        get_thumbnail_b64=lambda url: None,
        is_editing=lambda: state["editing"],
        is_archive_enabled=lambda: state["archive_enabled"],
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
        QMessageBox,
        "warning",
        lambda *a, **kw: warned.append(a) or QMessageBox.StandardButton.Ok,
    )
    app.url_entry.clear()

    dialog = app._open_original_dialog()

    assert dialog is None
    assert warned


# ── 区間ダウンロード（download sections） ───────────────────────────────────


def _enable_section(app, start: str, end: str, force: bool = False) -> None:
    app._section_check.setChecked(True)
    app._section_start.setText(start)
    app._section_end.setText(end)
    app._section_keyframe_check.setChecked(force)


def test_section_inputs_hidden_until_enabled(app):
    assert app._section_inputs.isHidden()
    app._section_check.setChecked(True)
    assert not app._section_inputs.isHidden()
    app._section_check.setChecked(False)
    assert app._section_inputs.isHidden()


def test_read_section_none_when_disabled(app):
    app._section_check.setChecked(False)
    assert app._read_section() == (None, None, False)


def test_read_section_returns_values_when_enabled(app):
    _enable_section(app, "00:01:30", "00:04:00", force=True)
    assert app._read_section() == ("00:01:30", "00:04:00", True)


def test_validate_section_ok_when_disabled(app):
    app._section_check.setChecked(False)
    assert app._validate_section() is True


def test_validate_section_rejects_invalid_time(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warned.append(a[2]) or None
    )
    _enable_section(app, "abc", "00:04:00")
    assert app._validate_section() is False
    assert warned


def test_validate_section_rejects_start_after_end(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warned.append(a[2]) or None
    )
    _enable_section(app, "00:05:00", "00:04:00")
    assert app._validate_section() is False
    assert warned == [t("warn_section_range")]


def test_validate_section_ok_with_valid_range(app):
    _enable_section(app, "90", "4:00")
    assert app._validate_section() is True


def test_playlist_with_section_warns_and_aborts(app, monkeypatch):
    """取得後にプレイリストと判明し区間指定がある場合は警告して中断する。"""
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warned.append(a[2]) or None
    )
    calls = []
    monkeypatch.setattr(
        app.queue, "enqueue_playlist", lambda *a, **k: calls.append(a) or []
    )

    job = build_job_spec(
        "fmt_best_mp4", Settings(), section_start="10", section_end="20"
    )
    payload = {
        "result": {
            "type": "playlist",
            "entries": [{"id": "a"}],
            "title": "PL",
        },
        "job": job,
        "format_label": "MP4",
    }
    app._on_fetch_for_add_done(payload)

    assert warned == [t("warn_playlist_section")]
    assert calls == []  # enqueue されない


def test_restore_section_from_job_single_edit(app):
    job = build_job_spec(
        "fmt_best_mp4",
        Settings(),
        section_start="00:01:00",
        section_end="00:02:00",
        section_force_keyframes=True,
    )
    app._restore_section_from_job(job)
    assert app._section_check.isChecked() is True
    assert app._section_start.text() == "00:01:00"
    assert app._section_end.text() == "00:02:00"
    assert app._section_keyframe_check.isChecked() is True


def test_restore_section_clears_when_no_section(app):
    _enable_section(app, "10", "20")
    app._restore_section_from_job(build_job_spec("fmt_best_mp4", Settings()))
    assert app._section_check.isChecked() is False
    assert app._section_start.text() == ""
    assert app._section_inputs.isHidden()


# ── 複数音声 MKV 昇格通知 × 再エンコードの干渉 ─────────────────────────────


def _recode_panel(*, has_multiple_audio: bool) -> PanelSnapshot:
    return PanelSnapshot(
        format_spec="137+140+141",
        subtitle_opts=None,
        remux_only=False,
        audio_only=False,
        recode_video=True,
        embed_thumbnail=False,
        embed_metadata=True,
        embed_chapters=True,
        has_multiple_audio=has_multiple_audio,
        raw_settings={},
    )


def test_no_mkv_promotion_notice_for_recode_video(app):
    """再エンコード時は video_container=mp4 固定で MKV 昇格ではないため、
    複数音声でも昇格通知を出さない（誤通知の回帰防止）。"""
    app._settings.video_container = "mkv"
    notices: list[str] = []
    app._update_status = lambda msg, pct=0: notices.append(msg)

    # recode + 複数音声: is_multi_audio=True かつ video_container=mp4
    job = build_job_spec(
        "fmt_original",
        Settings(video_container="mkv"),
        panel=_recode_panel(has_multiple_audio=True),
    )
    assert job.is_multi_audio is True
    assert job.recode_video is True
    assert job.video_container == "mp4"

    app._notify_container_promotion_if_needed(job)
    assert notices == []


def test_mkv_promotion_notice_still_fires_without_recode(app):
    """通常の複数音声 MKV 昇格では従来どおり通知する（回帰なし確認）。"""
    notices: list[str] = []
    app._update_status = lambda msg, pct=0: notices.append(msg)

    panel = PanelSnapshot(
        format_spec="137+140+141",
        subtitle_opts=None,
        remux_only=False,
        audio_only=False,
        recode_video=False,
        embed_thumbnail=False,
        embed_metadata=True,
        embed_chapters=True,
        has_multiple_audio=True,
        raw_settings={},
    )
    job = build_job_spec(
        "fmt_original", Settings(video_container="mp4"), panel=panel
    )
    assert job.is_multi_audio is True
    assert job.video_container == "mkv"

    app._notify_container_promotion_if_needed(job)
    assert len(notices) == 1
