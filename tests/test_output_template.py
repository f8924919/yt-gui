"""yt_gui.output_template のテスト。

対応仕様: docs/spec/screens/settings-dialog.md (ファイル名タブ),
docs/spec/features/download-behavior.md (OUTPUT TEMPLATE)。
"""

import pytest

from yt_gui.output_template import (
    DEFAULT_PLAYLIST_TEMPLATE,
    DEFAULT_VIDEO_TEMPLATE,
    render_preview,
    validate_template,
)


def test_render_preview_expands_sample_info() -> None:
    result = render_preview(DEFAULT_PLAYLIST_TEMPLATE)
    assert result == "My Playlist/001 - Sample Video.mp4"


def test_render_preview_returns_none_for_invalid_syntax() -> None:
    # %( で始まり ) が無い -> % 演算でエラー
    assert render_preview("%(title.%(ext)s") is None


@pytest.mark.parametrize(
    "template, expected",
    [
        (DEFAULT_VIDEO_TEMPLATE, None),
        ("", "warn_template_invalid"),
        ("   ", "warn_template_invalid"),
        ("%(title)s.mp4", "warn_template_no_ext"),
        ("%(title.%(ext)s", "warn_template_invalid"),
    ],
    ids=["valid", "empty", "whitespace_only", "missing_ext", "invalid_syntax"],
)
def test_validate_template(template: str, expected: str | None) -> None:
    assert validate_template(template) == expected
