"""yt_gui.utils のテスト。

対応する仕様/実装: yt_gui/utils.py (ANSI エスケープシーケンスの除去)。
"""

import pytest

from yt_gui.utils import strip_ansi


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\x1b[31mERROR\x1b[0m: failed", "ERROR: failed"),
        ("plain text", "plain text"),
        ("", ""),
    ],
    ids=["with_ansi_codes", "no_ansi_codes", "empty"],
)
def test_strip_ansi(raw: str, expected: str) -> None:
    assert strip_ansi(raw) == expected
