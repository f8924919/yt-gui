import re

from yt_dlp.utils import parse_duration

_ANSI_ESC = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return _ANSI_ESC.sub("", text)


def parse_time_to_seconds(text: str | None) -> float | None:
    """`HH:MM:SS` / `MM:SS` / 秒数の時刻文字列を秒へ変換する。

    解釈できない・空文字のときは `None` を返す。区間ダウンロードの入力検証で
    使う（変換そのものは downloader 側が `yt_dlp.utils.parse_duration` で行う）。
    """
    if not text:
        return None
    seconds = parse_duration(text.strip())
    return float(seconds) if seconds is not None else None
