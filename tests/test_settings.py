"""yt_gui.settings のテスト。

対応仕様: docs/spec/settings.md
"""

import json
from pathlib import Path

import pytest

from yt_gui.settings import Settings, SettingsManager


def test_settings_defaults_match_spec() -> None:
    s = Settings()
    assert s.cookies_path == ""
    assert s.cookies_browser == ""
    assert s.download_path == ""
    assert s.language == "ja"
    assert s.video_resolution == "720"
    assert s.mp3_bitrate == "192"
    assert s.audio_format == "mp3"
    assert s.video_container == "mp4"
    assert s.output_template_video == "%(title)s.%(ext)s"
    assert s.output_template_playlist == (
        "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    )


@pytest.fixture
def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SettingsManager:
    monkeypatch.setattr(
        "yt_gui.settings._get_config_dir", lambda: str(tmp_path / "yt-gui")
    )
    return SettingsManager()


def test_save_then_load_roundtrips_all_fields(manager: SettingsManager) -> None:
    original = Settings(
        download_path="/tmp/dl",
        language="en",
        video_resolution="1080",
        audio_format="flac",
    )
    manager.save(original)
    assert manager.load() == original


def test_load_returns_defaults_when_file_missing(manager: SettingsManager) -> None:
    assert manager.load() == Settings()


def test_load_returns_defaults_when_json_is_corrupt(
    manager: SettingsManager, tmp_path: Path
) -> None:
    config_file = tmp_path / "yt-gui" / "settings.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{not valid json", encoding="utf-8")
    assert manager.load() == Settings()


def test_load_ignores_unknown_fields(manager: SettingsManager, tmp_path: Path) -> None:
    config_file = tmp_path / "yt-gui" / "settings.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps({"language": "en", "obsolete_field": "value"}),
        encoding="utf-8",
    )
    loaded = manager.load()
    assert loaded.language == "en"
    assert not hasattr(loaded, "obsolete_field")
