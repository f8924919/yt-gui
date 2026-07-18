"""`App` 周辺の UI ロジックを検証する。

- `_QueueTree._edit_targets`: 「形式を変更」(= `edit_format_requested`) の対象判定
  （対象が `waiting` のみ、かつ編集モード中でない）
- `_refresh_format_labels`: 言語変更に追従して `format_combo` を再構築する

`contextMenuEvent` 本体はモーダル `QMenu.exec`（offscreen でヘッドレス駆動不可）を
含むため、活性判定と発火判定で共用する純粋ヘルパ `_edit_targets` を検証対象とする。

対応 spec: [メインウィンドウ](../docs/spec/screens/main-window.md)。
対応 arch: [app.py](../docs/arch/app.md)。
"""

from typing import Any

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from yt_gui import app as app_module
from yt_gui import i18n
from yt_gui.app import App, _QueueTree
from yt_gui.i18n import t
from yt_gui.job_spec import PanelSnapshot, build_job_spec
from yt_gui.queue_controller import _QueueItem
from yt_gui.settings import Settings
from yt_gui.yt_dlp_update import UpdateCheckResult, UpdateStatus

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
    tree, _state = queue_tree
    waiting = _make_item("waiting")
    downloading = _make_item("downloading")

    assert tree._edit_targets([waiting, downloading]) == [waiting]


def test_edit_targets_empty_while_editing(queue_tree):
    tree, state = queue_tree
    state["editing"] = True

    assert tree._edit_targets([_make_item("waiting")]) == []


def test_edit_targets_empty_when_no_waiting(queue_tree):
    tree, _state = queue_tree

    assert tree._edit_targets([_make_item("downloading"), _make_item("done")]) == []


@pytest.fixture
def app(qtbot, tmp_path, monkeypatch):
    # HOME の差し替えは Windows（APPDATA 参照）では効かないため、
    # 設定ディレクトリの解決関数を直接差し替えて OS 非依存に分離する。
    # デフォルト保存先（~/Downloads）は迂回されないが、App 構築時に
    # 書き込みは発生しないため分離は保たれる。
    monkeypatch.setattr(
        "yt_gui.settings._get_config_dir", lambda: str(tmp_path / "yt-gui")
    )
    from yt_gui.downloader import Downloader

    monkeypatch.setattr(Downloader, "missing_dependencies", lambda self: [])
    # 起動時のアプリ更新チェックがテストから実ネットワークへ出ないよう無効化。
    monkeypatch.setattr(App, "_check_app_update_on_startup", lambda self: None)
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


def test_settings_action_has_preferences_menu_role(app):
    """設定アクションは PreferencesRole を明示し、macOS で言語によらずアプリ
    メニュー配下に表示されるようにする（#160。既定の TextHeuristicRole だと
    英語 `Settings...` のみアプリメニューへ移動し日本語 `設定...` が File に残る）。"""
    from PySide6.QtGui import QAction

    assert app._act_settings.menuRole() == QAction.MenuRole.PreferencesRole


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

    def _warn(*a, **kw):
        warned.append(a)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)
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


def _enable_chapter_section(app, pattern: str, force: bool = False) -> None:
    app._section_check.setChecked(True)
    app._section_mode_chapter.setChecked(True)
    app._section_chapter_edit.setText(pattern)
    app._section_keyframe_check.setChecked(force)


def test_read_section_none_when_disabled(app):
    app._section_check.setChecked(False)
    assert app._read_section() == (None, None, None, False)


def test_read_section_returns_values_when_enabled(app):
    _enable_section(app, "00:01:30", "00:04:00", force=True)
    assert app._read_section() == ("00:01:30", "00:04:00", None, True)


def test_section_mode_defaults_to_time_range(app):
    app._section_check.setChecked(True)
    assert app._section_mode_time.isChecked() is True
    assert app._section_mode_chapter.isChecked() is False


def test_section_mode_chapter_switches_input_rows(app):
    """モード切り替えで選択中モードの入力行だけが表示される。"""
    app._section_check.setChecked(True)
    assert not app._section_time_row.isHidden()
    assert app._section_chapter_row.isHidden()

    app._section_mode_chapter.setChecked(True)
    assert app._section_time_row.isHidden()
    assert not app._section_chapter_row.isHidden()

    app._section_mode_time.setChecked(True)
    assert not app._section_time_row.isHidden()
    assert app._section_chapter_row.isHidden()


def test_read_section_returns_chapter_regex_in_chapter_mode(app):
    _enable_chapter_section(app, "^OP", force=True)
    # 排他: チャプターモードでは時間範囲は返さない（残存入力があっても無視）
    app._section_start.setText("10")
    app._section_end.setText("20")
    assert app._read_section() == (None, None, "^OP", True)


def test_validate_section_ok_when_disabled(app):
    app._section_check.setChecked(False)
    assert app._validate_section() is True


def test_validate_section_rejects_invalid_time(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []

    def _warn(*a, **k):
        warned.append(a[2])

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    _enable_section(app, "abc", "00:04:00")
    assert app._validate_section() is False
    assert warned


def test_validate_section_rejects_start_after_end(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []

    def _warn(*a, **k):
        warned.append(a[2])

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    _enable_section(app, "00:05:00", "00:04:00")
    assert app._validate_section() is False
    assert warned == [t("warn_section_range")]


def test_validate_section_ok_with_valid_range(app):
    _enable_section(app, "90", "4:00")
    assert app._validate_section() is True


@pytest.mark.parametrize("pattern", ["[invalid", "", "   "], ids=["bad", "empty", "ws"])
def test_validate_section_rejects_bad_chapter_pattern(app, monkeypatch, pattern):
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []

    def _warn(*a, **k):
        warned.append(a[2])

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    _enable_chapter_section(app, pattern)
    assert app._validate_section() is False
    assert warned == [t("warn_section_chapter_invalid")]


def test_validate_section_ok_with_valid_chapter_regex(app):
    _enable_chapter_section(app, "^Chapter \\d+$")
    assert app._validate_section() is True


def test_validate_section_chapter_mode_ignores_time_fields(app):
    # チャプターモードでは時間範囲欄の内容は検証しない
    _enable_chapter_section(app, "^OP")
    app._section_start.setText("abc")
    app._section_end.setText("")
    assert app._validate_section() is True


def test_playlist_with_section_warns_and_aborts(app, monkeypatch):
    """取得後にプレイリストと判明し区間指定がある場合は警告して中断する。"""
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []

    def _warn(*a, **k):
        warned.append(a[2])

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    calls = []

    def _enqueue(*a, **k):
        calls.append(a)
        return []

    monkeypatch.setattr(app.queue, "enqueue_playlist", _enqueue)

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


def test_restore_section_chapter_from_job(app):
    job = build_job_spec(
        "fmt_best_mp4",
        Settings(),
        section_chapter_regex="^OP",
        section_force_keyframes=True,
    )
    app._restore_section_from_job(job)
    assert app._section_check.isChecked() is True
    assert app._section_mode_chapter.isChecked() is True
    assert app._section_chapter_edit.text() == "^OP"
    assert app._section_keyframe_check.isChecked() is True


def test_playlist_with_chapter_section_warns_and_aborts(app, monkeypatch):
    """チャプター指定でも時間範囲と同様にプレイリスト後追い中断する。"""
    from PySide6.QtWidgets import QMessageBox

    from yt_gui.i18n import t

    warned = []

    def _warn(*a, **k):
        warned.append(a[2])

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    calls = []

    def _enqueue(*a, **k):
        calls.append(a)
        return []

    monkeypatch.setattr(app.queue, "enqueue_playlist", _enqueue)

    job = build_job_spec("fmt_best_mp4", Settings(), section_chapter_regex="^OP")
    payload = {
        "result": {"type": "playlist", "entries": [{"id": "a"}], "title": "PL"},
        "job": job,
        "format_label": "MP4",
    }
    app._on_fetch_for_add_done(payload)

    assert warned == [t("warn_playlist_section")]
    assert calls == []


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
    job = build_job_spec("fmt_original", Settings(video_container="mp4"), panel=panel)
    assert job.is_multi_audio is True
    assert job.video_container == "mkv"

    app._notify_container_promotion_if_needed(job)
    assert len(notices) == 1


# ── オリジナル形式 追加フロー通し（手段B: exec を介さずシグナル駆動） ──────────
#
# 対応 spec: [オリジナル形式ダイアログ](../docs/spec/screens/original-format-dialog.md)
# ・[ダウンロードキュー](../docs/spec/features/queue.md)。


def test_open_original_dialog_add_flow_enqueues_one(app, monkeypatch):
    """追加モードでダイアログを開き、フォーマット取得済みで追加要求すると
    キューに1件積まれ URL 入力がクリアされること。"""
    from yt_gui.original_format_dialog import OriginalFormatDialog

    # offscreen で exec がブロックしないよう no-op 化し、生成済みダイアログを取得する。
    monkeypatch.setattr(OriginalFormatDialog, "exec", lambda self: None)
    app.url_entry.setText("https://example.com/watch?v=abc")
    _select_format(app, "fmt_original")

    dialog = app._open_original_dialog()
    assert dialog is not None

    # ネットワークを使わずフォーマット取得済み・タイトル確定の状態を模す。
    monkeypatch.setattr(dialog.panel, "has_formats_loaded", lambda: True)
    monkeypatch.setattr(dialog.panel, "get_fetched_title", lambda: "動画タイトル")

    before = len(app.queue._items)
    dialog.add_requested.emit()

    assert len(app.queue._items) == before + 1
    assert app.url_entry.text() == ""


# ── 設定反映ループ（手段B: SettingsDialog.exec を no-op 化） ──────────────────
#
# 対応 spec: [設定ダイアログ](../docs/spec/screens/settings-dialog.md)
# #設定変更後のメインウィンドウへの反映。


def test_open_settings_applies_saved_settings_to_downloader(app, monkeypatch):
    """設定ダイアログを閉じた後、保存済み設定が downloader 各属性へ転写されること。"""
    from yt_gui.settings_dialog import SettingsDialog

    monkeypatch.setattr(SettingsDialog, "exec", lambda self: None)
    desired = Settings(
        language=app._settings.language,  # 言語は変えず反映のみ検証
        video_resolution="1080",
        mp3_bitrate="320",
        concurrent_fragments=8,
    )
    app._settings_manager.save(desired)

    app._open_settings()

    assert app.downloader.video_resolution == "1080"
    assert app.downloader.mp3_bitrate == "320"
    assert app.downloader.concurrent_fragments == 8


def test_open_settings_retranslates_on_language_change(app, monkeypatch):
    """言語が変わった場合は `_retranslate_ui` を呼ぶこと。"""
    from yt_gui.settings_dialog import SettingsDialog

    monkeypatch.setattr(SettingsDialog, "exec", lambda self: None)
    called: list[bool] = []
    monkeypatch.setattr(app, "_retranslate_ui", lambda: called.append(True))

    old_lang = app._settings.language
    new_lang = "en" if old_lang != "en" else "ja"
    app._settings_manager.save(Settings(language=new_lang))

    app._open_settings()

    assert called


def test_translation_bindings_cover_all_static_texts(app):
    """レジストリ全件について、言語切替後の表示が切替先ロケール値と一致すること（#243）。

    #238 のハードコード対応表テストの後継。バインディングレジストリを走査する
    ため、ウィジェット追加（バインド登録）に自動追従する。期待値にはバインディング
    自身の transform を適用する（ウィンドウタイトルのバージョン合成等が追従する）。
    不一致は全件収集して 1 回で報告する。"""
    from yt_gui.locales import en

    # 区間 UI（#238 の 7 ウィジェット）を含む static 26 箇所が登録されている前提。
    # 空レジストリでの空振り green を防ぐため件数下限も検証する（macOS では
    # `_act_quit` 非生成のため 25）。
    assert len(app._translation_bindings) >= 25

    i18n.set_language("ja")
    app._retranslate_ui()
    i18n.set_language("en")
    app._retranslate_ui()

    mismatches = []
    for binding in app._translation_bindings:
        expected = en.STRINGS[binding.key]
        if binding.transform is not None:
            expected = binding.transform(expected)
        actual = binding.getter()
        if actual != expected:
            mismatches.append(f"{binding.key}: {actual!r} != {expected!r}")
    assert not mismatches, "再翻訳されていないバインディング:\n" + "\n".join(mismatches)


def test_retranslate_leaves_no_japanese_text_after_switch_to_en(app):
    """セーフティネット: 英語切替後に ja 固有文字列が UI に残らないこと（#243）。

    バインド登録し忘れの検知網。ウィジェットツリー（`text` / `title` /
    `placeholderText`）に加え、`findChildren(QWidget)` では拾えない `QAction`
    （メニュー項目）・ウィンドウタイトル・キューツリーヘッダー列も走査する。
    偽陽性を避けるため ja/en で値が異なるキーの ja 値との完全一致のみを違反とする。
    デフォルト状態の UI のみ走査するため、状態依存テキストは個別テストで担保する。"""
    from PySide6.QtWidgets import QWidget

    from yt_gui.locales import en, ja

    i18n.set_language("en")
    app._retranslate_ui()

    ja_only = {
        value for key, value in ja.STRINGS.items() if en.STRINGS.get(key) != value
    }

    displayed: list[str] = []
    for widget in app.findChildren(QWidget):
        for accessor in ("text", "title", "placeholderText"):
            getter = getattr(widget, accessor, None)
            if callable(getter):
                displayed.append(getter())
    displayed.extend(action.text() for action in app.findChildren(QAction))
    displayed.append(app.windowTitle())
    header = app._queue_tree.headerItem()
    displayed.extend(header.text(col) for col in range(app._queue_tree.columnCount()))

    leftovers = sorted({text for text in displayed if text in ja_only})
    assert not leftovers, f"日本語のまま残っている表示: {leftovers}"


def test_retranslate_updates_multi_edit_url_entry(app):
    """複数選択編集中の言語切替で `url_entry` の複数選択表示が再翻訳されること（#243）。

    `edit_multiple_selected` は #238 と同型の再翻訳漏れ（未登録）だったもの。
    セーフティネットはデフォルト状態しか走査しないため個別に担保する。"""
    from yt_gui.locales import en, ja

    i18n.set_language("ja")
    app._retranslate_ui()
    items = [
        _make_item("waiting", url="https://example.com/v1"),
        _make_item("waiting", url="https://example.com/v2"),
    ]
    assert app.queue.enter_edit_mode(items)
    assert app.url_entry.text() == ja.STRINGS["edit_multiple_selected"].format(count=2)

    i18n.set_language("en")
    app._retranslate_ui()

    assert app.url_entry.text() == en.STRINGS["edit_multiple_selected"].format(count=2)


def test_retranslate_keeps_apply_edit_button_text_in_edit_mode(app):
    """編集モード中の言語切替で `add_button` が `btn_apply_edit` 側で追従すること。

    #238 由来テストの置き換えで既存担保が失われないよう明示的に残す（#243）。"""
    from yt_gui.locales import en

    i18n.set_language("ja")
    app._retranslate_ui()
    assert app.queue.enter_edit_mode([_make_item("waiting")])

    i18n.set_language("en")
    app._retranslate_ui()

    assert app.add_button.text() == en.STRINGS["btn_apply_edit"]


# ── URL 取得中の add_button 状態保持（#244） ─────────────────────────────────
#
# 対応 spec: [メインウィンドウ](../docs/spec/screens/main-window.md)
# の「状態の重なりと表示の優先順位（#244）」。
# タイトル取得中はテキスト解決の優先順位が fetching > edit_mode > 通常となり、
# 言語切替・編集モードの出入りでも「取得中...」表示が失われないことを検証する。


def _start_fetch(app, monkeypatch) -> dict:
    """タイトル取得開始直後の状態を実経路（`_start_add_thread`）で作る。

    スレッドは起動せず、`run_in_thread` に渡されるコールバックを捕捉して返す
    （`on_finished` = `_reset_add_button` を後から呼べるようにする）。"""
    captured: dict = {}

    def fake_run_in_thread(
        work, *, on_done=None, on_failed=None, on_finished=None, parent=None
    ):
        captured.update(on_done=on_done, on_failed=on_failed, on_finished=on_finished)

    monkeypatch.setattr(app_module, "run_in_thread", fake_run_in_thread)
    app._start_add_thread(
        "https://example.com/v",
        None,
        None,
        build_job_spec("fmt_best_mp4", Settings()),
        "MP4",
    )
    return captured


def test_retranslate_keeps_btn_adding_while_fetching(app, monkeypatch):
    """取得中に言語を切り替えても切替先ロケールの btn_adding を表示し続ける。"""
    from yt_gui.locales import en, ja

    i18n.set_language("ja")
    app._retranslate_ui()
    _start_fetch(app, monkeypatch)
    assert app.add_button.text() == ja.STRINGS["btn_adding"]
    assert not app.add_button.isEnabled()

    i18n.set_language("en")
    app._retranslate_ui()

    assert app.add_button.text() == en.STRINGS["btn_adding"]
    assert not app.add_button.isEnabled()


def test_enter_edit_mode_keeps_btn_adding_while_fetching(app, monkeypatch):
    """取得中の編集モード入りでも btn_adding 維持、取得完了後 btn_apply_edit。"""
    from yt_gui.locales import ja

    i18n.set_language("ja")
    app._retranslate_ui()
    captured = _start_fetch(app, monkeypatch)

    assert app.queue.enter_edit_mode([_make_item("waiting")])
    assert app.add_button.text() == ja.STRINGS["btn_adding"]

    captured["on_finished"]()  # = _reset_add_button（取得完了）

    assert app._fetching is False
    assert app.add_button.isEnabled()
    assert app.add_button.text() == ja.STRINGS["btn_apply_edit"]


def test_exit_edit_mode_keeps_btn_adding_while_fetching(app, monkeypatch):
    """取得中に編集モードを抜けても btn_adding が維持される（消失経路 3）。"""
    from yt_gui.locales import ja

    i18n.set_language("ja")
    app._retranslate_ui()
    _start_fetch(app, monkeypatch)

    assert app.queue.enter_edit_mode([_make_item("waiting")])
    app.queue.cancel_edit()

    assert app.add_button.text() == ja.STRINGS["btn_adding"]
    assert not app.add_button.isEnabled()


def test_reset_add_button_restores_normal_text_after_fetch(app, monkeypatch):
    """取得完了後は通常状態なら btn_add へ復帰する（成功経路の baseline）。"""
    from yt_gui.locales import ja

    i18n.set_language("ja")
    app._retranslate_ui()
    captured = _start_fetch(app, monkeypatch)

    captured["on_finished"]()

    assert app._fetching is False
    assert app.add_button.isEnabled()
    assert app.add_button.text() == ja.STRINGS["btn_add"]


def test_reset_add_button_restores_after_fetch_failure(app, monkeypatch):
    """取得失敗（on_failed 経由）でも _fetching が戻り btn_add へ復帰する。

    `run_in_thread` は成功・失敗を問わず最後に on_finished を呼ぶ契約
    （threading_utils）であり、失敗時も同じ復帰口を通ることを検証する。"""
    from yt_gui.locales import ja

    i18n.set_language("ja")
    app._retranslate_ui()
    captured = _start_fetch(app, monkeypatch)

    captured["on_failed"](Exception("boom"))  # QMessageBox は autouse で no-op
    captured["on_finished"]()

    assert app._fetching is False
    assert app.add_button.isEnabled()
    assert app.add_button.text() == ja.STRINGS["btn_add"]


def test_btn_adding_survives_combined_transitions_while_fetching(app, monkeypatch):
    """複合: 取得中の「編集入り→言語切替→編集抜け」でも常に btn_adding。"""
    from yt_gui.locales import en, ja

    i18n.set_language("ja")
    app._retranslate_ui()
    captured = _start_fetch(app, monkeypatch)

    assert app.queue.enter_edit_mode([_make_item("waiting")])
    assert app.add_button.text() == ja.STRINGS["btn_adding"]

    i18n.set_language("en")
    app._retranslate_ui()
    assert app.add_button.text() == en.STRINGS["btn_adding"]

    app.queue.cancel_edit()
    assert app.add_button.text() == en.STRINGS["btn_adding"]

    captured["on_finished"]()
    assert app.add_button.text() == en.STRINGS["btn_add"]


# ── ログダイアログの起動・再表示（_open_log_dialog） ─────────────────────────
#
# 対応 spec: [ログダイアログ](../docs/spec/screens/log-dialog.md)。


def test_open_log_dialog_creates_loads_and_shows(app):
    """初回起動で `LogDialog` を生成し、既存ログを読み込んで表示する。"""
    app._log_entries = ["[12:00:00] テストログ"]
    before = app._log_dialog
    assert before is None

    app._open_log_dialog()

    assert app._log_dialog is not None
    assert app._log_dialog.isVisible()
    assert "テストログ" in app._log_dialog._text.toPlainText()


def test_open_log_dialog_reuses_instance_while_visible(app):
    """表示中に再度開いても新規生成せず同一インスタンスを前面化する。"""
    app._open_log_dialog()
    first = app._log_dialog

    app._open_log_dialog()

    assert app._log_dialog is first


def test_log_dialog_close_clears_reference(app):
    """クローズコールバックで `_log_dialog` 参照が None に戻る。"""
    app._open_log_dialog()
    assert app._log_dialog is not None

    app._on_log_dialog_close()

    assert app._log_dialog is None


# ── ブラウザ拡張連携 ────────────────────────────────────────────────────────
# 対応 spec: docs/spec/features/browser-extension.md


def test_extension_default_format_uses_current_selection(app):
    """拡張追加の形式はメイン画面の現在選択を使う。"""
    _select_format(app, "fmt_mp3")
    format_id, label = app._extension_default_format()
    assert format_id == "fmt_mp3"
    assert label == app.format_combo.currentText()


def test_extension_default_format_falls_back_from_original(app):
    """オリジナル形式選択時は最高画質 MP4 へフォールバック。"""
    _select_format(app, "fmt_original")
    format_id, _label = app._extension_default_format()
    assert format_id == "fmt_best_mp4"


def test_write_extension_cookies_creates_file(app):
    path = app._write_extension_cookies("# Netscape HTTP Cookie File\nX\n")
    assert path is not None
    import os

    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        assert "Netscape" in f.read()


def test_on_extension_enqueue_threads_cookies(app, monkeypatch):
    """受信 cookies が一時ファイル化され、item_cookies_path として流れる。"""
    captured: dict[str, Any] = {}

    def _fake_start(
        url, cookies_path, cookies_browser, job, label, *, item_cookies_path=None
    ):
        captured.update(
            url=url,
            cookies_path=cookies_path,
            item_cookies_path=item_cookies_path,
        )

    monkeypatch.setattr(app, "_start_add_thread", _fake_start)
    app._on_extension_enqueue("https://example.com/v", "COOKIEDATA", None)

    import os

    assert captured["url"] == "https://example.com/v"
    assert captured["item_cookies_path"] is not None
    # fetch にも同じ cookies ファイルを使う
    assert captured["cookies_path"] == captured["item_cookies_path"]
    assert os.path.isfile(captured["item_cookies_path"])


def test_on_extension_enqueue_without_cookies(app, monkeypatch):
    captured: dict[str, Any] = {}

    def _fake_start(
        url, cookies_path, cookies_browser, job, label, *, item_cookies_path=None
    ):
        captured.update(cookies_path=cookies_path, item_cookies_path=item_cookies_path)

    monkeypatch.setattr(app, "_start_add_thread", _fake_start)
    app._on_extension_enqueue("https://example.com/v", None, None)

    assert captured["cookies_path"] is None
    assert captured["item_cookies_path"] is None


def _capture_enqueue_job(app, monkeypatch):
    """`_start_add_thread` をフックして (job, label) を捕捉するヘルパ。"""
    captured: dict[str, Any] = {}

    def _fake_start(
        url, cookies_path, cookies_browser, job, label, *, item_cookies_path=None
    ):
        captured.update(job=job, label=label)

    monkeypatch.setattr(app, "_start_add_thread", _fake_start)
    return captured


def test_on_extension_enqueue_audio_flac_overrides_per_item(app, monkeypatch):
    """拡張から audio/flac を指定するとアイテムにのみ反映し、グローバル設定は不変。"""
    app._settings.audio_format = "mp3"  # グローバルは mp3 のまま
    captured = _capture_enqueue_job(app, monkeypatch)

    app._on_extension_enqueue(
        "https://example.com/v", None, {"kind": "audio", "audio_format": "flac"}
    )

    job = captured["job"]
    assert job.format_id == "fmt_mp3"
    assert job.audio_codec == "flac"
    assert job.audio_only is True
    # グローバル設定は変更されない（アイテム単位の上書き）
    assert app._settings.audio_format == "mp3"


def test_on_extension_enqueue_audio_mp3_bitrate_override(app, monkeypatch):
    app._settings.audio_format = "mp3"
    app._settings.mp3_bitrate = "192"
    captured = _capture_enqueue_job(app, monkeypatch)

    app._on_extension_enqueue(
        "https://example.com/v",
        None,
        {"kind": "audio", "audio_format": "mp3", "mp3_bitrate": "320"},
    )

    job = captured["job"]
    assert job.format_id == "fmt_mp3"
    assert job.mp3_bitrate == "320"
    assert app._settings.mp3_bitrate == "192"  # グローバル不変


def test_on_extension_enqueue_resolution_override_keeps_container(app, monkeypatch):
    app._settings.video_resolution = "720"
    app._settings.video_container = "mkv"  # コンテナはアプリ設定に従う
    captured = _capture_enqueue_job(app, monkeypatch)

    app._on_extension_enqueue(
        "https://example.com/v", None, {"kind": "resolution", "resolution": "1080"}
    )

    job = captured["job"]
    assert job.format_id == "fmt_720p"
    assert "1080" in job.format_spec  # 指定解像度が反映
    assert job.video_container == "mkv"  # 拡張はコンテナを送らない
    # ラベルも実効 settings 基準（解像度 1080）で生成される
    assert "1080" in captured["label"]
    assert app._settings.video_resolution == "720"  # グローバル不変


def test_on_extension_enqueue_app_default_uses_combo_selection(app, monkeypatch):
    """app_default / 不正 format は従来どおりメイン画面の選択形式を使う。"""
    captured = _capture_enqueue_job(app, monkeypatch)

    app._on_extension_enqueue("https://example.com/v", None, {"kind": "app_default"})
    default_job = captured["job"]

    # 形式未指定（None）と同じ挙動になる
    captured2 = _capture_enqueue_job(app, monkeypatch)
    app._on_extension_enqueue("https://example.com/v", None, None)
    assert captured2["job"].format_id == default_job.format_id


# ── 拡張からのオリジナル形式（アプリ側ダイアログ起動・Issue #151） ────────────
# 対応 spec: docs/spec/features/browser-extension.md
#           （#オリジナル形式アプリ側ダイアログ起動）


def test_on_extension_enqueue_original_queues_dialog_request(app, monkeypatch):
    """kind=original は _start_add_thread せず pending キューへ積む。"""
    started = []
    monkeypatch.setattr(app, "_start_add_thread", lambda *a, **k: started.append(a))
    # 実ダイアログは開かず、pending への積み込みのみ検証する。
    monkeypatch.setattr(app, "_dispatch_next_original_dialog", lambda: None)

    app._on_extension_enqueue(
        "https://example.com/v", "COOKIEDATA", {"kind": "original"}
    )

    assert started == []  # 即時のキュー追加スレッドは起動しない
    assert len(app._pending_original_requests) == 1
    url, item_cookies_path = app._pending_original_requests[0]
    assert url == "https://example.com/v"
    # 受信 cookies が一時ファイル化され item_cookies_path として保持される
    import os

    assert item_cookies_path is not None
    assert os.path.isfile(item_cookies_path)


def test_dispatch_original_dialog_injects_url_cookies_and_fronts(app, monkeypatch):
    """ダイアログに拡張由来 URL と item Cookies が注入され、前面化される。"""
    captured = {}

    class _StubDialog:
        def exec(self):
            captured["exec_active"] = app._original_dialog_active

    def _fake_make(mode, restore, *, get_url=None, get_cookies=None, add_handler=None):
        captured.update(
            mode=mode,
            get_url=get_url,
            get_cookies=get_cookies,
            add_handler=add_handler,
        )
        return _StubDialog()

    monkeypatch.setattr(app, "_make_original_dialog", _fake_make)
    front = []
    monkeypatch.setattr(app, "raise_", lambda: front.append("raise"))
    monkeypatch.setattr(app, "activateWindow", lambda: front.append("activate"))

    app._pending_original_requests.append(
        ("https://example.com/v", "/tmp/ext_cookie.txt")
    )
    app._dispatch_next_original_dialog()

    assert captured["mode"] == "add"
    assert captured["get_url"]() == "https://example.com/v"
    # トラックプローブ・確定後 DL 双方へ item Cookies を適用する経路
    assert captured["get_cookies"]() == ("/tmp/ext_cookie.txt", None)
    assert front == ["raise", "activate"]  # 前面化された
    assert captured["exec_active"] is True  # exec 中は active フラグが立つ
    assert app._original_dialog_active is False  # 完了後に解除
    assert len(app._pending_original_requests) == 0  # 捌けた


def test_extension_original_add_enqueues_with_item_cookies(app, monkeypatch):
    """ダイアログ確定でキューに1件追加され、item Cookies がアイテムに紐付く。"""
    from yt_gui.original_format_dialog import OriginalFormatDialog

    opened = []
    monkeypatch.setattr(OriginalFormatDialog, "exec", lambda self: opened.append(self))

    app._pending_original_requests.append(
        ("https://example.com/v", "/tmp/ext_cookie.txt")
    )
    app._dispatch_next_original_dialog()
    dialog = opened[0]

    # ネットワークを使わずフォーマット取得済み・タイトル確定の状態を模す。
    monkeypatch.setattr(dialog.panel, "has_formats_loaded", lambda: True)
    monkeypatch.setattr(dialog.panel, "get_fetched_title", lambda: "動画タイトル")

    before = len(app.queue._items)
    dialog.add_requested.emit()

    assert len(app.queue._items) == before + 1
    item = app.queue._items[-1]
    assert item.url == "https://example.com/v"
    assert item.cookies_path == "/tmp/ext_cookie.txt"


def test_extension_original_uses_original_label_not_combo(app, monkeypatch):
    """拡張オリジナルフローのキュー表示は、メイン画面コンボの選択（既定の
    最高画質）に引きずられず「オリジナルの形式」になる（#175）。"""
    from yt_gui.formats import FORMAT_KEYS
    from yt_gui.original_format_dialog import OriginalFormatDialog

    # 拡張フローはコンボを操作しない。既定の最高画質 MP4 を選択した状態を再現。
    _select_format(app, "fmt_best_mp4")

    opened = []
    monkeypatch.setattr(OriginalFormatDialog, "exec", lambda self: opened.append(self))

    app._pending_original_requests.append(("https://example.com/v", None))
    app._dispatch_next_original_dialog()
    dialog = opened[0]

    monkeypatch.setattr(dialog.panel, "has_formats_loaded", lambda: True)
    monkeypatch.setattr(dialog.panel, "get_fetched_title", lambda: "動画タイトル")
    monkeypatch.setattr(dialog.panel, "get_audio_only", lambda: False)

    dialog.add_requested.emit()

    item = app.queue._items[-1]
    assert item.format_label == i18n.t("fmt_original")
    # 最高画質のラベルに化けていないこと（バグの再発防止）。
    best_label = app._format_display[FORMAT_KEYS.index("fmt_best_mp4")]
    assert item.format_label != best_label


def test_extension_original_cancel_does_not_enqueue(app, monkeypatch):
    """ダイアログをキャンセル（add_requested を発火しない）するとキューに積まれない。"""
    from yt_gui.original_format_dialog import OriginalFormatDialog

    opened = []
    monkeypatch.setattr(OriginalFormatDialog, "exec", lambda self: opened.append(self))

    before = len(app.queue._items)
    app._pending_original_requests.append(("https://example.com/v", None))
    app._dispatch_next_original_dialog()

    # 確定操作をしない＝キャンセル相当。キューは増えない。
    assert len(app.queue._items) == before


def test_extension_original_serializes_multiple_requests(app, monkeypatch):
    """複数 original を連続送信しても多重モーダルを開かず、順に直列処理される。

    直列化の検証にダイアログ内部は不要なため、`_make_original_dialog` を
    スタブ化して exec 中の再入ガードと待ち行列の捌け方だけを確認する。
    """
    opened: list[bool] = []

    class _StubDialog:
        def exec(self):
            # exec 中（active）に別の original が来ても多重起動しないこと。
            if not opened:
                app._pending_original_requests.append(("u2", None))
            app._dispatch_next_original_dialog()  # active ガードで何もしないはず
            opened.append(app._original_dialog_active)

    monkeypatch.setattr(app, "_make_original_dialog", lambda *a, **k: _StubDialog())

    app._pending_original_requests.append(("u1", None))
    app._dispatch_next_original_dialog()

    # u1 の exec 中に積まれた u2 も、exec 完了後に1件ずつ処理される。
    assert len(opened) == 2
    assert all(active is True for active in opened)  # 各 exec 中は active
    assert app._original_dialog_active is False  # 最終的に解除
    assert len(app._pending_original_requests) == 0  # 全部捌けた


def test_sync_extension_server_starts_and_stops(app, monkeypatch):
    """有効化（トークン有）で起動、無効化で停止すること。"""
    started = {"n": 0}
    stopped = {"n": 0}

    class _FakeServer:
        def __init__(self, *a, **k):
            pass

        def start(self):
            started["n"] += 1
            return 8718

        def stop(self):
            stopped["n"] += 1

    monkeypatch.setattr("yt_gui.app.ExtensionServer", _FakeServer)

    app._settings.extension_enabled = True
    app._settings.extension_token = "tok"
    app._sync_extension_server()
    assert app._extension_server is not None
    assert started["n"] == 1

    app._settings.extension_enabled = False
    app._sync_extension_server()
    assert app._extension_server is None
    assert stopped["n"] == 1


def test_sync_extension_server_skips_without_token(app, monkeypatch):
    """トークン未設定なら起動しない。"""
    monkeypatch.setattr(
        "yt_gui.app.ExtensionServer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not construct")),
    )
    app._settings.extension_enabled = True
    app._settings.extension_token = ""
    app._sync_extension_server()
    assert app._extension_server is None


def test_count_cookies_ignores_comments_and_blanks(app):
    netscape = (
        "# Netscape HTTP Cookie File\n"
        "\n"
        ".nicovideo.jp\tTRUE\t/\tTRUE\t0\tuser_session\tabc\n"
        ".nicovideo.jp\tTRUE\t/\tTRUE\t0\tlang\tja\n"
    )
    assert app._count_cookies(netscape) == 2
    assert app._count_cookies(None) == 0
    assert app._count_cookies("# only comment\n") == 0


def test_on_extension_enqueue_logs_cookie_count(app, monkeypatch):
    logs = []
    monkeypatch.setattr(app, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(app, "_start_add_thread", lambda *a, **k: None)

    netscape = (
        "# Netscape HTTP Cookie File\n"
        ".nicovideo.jp\tTRUE\t/\tTRUE\t0\tuser_session\tx\n"
    )
    app._on_extension_enqueue("https://www.nicovideo.jp/watch/sm1", netscape, None)
    assert any("1" in m and ("Cookie" in m or "cookie" in m) for m in logs)


def test_on_extension_enqueue_logs_no_cookies(app, monkeypatch):
    logs = []
    monkeypatch.setattr(app, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(app, "_start_add_thread", lambda *a, **k: None)

    app._on_extension_enqueue("https://www.nicovideo.jp/watch/sm1", None, None)
    # Cookie なしのログが出る（i18n 文言の一部で判定）
    assert any("Cookie" in m or "cookie" in m for m in logs)


# ── ヘルプメニュー / yt-dlp 更新チェック（#178） ──────────────────────────────


def test_help_menu_has_about_action(app):
    """ヘルプメニュー＋「バージョン情報 / 更新を確認」が AboutRole で追加される。"""
    assert app._help_menu is not None
    assert app._act_about.text() == t("menu_about")
    assert app._act_about.menuRole() == QAction.MenuRole.AboutRole


def test_check_update_up_to_date_runs_in_background_and_notifies(
    app, qtbot, monkeypatch
):
    """照会はバックグラウンド実行され、結果は Slot 経由で通知される（最新時）。"""
    result = UpdateCheckResult(
        current="2026.06.09", latest="2026.06.09", status=UpdateStatus.UP_TO_DATE
    )
    monkeypatch.setattr(app_module, "check_for_update", lambda current: result)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: seen.setdefault("msg", a[2]),
    )

    app._check_yt_dlp_update()
    qtbot.waitUntil(lambda: "msg" in seen, timeout=2000)
    assert seen["msg"] == t("update_up_to_date")


def test_check_update_available_shows_latest_version(app, qtbot, monkeypatch):
    """より新しい版があるときは最新版を含む通知を表示する。"""
    result = UpdateCheckResult(
        current="2026.05.01",
        latest="2026.06.09",
        status=UpdateStatus.UPDATE_AVAILABLE,
    )
    monkeypatch.setattr(app_module, "check_for_update", lambda current: result)
    captured = {}

    # UPDATE_AVAILABLE 分岐はインスタンス `QMessageBox.exec()` を使うため、
    # offscreen でハングしないよう no-op 化し、表示テキストだけ確認する。
    def fake_exec(self):
        captured["text"] = self.text()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec, raising=False)

    app._check_yt_dlp_update()
    qtbot.waitUntil(lambda: "text" in captured, timeout=2000)
    assert result.latest in captured["text"]


def test_check_update_failure_notifies_and_does_not_crash(app, qtbot, monkeypatch):
    """照会失敗時は警告で穏当に通知し、アプリは継続する。"""

    def boom(current):
        raise OSError("offline")

    monkeypatch.setattr(app_module, "check_for_update", boom)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: seen.setdefault("msg", a[2])
    )

    app._check_yt_dlp_update()
    qtbot.waitUntil(lambda: "msg" in seen, timeout=2000)
    assert "offline" in seen["msg"]


# ── アプリ実体更新（Phase B-2・#253）─────────────────────────────────────────
# 対応 spec: docs/spec/features/app-update.md「Phase B」節。
# 対応 arch: docs/arch/self_update.md「適用（Phase B-2）」/ docs/arch/app.md。


def _frozen_install(monkeypatch, tmp_path) -> Any:
    """PyInstaller バンドル実行相当（frozen・書き込み可能な親）を構成する。"""
    import sys

    exe = tmp_path / "apps" / "yt-gui" / "yt-gui.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(app_module, "get_version", lambda: "0.5.0")
    return exe.parent


def _available_result() -> UpdateCheckResult:
    return UpdateCheckResult(
        current="0.5.0", latest="9.9.9", status=UpdateStatus.UPDATE_AVAILABLE
    )


def test_app_update_box_shows_update_button_when_available(app, monkeypatch, tmp_path):
    _frozen_install(monkeypatch, tmp_path)
    _box, update_btn, open_btn = app._create_app_update_box(_available_result())
    assert update_btn is not None
    assert update_btn.isEnabled()
    assert open_btn is not None
    assert update_btn.text() == t("btn_update_and_restart")


def test_app_update_box_hides_update_button_on_non_windows(app, monkeypatch, tmp_path):
    import sys

    _frozen_install(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    _box, update_btn, open_btn = app._create_app_update_box(_available_result())
    assert update_btn is None
    assert open_btn is not None  # 手動 DL 導線は常に残す


def test_app_update_box_hides_update_button_when_not_frozen(app, monkeypatch, tmp_path):
    import sys

    _frozen_install(monkeypatch, tmp_path)
    monkeypatch.delattr(sys, "frozen", raising=False)
    _box, update_btn, _open_btn = app._create_app_update_box(_available_result())
    assert update_btn is None


def test_app_update_box_hides_update_button_when_version_unknown(
    app, monkeypatch, tmp_path
):
    _frozen_install(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "get_version", lambda: "unknown")
    _box, update_btn, _open_btn = app._create_app_update_box(_available_result())
    assert update_btn is None


def test_app_update_box_hides_update_button_when_parent_not_writable(
    app, monkeypatch, tmp_path
):
    import sys

    _frozen_install(monkeypatch, tmp_path)
    # 親ディレクトリが存在しない = 書き込み判定 False（プリフライト不可）。
    monkeypatch.setattr(
        sys, "executable", str(tmp_path / "gone" / "yt-gui" / "yt-gui.exe")
    )
    _box, update_btn, _open_btn = app._create_app_update_box(_available_result())
    assert update_btn is None


def test_app_update_box_disables_update_button_while_queue_running(
    app, monkeypatch, tmp_path
):
    _frozen_install(monkeypatch, tmp_path)
    monkeypatch.setattr(type(app.queue), "is_running", property(lambda self: True))
    box, update_btn, _open_btn = app._create_app_update_box(_available_result())
    assert update_btn is not None
    assert not update_btn.isEnabled()
    # キュー完了後の実行を案内する文言を本文に添える。
    assert t("app_update_queue_running_hint") in box.text()


def _success_result(tmp_path) -> Any:
    from yt_gui.self_update import SelfUpdateResult, SelfUpdateStatus

    new_dir = tmp_path / "apps" / "yt-gui.update-staging" / "yt-gui-9.9.9-new"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "yt-gui.exe").write_bytes(b"")
    return SelfUpdateResult(
        SelfUpdateStatus.SUCCESS, version="9.9.9", extracted_dir=new_dir
    )


def _wire_apply_recorders(app, monkeypatch, *, launch_ok: bool = True) -> dict:
    """スクリプト生成・起動・close・失敗ダイアログの呼び出しを記録する。"""
    calls: dict[str, Any] = {}

    def _fake_build(**kw: Any) -> str:
        calls["build"] = kw
        return "SCRIPT"

    def _fake_launch(text: str, **kw: Any) -> bool:
        calls["launch"] = text
        return launch_ok

    monkeypatch.setattr(app_module.self_update, "build_replace_script", _fake_build)
    monkeypatch.setattr(app_module.self_update, "launch_replace_script", _fake_launch)
    monkeypatch.setattr(app, "close", lambda: calls.setdefault("close", True))
    monkeypatch.setattr(
        app, "_show_self_update_failed", lambda: calls.setdefault("failed", True)
    )
    return calls


def _drive_self_update(
    app, qtbot, monkeypatch, result, *, cancel_before_finish: bool = False
) -> None:
    """`_start_self_update()` の実配線で完了ハンドラまで駆動する（#268）。

    実 `QProgressDialog`・実 `canceled` 接続を通す（`dialog.close()` は
    差し替えない）。`cancel_before_finish` は「検証完了直前にユーザー
    キャンセルが立った」競合を再現する。
    """

    def fake_download(current, work_dir, *, progress=None, cancel=None, **kw):
        if cancel_before_finish and cancel is not None:
            cancel.set()
        # _start_self_update() 冒頭の cleanup_leftovers がステージングを消す
        # ため、展開結果は callable で渡してこの時点（掃除後）に生成する。
        return result() if callable(result) else result

    monkeypatch.setattr(
        app_module.self_update, "download_and_verify_update", fake_download
    )
    with qtbot.waitSignal(app._signals.self_update_finished, timeout=5000):
        app._start_self_update()
    qtbot.waitUntil(lambda: app._self_update_dialog is None, timeout=2000)


def test_self_update_success_launches_script_and_closes(
    app, qtbot, monkeypatch, tmp_path
):
    """成功時は実ダイアログ配線でもスクリプト起動 → アプリ終了へ進む（#268）。"""
    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch)

    _drive_self_update(app, qtbot, monkeypatch, lambda: _success_result(tmp_path))

    assert calls.get("launch") == "SCRIPT"
    assert calls.get("close") is True
    assert "failed" not in calls


def test_self_update_success_respects_late_cancel(app, qtbot, monkeypatch, tmp_path):
    """検証完了とキャンセルの競合: 適用直前にキャンセル状態を再確認する。"""
    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch)

    _drive_self_update(
        app,
        qtbot,
        monkeypatch,
        lambda: _success_result(tmp_path),
        cancel_before_finish=True,
    )

    assert "launch" not in calls
    assert "close" not in calls


def test_self_update_failure_shows_failed_dialog_and_keeps_app(
    app, qtbot, monkeypatch, tmp_path
):
    """fail-closed: 検証失敗はアプリを終了せず穏当に通知する。"""
    from yt_gui.self_update import SelfUpdateResult, SelfUpdateStatus

    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch)

    _drive_self_update(
        app,
        qtbot,
        monkeypatch,
        SelfUpdateResult(SelfUpdateStatus.VERIFICATION_FAILED, version="9.9.9"),
    )

    assert calls.get("failed") is True
    assert "launch" not in calls
    assert "close" not in calls


def test_self_update_cancelled_is_silent(app, qtbot, monkeypatch, tmp_path):
    """ワーカー起点の CANCELLED は通知なしで閉じ、適用しない。"""
    from yt_gui.self_update import SelfUpdateResult, SelfUpdateStatus

    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch)

    _drive_self_update(
        app,
        qtbot,
        monkeypatch,
        SelfUpdateResult(SelfUpdateStatus.CANCELLED, version="9.9.9"),
    )

    assert "failed" not in calls
    assert "launch" not in calls
    assert "close" not in calls


def test_self_update_launch_failure_keeps_app_open(app, qtbot, monkeypatch, tmp_path):
    """スクリプト起動失敗時はアプリを終了せず「更新失敗」へ戻す。"""
    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch, launch_ok=False)

    _drive_self_update(app, qtbot, monkeypatch, lambda: _success_result(tmp_path))

    assert calls.get("failed") is True
    assert "close" not in calls


def test_self_update_rejects_extracted_dir_without_exe(
    app, qtbot, monkeypatch, tmp_path
):
    """展開結果に exe が無ければ差し替えに進まない（健全性確認）。"""
    import shutil

    _frozen_install(monkeypatch, tmp_path)
    calls = _wire_apply_recorders(app, monkeypatch)
    result = _success_result(tmp_path)
    shutil.rmtree(result.extracted_dir)

    _drive_self_update(app, qtbot, monkeypatch, result)

    assert calls.get("failed") is True
    assert "launch" not in calls
    assert "close" not in calls


def test_self_update_dialog_is_application_modal(app):
    """進捗ダイアログはモーダル（表示中のキュー開始等をブロックする）。"""
    from PySide6.QtCore import Qt

    dialog = app._create_self_update_dialog()
    try:
        assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    finally:
        dialog.deleteLater()


def test_self_update_progress_slot_updates_dialog(app, monkeypatch, tmp_path):
    _frozen_install(monkeypatch, tmp_path)
    dialog = app._create_self_update_dialog()
    app._self_update_dialog = dialog
    try:
        app._on_self_update_progress(50, 100)
        assert dialog.maximum() == 100
        assert dialog.value() == 50
        # Content-Length 欠落（total=None）は不定進捗（busy）表示へ切り替える。
        app._on_self_update_progress(10, None)
        assert dialog.maximum() == 0
    finally:
        dialog.deleteLater()
        app._self_update_dialog = None


def test_self_update_worker_reports_via_signals(app, qtbot, monkeypatch, tmp_path):
    """ワーカースレッドからの進捗・完了が Signal/Slot 経由でメインスレッドへ届く。"""
    from yt_gui.self_update import SelfUpdateResult, SelfUpdateStatus

    _frozen_install(monkeypatch, tmp_path)

    def fake_download(current, work_dir, *, progress=None, cancel=None, **kw):
        progress(50, 100)
        return SelfUpdateResult(SelfUpdateStatus.CANCELLED, version="9.9.9")

    monkeypatch.setattr(
        app_module.self_update, "download_and_verify_update", fake_download
    )
    with qtbot.waitSignals(
        [app._signals.self_update_progress, app._signals.self_update_finished],
        timeout=5000,
    ):
        app._start_self_update()
    # CANCELLED はサイレント（ダイアログは閉じられ、アプリは開いたまま）。
    qtbot.waitUntil(lambda: app._self_update_dialog is None, timeout=2000)


def test_start_self_update_clears_stale_leftovers(app, qtbot, monkeypatch, tmp_path):
    """更新開始時に前回の .bak / ステージング残骸を掃除してから DL する。"""
    from yt_gui.self_update import SelfUpdateResult, SelfUpdateStatus

    install = _frozen_install(monkeypatch, tmp_path)
    stale_staging = install.parent / "yt-gui.update-staging"
    stale_staging.mkdir()
    (stale_staging / "junk.txt").write_bytes(b"junk")

    monkeypatch.setattr(
        app_module.self_update,
        "download_and_verify_update",
        lambda *a, **kw: SelfUpdateResult(SelfUpdateStatus.CANCELLED),
    )
    with qtbot.waitSignal(app._signals.self_update_finished, timeout=5000):
        app._start_self_update()
    assert not (stale_staging / "junk.txt").exists()


def test_cleanup_update_leftovers_on_startup(app, monkeypatch, tmp_path):
    """起動時（メインウィンドウ表示後）に .bak とステージング残骸を削除する。"""
    install = _frozen_install(monkeypatch, tmp_path)
    bak = install.parent / "yt-gui.bak"
    staging = install.parent / "yt-gui.update-staging"
    for d in (bak, staging):
        d.mkdir()
        (d / "f.txt").write_bytes(b"x")

    # run_in_thread を同期実行に差し替え（既存テストと同じ注入点）。
    def sync_run_in_thread(fn, on_done=None, on_failed=None, **kw):
        try:
            result = fn()
        except Exception as exc:
            if on_failed is not None:
                on_failed(exc)
            return
        if on_done is not None:
            on_done(result)

    monkeypatch.setattr(app_module, "run_in_thread", sync_run_in_thread)
    app._cleanup_update_leftovers()
    assert not bak.exists()
    assert not staging.exists()


def test_cleanup_update_leftovers_noop_when_not_frozen(app, monkeypatch):
    import sys

    monkeypatch.delattr(sys, "frozen", raising=False)
    app._cleanup_update_leftovers()  # 例外を出さない（何もしない）
