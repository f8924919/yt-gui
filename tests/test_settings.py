"""yt_gui.settings のテスト。

対応仕様: docs/spec/settings.md
"""

import json
from pathlib import Path

import pytest

from yt_gui.settings import Settings, SettingsManager, build_proxy_url


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
    assert s.concurrent_fragments == 1
    assert s.proxy_enabled is False
    assert s.proxy_scheme == "http"
    assert s.proxy_host == ""
    assert s.proxy_port == ""
    assert s.proxy_username == ""
    assert s.proxy_password == ""


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


def test_concurrent_fragments_roundtrips(manager: SettingsManager) -> None:
    original = Settings(concurrent_fragments=8)
    manager.save(original)
    assert manager.load().concurrent_fragments == 8


def test_concurrent_fragments_defaults_from_old_json(
    manager: SettingsManager, tmp_path: Path
) -> None:
    """concurrent_fragments 無しの古い settings.json でも既定 1 で読み込めること。"""
    config_file = tmp_path / "yt-gui" / "settings.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"language": "en"}), encoding="utf-8")
    assert manager.load().concurrent_fragments == 1


def test_proxy_fields_roundtrip(manager: SettingsManager) -> None:
    original = Settings(
        proxy_enabled=True,
        proxy_scheme="socks5h",
        proxy_host="proxy.example.com",
        proxy_port="1080",
        proxy_username="alice",
        proxy_password="s3cret",
    )
    manager.save(original)
    assert manager.load() == original


def test_proxy_fields_migrate_from_old_json(
    manager: SettingsManager, tmp_path: Path
) -> None:
    """proxy_* 無しの古い settings.json でもデフォルト値で読み込めること。"""
    config_file = tmp_path / "yt-gui" / "settings.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"language": "en"}), encoding="utf-8")
    loaded = manager.load()
    assert loaded.language == "en"
    assert loaded.proxy_enabled is False
    assert loaded.proxy_host == ""


def test_build_proxy_url_disabled_returns_empty() -> None:
    assert (
        build_proxy_url(Settings(proxy_enabled=False, proxy_host="proxy.example.com"))
        == ""
    )


def test_build_proxy_url_no_host_returns_empty() -> None:
    assert build_proxy_url(Settings(proxy_enabled=True, proxy_host="")) == ""


def test_build_proxy_url_blank_host_returns_empty() -> None:
    assert build_proxy_url(Settings(proxy_enabled=True, proxy_host="   ")) == ""


def test_build_proxy_url_basic_http() -> None:
    s = Settings(
        proxy_enabled=True,
        proxy_scheme="http",
        proxy_host="proxy.example.com",
        proxy_port="8080",
    )
    assert build_proxy_url(s) == "http://proxy.example.com:8080"


def test_build_proxy_url_socks5h_without_port() -> None:
    s = Settings(
        proxy_enabled=True,
        proxy_scheme="socks5h",
        proxy_host="proxy.example.com",
    )
    assert build_proxy_url(s) == "socks5h://proxy.example.com"


def test_build_proxy_url_with_auth() -> None:
    s = Settings(
        proxy_enabled=True,
        proxy_scheme="socks5",
        proxy_host="proxy.example.com",
        proxy_port="1080",
        proxy_username="alice",
        proxy_password="bob",
    )
    assert build_proxy_url(s) == "socks5://alice:bob@proxy.example.com:1080"


def test_build_proxy_url_with_username_only() -> None:
    s = Settings(
        proxy_enabled=True,
        proxy_scheme="http",
        proxy_host="proxy.example.com",
        proxy_port="8080",
        proxy_username="alice",
    )
    assert build_proxy_url(s) == "http://alice@proxy.example.com:8080"


def test_build_proxy_url_encodes_special_chars() -> None:
    s = Settings(
        proxy_enabled=True,
        proxy_scheme="http",
        proxy_host="proxy.example.com",
        proxy_port="8080",
        proxy_username="user@corp",
        proxy_password="p@ss:word",
    )
    assert (
        build_proxy_url(s) == "http://user%40corp:p%40ss%3Aword@proxy.example.com:8080"
    )
