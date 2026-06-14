"""yt_gui.formats のテスト。

対応仕様: docs/spec/features/download-formats.md
"""

import pytest

from yt_gui.formats import (
    AUDIO_FORMATS,
    FORMAT_KEYS,
    FORMAT_SPECS,
    MP3_BITRATES,
    VIDEO_CONTAINERS,
    VIDEO_RESOLUTIONS,
    ResolvedExtensionFormat,
    build_720p_spec,
    build_best_spec,
    resolve_extension_format,
)

_DEFAULTS = {
    "default_resolution": "720",
    "default_audio_format": "mp3",
    "default_mp3_bitrate": "192",
}


@pytest.mark.parametrize(
    "container, expected",
    [
        (
            "mp4",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        ),
        ("mkv", "bestvideo+bestaudio/best"),
        (
            "webm",
            "bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best",
        ),
    ],
)
def test_build_best_spec(container: str, expected: str) -> None:
    assert build_best_spec(container) == expected


def test_build_best_spec_default_is_mp4() -> None:
    assert build_best_spec() == build_best_spec("mp4")


@pytest.mark.parametrize(
    "resolution, container, expected",
    [
        (
            "720",
            "mp4",
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=720]+bestaudio/best",
        ),
        (
            "1080",
            "mkv",
            "bestvideo[height<=1080]+bestaudio/best",
        ),
        (
            "1440",
            "webm",
            "bestvideo[height<=1440][ext=webm]+bestaudio[ext=webm]"
            "/bestvideo[height<=1440]+bestaudio/best",
        ),
    ],
)
def test_build_720p_spec(resolution: str, container: str, expected: str) -> None:
    assert build_720p_spec(resolution, container) == expected


def test_format_constants_match_spec() -> None:
    """docs/spec/features/download-formats.md と定数値が一致するか。"""
    assert FORMAT_KEYS == ["fmt_best_mp4", "fmt_720p", "fmt_mp3", "fmt_original"]
    # 音声のみフラグは fmt_mp3 のみ True
    assert {k: v[1] for k, v in FORMAT_SPECS.items()} == {
        "fmt_best_mp4": False,
        "fmt_720p": False,
        "fmt_mp3": True,
        "fmt_original": False,
    }
    assert VIDEO_RESOLUTIONS == ("480", "720", "1080", "1440", "2160")
    assert MP3_BITRATES == ("128", "192", "256", "320")
    assert AUDIO_FORMATS == ("mp3", "flac")
    assert VIDEO_CONTAINERS == ("mp4", "mkv", "webm")


# ── resolve_extension_format（ブラウザ拡張の形式指定オブジェクト） ──────────


def test_resolve_best_maps_to_best_mp4() -> None:
    r = resolve_extension_format({"kind": "best"}, **_DEFAULTS)
    assert r == ResolvedExtensionFormat(
        format_id="fmt_best_mp4",
        resolution="720",
        audio_format="mp3",
        mp3_bitrate="192",
    )


def test_resolve_resolution_uses_given_value() -> None:
    r = resolve_extension_format(
        {"kind": "resolution", "resolution": "1080"}, **_DEFAULTS
    )
    assert r is not None
    assert r.format_id == "fmt_720p"
    assert r.resolution == "1080"


def test_resolve_resolution_clamps_unknown_to_default() -> None:
    r = resolve_extension_format(
        {"kind": "resolution", "resolution": "9999"}, **_DEFAULTS
    )
    assert r is not None
    assert r.format_id == "fmt_720p"
    assert r.resolution == "720"  # 既定へフォールバック


def test_resolve_resolution_missing_uses_default() -> None:
    r = resolve_extension_format({"kind": "resolution"}, **_DEFAULTS)
    assert r is not None
    assert r.resolution == "720"


def test_resolve_audio_uses_given_format_and_bitrate() -> None:
    r = resolve_extension_format(
        {"kind": "audio", "audio_format": "mp3", "mp3_bitrate": "320"}, **_DEFAULTS
    )
    assert r == ResolvedExtensionFormat(
        format_id="fmt_mp3",
        resolution="720",
        audio_format="mp3",
        mp3_bitrate="320",
    )


def test_resolve_audio_flac() -> None:
    r = resolve_extension_format(
        {"kind": "audio", "audio_format": "flac"}, **_DEFAULTS
    )
    assert r is not None
    assert r.format_id == "fmt_mp3"
    assert r.audio_format == "flac"


def test_resolve_audio_clamps_unknown_format_and_bitrate() -> None:
    r = resolve_extension_format(
        {"kind": "audio", "audio_format": "ogg", "mp3_bitrate": "999"}, **_DEFAULTS
    )
    assert r is not None
    assert r.audio_format == "mp3"  # 既定
    assert r.mp3_bitrate == "192"  # 既定


@pytest.mark.parametrize(
    "fmt",
    [
        None,
        {},  # kind 欠落
        {"kind": "app_default"},
        {"kind": "original"},  # 拡張からは指定不可
        {"kind": "unknown"},
        "fmt_mp3",  # dict 以外
        ["best"],
        42,
    ],
)
def test_resolve_returns_none_for_app_default_or_invalid(fmt: object) -> None:
    assert resolve_extension_format(fmt, **_DEFAULTS) is None
