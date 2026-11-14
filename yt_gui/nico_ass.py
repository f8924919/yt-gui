"""ニコニコ動画のコメントを ASS 字幕の文字列に変換する（#387）。

Web 表示の再現 OSS niconicomments（参照コミット `899203436285`）の HTML5 描画の式・
定数・色表を移植したもの。移植した式・定数・色表の著作権表示と許諾表示は
`NICONICOMMENTS_LICENSE` に全文を持つ。定数ごとに移植元のファイルと行（コメントの
`ts:` 以降）を注記する。設計は docs/arch/nico_ass.md。
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
import struct
import unicodedata
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, NamedTuple, Protocol

NICONICOMMENTS_LICENSE: str = """MIT License

Copyright (c) 2022 xpadev-net

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


# ---------------------------------------------------------------------------
# 型
# ---------------------------------------------------------------------------


class FontFace(NamedTuple):
    name: str
    weight: int


class FontMetrics(NamedTuple):
    ascent: float
    descent: float


class Command(NamedTuple):
    loc: str
    size: str
    color: str
    font: str
    long: int
    live: bool
    invisible: bool


class Measured(NamedTuple):
    char_size: float
    line_height: float
    font_px: float
    scale: float
    line_widths: list[int]
    width: float
    height: float


class LayoutItem(NamedTuple):
    loc: str
    vpos: int
    long: int
    width: float
    height: float
    commands: tuple[str, ...]


class ConvertResult(NamedTuple):
    ass: str
    skipped: int


class _Rng(Protocol):
    def random(self) -> float: ...


# 測定器: (テキスト, フォント名, 太さ, size_px[CSS の em]) -> 送り幅[px]
Measure = Callable[[str, str, int, float], float]
# 寸法: (フォント名, 太さ) -> FontMetrics | None
MetricsFn = Callable[[str, int], FontMetrics | None]


# ---------------------------------------------------------------------------
# 定数（移植元の値。実測値は書かない）
# ---------------------------------------------------------------------------

# ts: utils/comment.ts:47（RE_LONG）, :54（RE_COLOR_CODE）
_RE_LONG = re.compile(r"[@＠]([0-9.]+)")
_RE_COLOR_CODE = re.compile(r"#(?:[0-9a-z]{3}|[0-9a-z]{6})")
_RE_HEX_COLOR = re.compile(r"#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})")
_RE_LONE_SURROGATE = re.compile("[\ud800-\udfff]")

# ts: utils/comment.ts:55（DEFAULT_COMMENT_LONG）, :57（MAX_COMMENT_LONG）,
#     :66-67（MAX_PARSED_COMMAND_MAIL_ENTRIES / _CHARS）
_DEFAULT_LONG = 300
_MAX_LONG = 120 * 100
_MAX_COMMANDS = 64
_MAX_COMMAND_CHARS = 128

# ts: definition/colors.ts（色名 27 色）
_COLORS: dict[str, str] = {
    "white": "#FFFFFF",
    "red": "#FF0000",
    "pink": "#FF8080",
    "orange": "#FFC000",
    "yellow": "#FFFF00",
    "green": "#00FF00",
    "cyan": "#00FFFF",
    "blue": "#0000FF",
    "purple": "#C000FF",
    "black": "#000000",
    "white2": "#CCCC99",
    "niconicowhite": "#CCCC99",
    "red2": "#CC0033",
    "truered": "#CC0033",
    "pink2": "#FF33CC",
    "orange2": "#FF6600",
    "passionorange": "#FF6600",
    "yellow2": "#999900",
    "madyellow": "#999900",
    "green2": "#00CC66",
    "elementalgreen": "#00CC66",
    "cyan2": "#00CCCC",
    "blue2": "#3399FF",
    "marinblue": "#3399FF",
    "purple2": "#6633CC",
    "nobleviolet": "#6633CC",
    "black2": "#666666",
}

_LOCS = ("naka", "ue", "shita")
_SIZES = ("big", "medium", "small")
_FONTS = ("defont", "gothic", "mincho")
_FLASH_FONTS = ("gulim", "simsun")  # defont の枠を取り、defont として描く

# ts: definition/initConfig.ts:74（commentStageSize.html5: width 512 / height 384）
_STAGE_WIDTH = 512
_STAGE_HEIGHT = 384
# ts: definition/initConfig.ts:66（commentScale.html5 = 1920 / 683）
_COMMENT_SCALE = 1920 / 683
# ts: definition/initConfig.ts:124-（html5LineCounts）
_DEFAULT_LINE_COUNT = {"big": 8.4, "medium": 13.1, "small": 21}
_DOUBLE_RESIZED_LINE_COUNT = {"big": 7.8, "medium": 11.3, "small": 16.6}
# ts: definition/initConfig.ts:150（html5MinFontSize）
_MIN_FONT_SIZE = 10
# ts: comments/HTML5Comment.ts:32-33
_MAX_RESIZE_ITERATIONS = 20
_MIN_RESIZE_CHAR_SIZE = 1e-6
# ts: comments/HTML5Comment.ts:34-35（MAX_HTML5_COMMENT_CHARS / _LINES）
_MAX_COMMENT_CHARS = 16_384
_MAX_COMMENT_LINES = 256

# ts: definition/initConfig.ts:179-205, :339
_CANVAS_W = 1920
_CANVAS_H = 1080
_DRAW_RANGE = 1530
_DRAW_PADDING = 195
_COLLISION_RIGHT = 1685
_COLLISION_LEFT = 235
_COLLISION_PADDING = 5
_SPEED_OFFSET = 0.95
# ts: utils/comment.ts:214（MOVABLE_COLLISION_BUCKET_SIZE）
_BUCKET_SIZE = 100

# ts: definition/initConfig.ts:42-58（枠線の透明度・_live の透明度・線の太さ）
_STROKE_OPACITY = 0.4
_LIVE_OPACITY = 0.5
_LINE_WIDTH = 2.8
# ts: comments/HTML5Comment.ts:451, :532（_generateTextImage の -0.16）
_BASELINE_SHIFT = 0.16

# arch の「行の置き方」: 寸法が無いとき（#372 の比率 0.09 から導く）
_FALLBACK_METRICS = FontMetrics(ascent=1.0, descent=0.280625)

# arch の「フォント」: 「英字」は U+0000〜U+024F
_LATIN_MAX = 0x24F


# ---------------------------------------------------------------------------
# コマンド（ts: utils/comment.ts:1064-1183）
# ---------------------------------------------------------------------------


def _js_number(text: str) -> float:
    """`Number(text)` 相当（`[0-9.]+` だけが来る。読めなければ NaN）。"""
    try:
        return float(text)
    except ValueError:
        return math.nan


def _normalize_long(value: float | None) -> int:
    """ts: utils/comment.ts:126-155（normalizeCommentLong ほか）"""
    if value is None or not math.isfinite(value):
        return _DEFAULT_LONG
    scaled = value * 100
    if not math.isfinite(scaled) or scaled <= 0:
        return _DEFAULT_LONG
    return min(math.floor(scaled), _MAX_LONG) or _DEFAULT_LONG


def parse_commands(commands: Sequence[str], body: str, is_premium: bool) -> Command:
    loc: str | None = None
    size: str | None = None
    color: str | None = None
    font: str | None = None
    long_value: float | None = None
    live = False
    invisible = False
    for raw in commands[:_MAX_COMMANDS]:
        if len(raw) > _MAX_COMMAND_CHARS:
            continue
        command = raw.lower()
        if command.startswith("nico:"):
            continue
        m = _RE_LONG.match(command)
        if m:
            long_value = _js_number(m.group(1))
            continue
        if command in _LOCS:
            if loc is None:
                loc = command
            continue
        if size is None and command in _SIZES:
            size = command
            continue
        if command in _COLORS:
            if color is None:
                color = _COLORS[command]
            continue
        if is_premium and _RE_COLOR_CODE.fullmatch(command):
            if color is None:
                color = command.upper()
            continue
        if command in _FONTS or command in _FLASH_FONTS:
            if font is None:
                font = "defont" if command in _FLASH_FONTS else command
            continue
        if command == "_live":
            live = True
        elif command == "invisible":
            invisible = True
    if body.startswith("/"):
        invisible = True
    return Command(
        loc=loc or "naka",
        size=size or "medium",
        color=color or "#FFFFFF",
        font=font or "defont",
        long=_normalize_long(long_value),
        live=live,
        invisible=invisible,
    )


def ass_color(color: str) -> str:
    """`#RRGGBB` / `#RGB` を ASS の `&HBBGGRR&` にする。読めない値は白。"""
    if not _RE_HEX_COLOR.fullmatch(color):
        return "&HFFFFFF&"
    digits = color[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return f"&H{digits[4:6]}{digits[2:4]}{digits[0:2]}&".upper()


# ---------------------------------------------------------------------------
# 文字サイズ（ts: utils/niconico.ts:24-60, :216-）
# ---------------------------------------------------------------------------


def char_size(size: str) -> float:
    return _STAGE_HEIGHT / _DOUBLE_RESIZED_LINE_COUNT[size]


def line_height(size: str) -> float:
    base = _STAGE_HEIGHT / _DOUBLE_RESIZED_LINE_COUNT[size]
    return (_STAGE_HEIGHT - base) / (_DEFAULT_LINE_COUNT[size] - 1)


def font_size_and_scale(size: float) -> tuple[int, float]:
    """`getFontSizeAndScale`: 文字サイズ（舞台）から (CSS の font-size, 縮小率)。"""
    scaled = size * 0.8
    if scaled < _MIN_FONT_SIZE:
        if scaled >= 1:
            scaled = math.floor(scaled)
        return _MIN_FONT_SIZE, scaled / _MIN_FONT_SIZE
    return math.floor(scaled), 1


# ---------------------------------------------------------------------------
# フォント（arch の「フォント」）
# ---------------------------------------------------------------------------


def font_candidates(font: str, platform: str) -> tuple[FontFace, ...]:
    if platform == "windows":
        if font == "gothic":
            return (FontFace("Yu Gothic", 400),)
        if font == "mincho":
            return (FontFace("Yu Mincho", 400),)
        return (FontFace("Arial", 600), FontFace("MS PGothic", 600))
    if platform == "macos":
        if font == "gothic":
            return (FontFace("YuGothic", 400),)
        if font == "mincho":
            return (FontFace("YuMincho", 400),)
        return (FontFace("Hiragino Sans", 600),)
    if font == "gothic":
        return (FontFace("sans-serif", 400),)
    if font == "mincho":
        return (FontFace("serif", 400),)
    return (FontFace("sans-serif", 600),)


def font_runs(text: str, font: str, platform: str) -> list[tuple[str, FontFace]]:
    candidates = font_candidates(font, platform)
    runs: list[tuple[str, FontFace]] = []
    for ch in text:
        face = (
            candidates[0]
            if len(candidates) == 1 or ord(ch) <= _LATIN_MAX
            else candidates[1]
        )
        if runs and runs[-1][1] == face:
            runs[-1] = (runs[-1][0] + ch, face)
        else:
            runs.append((ch, face))
    return runs


# ---------------------------------------------------------------------------
# 幅の測定と上下固定の縮小（ts: comments/HTML5Comment.ts:200-430）
# ---------------------------------------------------------------------------


def measure_comment(
    lines: Sequence[str],
    cmd: Command,
    *,
    platform: str,
    measure: Measure,
    font_scale: float,
) -> Measured:
    lines_runs = [font_runs(line, cmd.font, platform) for line in lines]
    base_char = char_size(cmd.size)
    base_line_height = line_height(cmd.size)

    def widths_at(size: float) -> list[int]:
        font_px, scale = font_size_and_scale(size)
        return [
            math.ceil(
                sum(measure(t, f.name, f.weight, font_px) for t, f in runs) * scale
            )
            for runs in lines_runs
        ]

    cur_char = base_char
    cur_height = base_line_height
    widths = widths_at(cur_char)
    max_width = max(widths)
    if cmd.loc != "naka" and max_width * font_scale > _STAGE_WIDTH:
        cur_char, cur_height = _resize_x(
            lambda size: max(widths_at(size)),
            max_width,
            base_char,
            base_line_height,
            _STAGE_WIDTH / font_scale,
        )
        widths = widths_at(cur_char)
    font_px, scale = font_size_and_scale(cur_char)
    c = _COMMENT_SCALE * font_scale
    return Measured(
        char_size=cur_char,
        line_height=cur_height,
        font_px=font_px,
        scale=scale,
        line_widths=widths,
        width=max(widths) * c,
        height=(cur_height * (len(lines) - 1) + cur_char) * c,
    )


def _resize_x(
    max_width_at: Callable[[float], float],
    width: float,
    char0: float,
    line_height0: float,
    limit: float,
) -> tuple[float, float]:
    """ts: `_processResizeX`。複数行の縮小（resizedY）は扱わない。

    戻り値は (文字サイズ, 行高)。幅は文字サイズだけで決まる。
    """
    ratio = limit / width
    current_char = max(_MIN_RESIZE_CHAR_SIZE, char0)
    current_height = max(_MIN_RESIZE_CHAR_SIZE, line_height0)
    raw_char = current_char * ratio
    raw_height = current_height * ratio
    base_char = max(_MIN_RESIZE_CHAR_SIZE, raw_char)
    base_height = max(_MIN_RESIZE_CHAR_SIZE, raw_height)
    legacy_char = max(1, raw_char)
    legacy_height = max(1, raw_height)

    if base_char >= 1:
        resized_char = legacy_char
        resized_height = legacy_height
        result = max_width_at(resized_char)
        if result > limit:
            remaining = _MAX_RESIZE_ITERATIONS
            while result > limit and resized_char > 1 and remaining > 0:
                remaining -= 1
                original = resized_char
                resized_char = max(1, resized_char - 1)
                resized_height *= resized_char / original
                result = max_width_at(resized_char)
        else:
            last_char = resized_char
            last_height = resized_height
            remaining = _MAX_RESIZE_ITERATIONS
            while result < limit and remaining > 0:
                remaining -= 1
                last_char = resized_char
                last_height = resized_height
                original = resized_char
                resized_char += 1
                resized_height *= resized_char / original
                result = max_width_at(resized_char)
            resized_char = last_char
            resized_height = last_height
        return resized_char, resized_height

    def measured_at(next_char: float) -> float:
        return max_width_at(max(_MIN_RESIZE_CHAR_SIZE, next_char))

    best = base_char
    if measured_at(base_char) > limit:
        low = _MIN_RESIZE_CHAR_SIZE
        high = base_char
        remaining = _MAX_RESIZE_ITERATIONS
        best = low
        if measured_at(low) <= limit:
            while remaining > 0:
                remaining -= 1
                if not low < high:
                    break
                candidate = (low + high) / 2
                if measured_at(candidate) <= limit:
                    best = candidate
                    low = candidate
                else:
                    high = candidate
    else:
        low = base_char
        high = current_char
        remaining = _MAX_RESIZE_ITERATIONS
        while remaining > 0:
            remaining -= 1
            if not low < high:
                break
            mid = (low + high) / 2
            if measured_at(mid) <= limit:
                best = mid
                low = mid
            else:
                high = mid
    return best, base_height * (best / base_char)


# ---------------------------------------------------------------------------
# 速さと横位置（ts: utils/comment.ts:1566-1590 getPosX）
# ---------------------------------------------------------------------------


def naka_speed(width: float, long: int) -> float:
    return (_DRAW_RANGE + width * _SPEED_OFFSET) / (long + 100)


def naka_x(width: float, long: int, elapsed: float) -> float:
    return _DRAW_PADDING + _DRAW_RANGE - (elapsed + 100) * naka_speed(width, long)


# ---------------------------------------------------------------------------
# 配置（ts: utils/comment.ts:214-446, :1312-1564）
# ---------------------------------------------------------------------------


def _js_round(x: float) -> int:
    return math.floor(x + 0.5)


def layout(items: Sequence[LayoutItem], rng: _Rng) -> list[float]:
    """niconicomments の衝突判定で各コメントのキャンバスの `posY` を決める。"""
    count = len(items)
    pos_y: list[float] = [0.0] * count
    fixed_collision: dict[str, dict[int, list[int]]] = {"ue": {}, "shita": {}}
    right: dict[int, list[int]] = {}
    left: dict[int, list[int]] = {}
    buckets: dict[int, list[int]] = {}
    durations: set[int] = set()
    # 移動コメントごとの派生値（登録時に求める）
    before_of: dict[int, int] = {}
    speed_of: dict[int, float] = {}
    range_of: dict[int, tuple[int, int]] = {}
    coll_range_of: dict[int, tuple[float, float]] = {}
    initial_left = _DRAW_PADDING + _DRAW_RANGE

    def get_pos_y(
        current: float, idx: int, collision: list[int] | None
    ) -> tuple[float, bool, bool]:
        if not collision:
            return current, False, False
        changed = False
        target_height = items[idx].height
        while True:
            for other in collision:
                if other == idx or pos_y[other] < 0:
                    continue
                other_y = pos_y[other]
                other_bottom = other_y + items[other].height
                if current < other_bottom and current + target_height > other_y:
                    current = other_bottom
                    changed = True
                    if current + target_height > _CANVAS_H:
                        if target_height > _CANVAS_H:
                            current = (
                                (target_height - _CANVAS_H) / -2
                                if "naka" in items[idx].commands
                                else 0
                            )
                        else:
                            current = math.floor(
                                rng.random() * (_CANVAS_H - target_height)
                            )
                        return current, True, True
                    break
            else:
                return current, changed, False

    def fixed_pos_y(idx: int) -> float:
        item = items[idx]
        collision = fixed_collision[item.loc]
        y: float = 0
        changed = True
        passes = 0
        while changed and passes < 10:
            changed = False
            passes += 1
            for j in range(item.long):
                y, did_change, did_break = get_pos_y(
                    y, idx, collision.get(item.vpos + j)
                )
                changed = changed or did_change
                if did_break:
                    break
        return y

    def collision_range(idx: int) -> tuple[float, float]:
        item = items[idx]
        speed = speed_of[idx]
        active_start, active_end = range_of[idx]
        return (
            max(
                active_start,
                item.vpos - 100 + (initial_left - _COLLISION_RIGHT) / speed,
            ),
            min(
                active_end,
                item.vpos
                - 100
                + (initial_left + item.width + _COLLISION_PADDING - _COLLISION_LEFT)
                / speed,
            ),
        )

    def trajectories_intersect(
        idx: int, comment_range: tuple[float, float], cand: int
    ) -> bool:
        item = items[idx]
        candidate = items[cand]
        speed = speed_of[idx]
        cand_speed = speed_of[cand]
        cand_start, cand_end = coll_range_of[cand]
        shared_start = max(comment_range[0], cand_start)
        shared_end = min(comment_range[1], cand_end)
        if shared_start >= shared_end:
            return False

        def relative(vpos: float) -> float:
            return (vpos - item.vpos + 100) * speed - (
                vpos - candidate.vpos + 100
            ) * cand_speed

        at_start = relative(shared_start)
        at_end = relative(shared_end)
        return min(at_start, at_end) <= item.width + _COLLISION_PADDING and max(
            at_start, at_end
        ) >= -(candidate.width + _COLLISION_PADDING)

    def analytic_candidates(idx: int) -> list[int] | None:
        item = items[idx]
        if not durations:
            return None
        if len(durations) == 1 and item.long in durations:
            return None
        comment_range = collision_range(idx)
        active_start, active_end = range_of[idx]
        seen: set[int] = set()
        candidates: list[int] = []
        first = math.floor(active_start / _BUCKET_SIZE)
        last = math.floor((active_end - 1) / _BUCKET_SIZE)
        for bucket in range(first, last + 1):
            for cand in buckets.get(bucket, ()):
                if cand in seen or cand == idx or items[cand].long == item.long:
                    continue
                seen.add(cand)
                if trajectories_intersect(idx, comment_range, cand):
                    candidates.append(cand)
        return candidates

    def movable_pos_y(idx: int) -> float:
        item = items[idx]
        if item.height > _CANVAS_H:
            return (item.height - _CANVAS_H) / -2
        before = before_of[idx]
        speed = speed_of[idx]
        end = item.long + 125
        candidates = analytic_candidates(idx)
        y: float = 0
        changed = True
        passes = 0
        last_updated: int | None = None
        while changed and passes < 10:
            changed = False
            passes += 1
            y, did_change, did_break = get_pos_y(y, idx, candidates)
            changed = changed or did_change
            if did_break:
                return y
            for j in range(before, end, 5):
                vpos = item.vpos + j
                left_pos = _DRAW_PADDING + _DRAW_RANGE - (j + 100) * speed
                is_break = False
                if last_updated is not None and last_updated == vpos:
                    return y
                if (
                    left_pos + item.width >= _COLLISION_RIGHT
                    and left_pos <= _COLLISION_RIGHT
                ):
                    y, did_change, did_break = get_pos_y(y, idx, right.get(vpos))
                    changed = changed or did_change
                    if did_change:
                        last_updated = vpos
                    is_break = is_break or did_break
                if (
                    left_pos + item.width >= _COLLISION_LEFT
                    and left_pos <= _COLLISION_LEFT
                ):
                    y, did_change, did_break = get_pos_y(y, idx, left.get(vpos))
                    changed = changed or did_change
                    if did_change:
                        last_updated = vpos
                    is_break = is_break or did_break
                if is_break:
                    return y
        return y

    for idx, item in enumerate(items):
        if item.loc == "naka":
            speed = naka_speed(item.width, item.long)
            before = _js_round(-288 / ((1632 + item.width) / (item.long + 125))) - 100
            before_of[idx] = before
            speed_of[idx] = speed
            range_of[idx] = (item.vpos + before, item.vpos + item.long + 125)
            coll_range_of[idx] = collision_range(idx)
            y = movable_pos_y(idx)
            end = item.long + 125
            for j in range(before, end):
                vpos = item.vpos + j
                left_pos = _DRAW_PADDING + _DRAW_RANGE - (j + 100) * speed
                if (
                    left_pos + item.width + _COLLISION_PADDING >= _COLLISION_RIGHT
                    and left_pos <= _COLLISION_RIGHT
                ):
                    right.setdefault(vpos, []).append(idx)
                if (
                    left_pos + item.width + _COLLISION_PADDING >= _COLLISION_LEFT
                    and left_pos <= _COLLISION_LEFT
                ):
                    left.setdefault(vpos, []).append(idx)
            pos_y[idx] = y
            durations.add(item.long)
            active_start, active_end = range_of[idx]
            for bucket in range(
                math.floor(active_start / _BUCKET_SIZE),
                math.floor((active_end - 1) / _BUCKET_SIZE) + 1,
            ):
                buckets.setdefault(bucket, []).append(idx)
        else:
            y = fixed_pos_y(idx)
            collision = fixed_collision[item.loc]
            collision_end = max(item.long - 20, 0)
            for j in range(min(item.long, collision_end + 1)):
                collision.setdefault(item.vpos + j, []).append(idx)
            pos_y[idx] = y
    return pos_y


# ---------------------------------------------------------------------------
# 測定器と寸法（arch の「公開する関数」）
# ---------------------------------------------------------------------------


def approx_measurer(text: str, font_name: str, weight: int, size_px: float) -> float:
    return sum(
        size_px if unicodedata.east_asian_width(ch) in ("F", "W") else size_px / 2
        for ch in text
    )


def _no_metrics(font_name: str, weight: int) -> FontMetrics | None:
    return None


# フォント名 -> {太さ: ファイル名の候補}（arch の「フォント」）
_WINDOWS_FONT_FILES: dict[str, dict[int, list[str]]] = {
    "Arial": {600: ["arialbd.ttf"]},
    "MS PGothic": {600: ["msgothic.ttc"]},
    "Yu Gothic": {400: ["YuGothR.ttc"]},
    "Yu Mincho": {400: ["yumin.ttf"]},
}
_MACOS_FONT_FILES: dict[str, dict[int, list[str]]] = {
    "Hiragino Sans": {600: ["ヒラギノ角ゴシック W6.ttc"]},
    "YuGothic": {400: ["YuGothic-Medium.otf", "游ゴシック体.ttc"]},
    "YuMincho": {400: ["YuMincho-Medium.otf", "游明朝体.ttc"]},
}
_MAX_FACE_INDEX = 32


def _font_dirs(platform: str) -> list[str]:
    if platform == "windows":
        return [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
    if platform == "macos":
        return [
            "/System/Library/Fonts",
            "/Library/Fonts",
            "/System/Library/Fonts/Supplemental",
        ]
    return []


def _font_files(platform: str, name: str, weight: int) -> list[str]:
    table = _WINDOWS_FONT_FILES if platform == "windows" else _MACOS_FONT_FILES
    return table.get(name, {}).get(weight, [])


def _resolve_font(platform: str, name: str, weight: int) -> tuple[str, int] | None:
    """(ファイルのパス, フェイスの index)。無い・開けないときは None。"""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for directory in _font_dirs(platform):
        for filename in _font_files(platform, name, weight):
            path = os.path.join(directory, filename)
            if not os.path.isfile(path):
                continue
            if not path.lower().endswith(".ttc"):
                return path, 0
            for index in range(_MAX_FACE_INDEX):
                try:
                    family = ImageFont.truetype(path, 100, index=index).getname()[0]
                except OSError:
                    break
                if family == name:
                    return path, index
    return None


@functools.cache
def pillow_measurer(platform: str) -> Measure:
    try:
        from PIL import ImageFont
    except ImportError:
        return approx_measurer
    if platform not in ("windows", "macos"):
        return approx_measurer

    fonts: dict[tuple[str, int], Any] = {}

    def load(name: str, weight: int) -> Any:
        key = (name, weight)
        if key not in fonts:
            font = None
            resolved = _resolve_font(platform, name, weight)
            if resolved is not None:
                try:
                    font = ImageFont.truetype(resolved[0], 100, index=resolved[1])
                except OSError:
                    font = None
            fonts[key] = font
        return fonts[key]

    @functools.lru_cache(maxsize=65536)
    def length_at_100(text: str, name: str, weight: int) -> float | None:
        font = load(name, weight)
        if font is None:
            return None
        try:
            return float(font.getlength(text))
        except OSError, ValueError:
            return None

    def measure(text: str, font_name: str, weight: int, size_px: float) -> float:
        length = length_at_100(text, font_name, weight)
        if length is None:
            return approx_measurer(text, font_name, weight, size_px)
        return length * size_px / 100

    return measure


def _read_vertical_metrics(path: str, index: int) -> FontMetrics | None:
    """sfnt の `head` の unitsPerEm と `OS/2` の usWinAscent / usWinDescent を読む。"""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            offset = 0
            if header[:4] == b"ttcf":
                (num_fonts,) = struct.unpack(">I", header[8:12])
                if not 0 <= index < num_fonts:
                    return None
                f.seek(12 + 4 * index)
                (offset,) = struct.unpack(">I", f.read(4))
            f.seek(offset + 4)
            (num_tables,) = struct.unpack(">H", f.read(2))
            f.seek(offset + 12)
            tables: dict[bytes, int] = {}
            for _ in range(num_tables):
                tag, _checksum, table_offset, _length = struct.unpack(
                    ">4sIII", f.read(16)
                )
                tables[tag] = table_offset
            if b"head" not in tables or b"OS/2" not in tables:
                return None
            f.seek(tables[b"head"] + 18)
            (units_per_em,) = struct.unpack(">H", f.read(2))
            f.seek(tables[b"OS/2"] + 74)
            win_ascent, win_descent = struct.unpack(">HH", f.read(4))
    except OSError, struct.error:
        return None
    if units_per_em == 0:
        return None
    return FontMetrics(win_ascent / units_per_em, win_descent / units_per_em)


@functools.cache
def font_metrics(platform: str) -> MetricsFn:
    try:
        from PIL import ImageFont as _  # noqa: F401
    except ImportError:
        return _no_metrics
    if platform not in ("windows", "macos"):
        return _no_metrics

    cache: dict[tuple[str, int], FontMetrics | None] = {}

    def metrics(font_name: str, weight: int) -> FontMetrics | None:
        key = (font_name, weight)
        if key not in cache:
            resolved = _resolve_font(platform, font_name, weight)
            cache[key] = None if resolved is None else _read_vertical_metrics(*resolved)
        return cache[key]

    return metrics


# ---------------------------------------------------------------------------
# 変換
# ---------------------------------------------------------------------------


class _Row(NamedTuple):
    vpos: int
    posted: int
    body: str
    commands: list[str]
    premium: bool


def _parse_posted(value: str) -> int | None:
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        seconds = math.floor(moment.timestamp())
    except ValueError, OverflowError, OSError:
        return None
    return seconds if seconds >= 0 else None


def _parse_row(entry: object) -> _Row | None:
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    commands = entry.get("commands")
    vpos_ms = entry.get("vposMs")
    premium = entry.get("isPremium")
    posted_at = entry.get("postedAt")
    if not isinstance(body, str):
        return None
    if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
        return None
    if isinstance(vpos_ms, bool) or not isinstance(vpos_ms, int | float):
        return None
    if not isinstance(premium, bool) or not isinstance(posted_at, str):
        return None
    if isinstance(vpos_ms, float):
        if not math.isfinite(vpos_ms):
            return None
        vpos = math.floor(vpos_ms / 10)
    else:
        vpos = vpos_ms // 10
    posted = _parse_posted(posted_at)
    if posted is None:
        return None
    # 対になっていないサロゲート（JSON の `\udXXX`）は UTF-8 に書けないので置き換える
    body = _RE_LONE_SURROGATE.sub("�", body)
    return _Row(vpos, posted, body, commands, premium)


def _body_lines(body: str) -> list[str]:
    """ts: comments/HTML5Comment.ts:48-62（clampHTML5Content）。CR は落とす。"""
    text = body.replace(chr(13), "")[:_MAX_COMMENT_CHARS]
    return text.split(chr(10))[:_MAX_COMMENT_LINES]


def _num(value: float) -> str:
    text = f"{value:.2f}"
    text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _ass_time(centiseconds: int) -> str:
    centiseconds = max(centiseconds, 0)
    hours, rest = divmod(centiseconds, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "＼")
        .replace("{", "｛")
        .replace("}", "｝")
        .replace(" ", "\\h")
    )


def _alpha(opacity: float) -> str:
    value = min(max(math.floor(255 * (1 - opacity) + 0.5), 0), 255)
    return f"&H{value:02X}&"


_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding"
)
_STYLE = (
    "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
    "0,0,0,0,100,100,0,0,1,2,0,7,0,0,0,1"
)
_HEADER = """[Script Info]
; Generated by yt-gui (nico_ass)
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
{style_format}
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


class _Placed(NamedTuple):
    cmd: Command
    lines: list[str]
    measured: Measured
    vpos: int


def convert(
    comments_json: str,
    *,
    width: int,
    height: int,
    font_scale_percent: int,
    opacity: float,
    platform: str,
    measure: Measure,
    metrics: MetricsFn,
    rng: _Rng,
) -> ConvertResult:
    data = json.loads(comments_json)
    if not isinstance(data, list):
        raise ValueError("コメントの JSON がリストではない")
    font_scale = font_scale_percent / 100
    if font_scale <= 0:
        raise ValueError("font_scale_percent が 0 以下")

    rows: list[_Row] = []
    skipped = 0
    for entry in data:
        row = _parse_row(entry)
        if row is None:
            skipped += 1
        else:
            rows.append(row)
    rows.sort(key=lambda r: (r.vpos, r.posted))

    placed: list[_Placed] = []
    items: list[LayoutItem] = []
    for row in rows:
        cmd = parse_commands(row.commands, row.body, row.premium)
        if cmd.invisible:
            continue
        lines = _body_lines(row.body)
        measured = measure_comment(
            lines, cmd, platform=platform, measure=measure, font_scale=font_scale
        )
        placed.append(_Placed(cmd, lines, measured, row.vpos))
        items.append(
            LayoutItem(
                cmd.loc,
                row.vpos,
                cmd.long,
                measured.width,
                measured.height,
                tuple(row.commands),
            )
        )
    positions = layout(items, rng)

    base_height = width * 9 / 16 if height > width else height
    k = base_height / _CANVAS_H
    offset_x = (width - _CANVAS_W * k) / 2
    offset_y = (height - _CANVAS_H * k) / 2
    c = _COMMENT_SCALE * font_scale
    metrics_cache: dict[tuple[str, int], FontMetrics] = {}

    def face_metrics(face: FontFace) -> FontMetrics:
        key = (face.name, face.weight)
        if key not in metrics_cache:
            metrics_cache[key] = metrics(face.name, face.weight) or _FALLBACK_METRICS
        return metrics_cache[key]

    out = [_HEADER.format(w=width, h=height, style_format=_STYLE_FORMAT, style=_STYLE)]
    for place, pos in zip(placed, positions, strict=True):
        cmd, m = place.cmd, place.measured
        fill_opacity = opacity * (_LIVE_OPACITY if cmd.live else 1)
        stroke_opacity = opacity * _STROKE_OPACITY * (_LIVE_OPACITY if cmd.live else 1)
        stroke_color = "&HFFFFFF&" if cmd.color == "#000000" else "&H000000&"
        bord = _LINE_WIDTH * _COMMENT_SCALE * m.scale / 2 * k
        style_tags = (
            f"\\bord{_num(bord)}\\c{ass_color(cmd.color)}\\3c{stroke_color}"
            f"\\1a{_alpha(fill_opacity)}\\3a{_alpha(stroke_opacity)}"
        )
        top = _CANVAS_H - pos - m.height if cmd.loc == "shita" else pos
        em = m.font_px * m.scale * c
        left = (_CANVAS_W - m.width) / 2

        if cmd.loc == "naka":
            speed = naka_speed(m.width, cmd.long)
            right_edge = (width / k + _CANVAS_W) / 2
            left_edge = (_CANVAS_W - width / k) / 2
            t1 = (_DRAW_PADDING + _DRAW_RANGE - right_edge) / speed - 100
            t2 = (_DRAW_PADDING + _DRAW_RANGE + m.width - left_edge) / speed - 100
            start = max(place.vpos + math.floor(t1), 0)
            end = place.vpos + math.ceil(t2)
            x1 = naka_x(m.width, cmd.long, start - place.vpos)
            x2 = naka_x(m.width, cmd.long, end - place.vpos)
        else:
            start = max(place.vpos, 0)
            end = place.vpos + cmd.long
        if end <= start:
            continue

        for i, line in enumerate(place.lines):
            runs = font_runs(line, cmd.font, platform)
            if not runs:
                continue
            baseline = (
                top
                + (
                    m.line_height * (i + 1)
                    + (m.char_size - m.line_height) / 2
                    - _BASELINE_SHIFT * m.line_height
                )
                * c
            )
            all_metrics = [face_metrics(face) for _, face in runs]
            if cmd.loc == "shita":
                anchor = "\\an2"
                y = baseline + em * max(fm.descent for fm in all_metrics)
            else:
                anchor = "\\an8" if cmd.loc == "ue" else "\\an7"
                y = baseline - em * max(fm.ascent for fm in all_metrics)
            py = offset_y + k * y
            if cmd.loc == "naka":
                move = (
                    f"\\move({_num(offset_x + k * x1)},{_num(py)},"
                    f"{_num(offset_x + k * x2)},{_num(py)})"
                )
                position = move
            else:
                x = left + m.line_widths[i] * c / 2
                position = f"\\pos({_num(offset_x + k * x)},{_num(py)})"
            text = f"{{{anchor}{position}\\b{runs[0][1].weight}{style_tags}}}"
            for (run_text, face), fm in zip(runs, all_metrics, strict=True):
                size = em * k * (fm.ascent + fm.descent)
                text += f"{{\\fn{face.name}\\fs{_num(size)}}}{_escape(run_text)}"
            times = f"{_ass_time(start)},{_ass_time(end)}"
            out.append(f"Dialogue: 0,{times},Default,,0,0,0,,{text}\n")
    return ConvertResult("".join(out), skipped)
