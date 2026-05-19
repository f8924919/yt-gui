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
    build_720p_spec,
    build_best_spec,
)


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
