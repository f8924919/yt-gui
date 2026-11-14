"""yt_gui/nico_ass.py のテスト（#387）。

期待値は niconicomments（コミット 899203436285）の式から手で計算した数値で書く。
文字の幅は決定的な測定器（全角 1 em、半角 0.5 em）を注入し、Pillow に依存させない。
単位: 舞台（高さ 384）の値は stage、キャンバス（1920 × 1080）の値は canvas。
"""

from __future__ import annotations

import gzip
import json
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from yt_gui import nico_ass
from yt_gui.nico_ass import FontFace, FontMetrics, LayoutItem

DATA = Path(__file__).parent / "data"

# 1920 / 683（niconicomments の commentScale）
C0 = 2.8111273792093706


def fw_measure(text: str, font_name: str, weight: int, size_px: float) -> float:
    """全角 1 em、半角 0.5 em の決定的な測定器（テスト用）。"""
    return sum(
        size_px if unicodedata.east_asian_width(ch) in ("F", "W") else size_px / 2
        for ch in text
    )


FAKE_METRICS = {
    "Arial": FontMetrics(ascent=0.9, descent=0.2),
    "MS PGothic": FontMetrics(ascent=0.8, descent=0.2),
    "Yu Gothic": FontMetrics(ascent=1.0, descent=0.25),
    "Yu Mincho": FontMetrics(ascent=1.0, descent=0.25),
}


def fake_metrics(font_name: str, weight: int) -> FontMetrics | None:
    return FAKE_METRICS.get(font_name)


def no_metrics(font_name: str, weight: int) -> FontMetrics | None:
    return None


class ScriptedRng:
    """random() が決めた値を順に返し、引いた回数を数える。"""

    def __init__(self, values: list[float]) -> None:
        self.values = list(values)
        self.draws = 0

    def random(self) -> float:
        value = self.values[min(self.draws, len(self.values) - 1)]
        self.draws += 1
        return value


def row(
    body: str = "あ",
    commands: list[str] | None = None,
    vpos_ms: int = 10000,
    premium: bool = False,
    posted: str = "2020-01-01T00:00:00+09:00",
) -> dict:
    return {
        "body": body,
        "commands": commands if commands is not None else [],
        "vposMs": vpos_ms,
        "isPremium": premium,
        "postedAt": posted,
    }


def run(
    rows: list[Any],
    *,
    width: int = 1920,
    height: int = 1080,
    font_scale_percent: int = 100,
    opacity: float = 0.8,
    platform: str = "windows",
    metrics=fake_metrics,
    rng=None,
) -> nico_ass.ConvertResult:
    return nico_ass.convert(
        json.dumps(rows, ensure_ascii=False),
        width=width,
        height=height,
        font_scale_percent=font_scale_percent,
        opacity=opacity,
        platform=platform,
        measure=fw_measure,
        metrics=metrics,
        rng=rng if rng is not None else random.Random(0),
    )


def dialogues(ass: str) -> list[str]:
    return [line for line in ass.splitlines() if line.startswith("Dialogue:")]


def fields(dialogue: str) -> tuple[str, str, str]:
    """(開始, 終了, テキスト) を返す。"""
    parts = dialogue[len("Dialogue:") :].split(",", 9)
    return parts[1].strip(), parts[2].strip(), parts[9]


def tag_numbers(text: str, tag: str) -> list[float]:
    """`\\pos(…)` / `\\move(…)` の引数を数値で返す。"""
    m = re.search(r"\\" + tag + r"\(([^)]*)\)", text)
    assert m, f"\\{tag} がない: {text}"
    return [float(v) for v in m.group(1).split(",")]


def tag_value(text: str, tag: str) -> str:
    m = re.search(r"\\" + tag + r"(?![a-z])([^\\}]*)", text)
    assert m, f"\\{tag} がない: {text}"
    return m.group(1)


def runs_of(text: str) -> list[tuple[str, Any, str]]:
    """`{\\fn名前\\fsサイズ}本文` の区間を (名前, サイズ, 本文) で返す。"""
    return [
        (name, float(size), body)
        for name, size, body in re.findall(
            r"\{\\fn([^\\}]+)\\fs([0-9.]+)\}([^{]*)", text
        )
    ]


# ---------------------------------------------------------------------------
# parse_commands（C4 / C6 / C7 / C11）
# ---------------------------------------------------------------------------


def test_parse_commands_defaults():
    cmd = nico_ass.parse_commands([], "abc", False)
    assert (cmd.loc, cmd.size, cmd.color, cmd.font, cmd.long) == (
        "naka",
        "medium",
        "#FFFFFF",
        "defont",
        300,
    )
    assert (cmd.live, cmd.invisible) == (False, False)


def test_parse_commands_lowercases_before_matching():
    cmd = nico_ass.parse_commands(["UE", "BIG", "RED", "MINCHO"], "abc", False)
    assert (cmd.loc, cmd.size, cmd.color, cmd.font) == (
        "ue",
        "big",
        "#FF0000",
        "mincho",
    )


def test_parse_commands_first_wins_for_loc_size_color_font():
    cmd = nico_ass.parse_commands(
        ["ue", "shita", "big", "small", "red", "blue", "mincho", "gothic"], "abc", False
    )
    assert (cmd.loc, cmd.size, cmd.color, cmd.font) == (
        "ue",
        "big",
        "#FF0000",
        "mincho",
    )


@pytest.mark.parametrize(
    ("commands", "expected"),
    [
        (["@5"], 500),
        (["@5", "@10"], 1000),
        (["＠4"], 400),
        (["@0.555"], 55),
        (["@200"], 12000),
        (["@0"], 300),
        (["@."], 300),
        (["@5", "@1.2.3"], 300),
        (["@5abc"], 500),
        (["@-1"], 300),
    ],
    ids=[
        "seconds",
        "lastwins",
        "fullwidth",
        "floor",
        "cap",
        "zero",
        "dot",
        "nanwins",
        "prefix",
        "negative",
    ],
)
def test_parse_commands_long(commands, expected):
    assert nico_ass.parse_commands(commands, "abc", False).long == expected


@pytest.mark.parametrize(
    ("commands", "expected"),
    [(["gulim"], "defont"), (["simsun", "mincho"], "defont"), (["gothic"], "gothic")],
    ids=["gulim", "simsunslot", "gothic"],
)
def test_parse_commands_flash_fonts_take_slot_as_defont(commands, expected):
    assert nico_ass.parse_commands(commands, "abc", False).font == expected


def test_parse_commands_ignores_unknown_and_nico_prefixed():
    cmd = nico_ass.parse_commands(
        ["184", "device:switch", "middle", "nico:stroke:red", "NICO:fill:red", "shita"],
        "abc",
        False,
    )
    assert (cmd.loc, cmd.color) == ("shita", "#FFFFFF")


def test_parse_commands_live():
    assert nico_ass.parse_commands(["_live"], "abc", False).live is True


@pytest.mark.parametrize(
    ("commands", "body"),
    [(["invisible"], "abc"), ([], "/abc")],
    ids=["command", "slash"],
)
def test_parse_commands_invisible(commands, body):
    assert nico_ass.parse_commands(commands, body, False).invisible is True


COLOR_TABLE = {
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


def test_color_table_has_27_names():
    assert len(COLOR_TABLE) == 27


@pytest.mark.parametrize(
    ("name", "hex_"), list(COLOR_TABLE.items()), ids=list(COLOR_TABLE)
)
def test_parse_commands_color_names(name, hex_):
    assert nico_ass.parse_commands([name], "abc", False).color == hex_


@pytest.mark.parametrize(
    ("commands", "premium", "expected"),
    [
        (["#ff0000"], True, "#FF0000"),
        (["#ff0000"], False, "#FFFFFF"),
        (["#00ff00", "red"], False, "#FF0000"),
        (["#00ff00", "red"], True, "#00FF00"),
        (["#f00"], True, "#F00"),
        (["#zzz", "red"], True, "#ZZZ"),
    ],
    ids=[
        "premium",
        "nonpremium",
        "nonpremiumfallthrough",
        "premiumslot",
        "short",
        "invalidslot",
    ],
)
def test_parse_commands_color_code_only_for_premium(commands, premium, expected):
    assert nico_ass.parse_commands(commands, "abc", premium).color == expected


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("#FF0000", "&H0000FF&"),
        ("#123456", "&H563412&"),
        ("#F00", "&H0000FF&"),
        ("#ZZZ", "&HFFFFFF&"),
    ],
    ids=["red", "bgr", "short", "invalid"],
)
def test_ass_color(color, expected):
    assert nico_ass.ass_color(color) == expected


# ---------------------------------------------------------------------------
# 文字サイズ（C5）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "char", "line"),
    [
        ("big", 49.2308, 45.2391),
        ("medium", 33.9823, 28.9271),
        ("small", 23.1325, 18.0434),
    ],
    ids=["big", "medium", "small"],
)
def test_char_size_and_line_height(size, char, line):
    assert nico_ass.char_size(size) == pytest.approx(char, abs=1e-4)
    assert nico_ass.line_height(size) == pytest.approx(line, abs=1e-4)


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        (33.9823, (27, 1)),
        (49.2308, (39, 1)),
        (23.1325, (18, 1)),
        (12.5, (10, 1)),
        (12.0, (10, 0.9)),
        (1.0, (10, 0.08)),
    ],
    ids=["medium", "big", "small", "justten", "belowten", "belowone"],
)
def test_font_size_and_scale(char, expected):
    font_px, scale = nico_ass.font_size_and_scale(char)
    assert font_px == expected[0]
    assert scale == pytest.approx(expected[1])


def _measure(lines, commands=(), font_scale=1.0, measure=fw_measure):
    cmd = nico_ass.parse_commands(list(commands), "\n".join(lines), False)
    return nico_ass.measure_comment(
        lines, cmd, platform="windows", measure=measure, font_scale=font_scale
    )


def test_measure_comment_ceils_stage_width_and_scales_to_canvas():
    m = _measure(["abc"])  # 13.5 × 3 = 40.5 → 41
    assert m.line_widths == [41]
    assert m.width == pytest.approx(41 * C0)
    assert m.height == pytest.approx(95.5286, abs=1e-3)
    assert (m.font_px, m.scale) == (27, 1)


@pytest.mark.parametrize(
    ("commands", "width", "height"),
    [(["big"], 39 * C0, 138.3940), (["small"], 18 * C0, 65.0285)],
    ids=["big", "small"],
)
def test_measure_comment_sizes(commands, width, height):
    m = _measure(["あ"], commands)
    assert m.width == pytest.approx(width)
    assert m.height == pytest.approx(height, abs=1e-3)


def test_measure_comment_font_scale_multiplies_canvas_size():
    m = _measure(["ab"], font_scale=1.5)
    assert m.width == pytest.approx(75.9004 * 1.5, abs=1e-3)
    assert m.height == pytest.approx(95.5286 * 1.5, abs=1e-3)


def test_measure_comment_multiline_uses_max_width_and_total_height():
    m = _measure(["あ", "あいう"])
    assert m.line_widths == [27, 81]
    assert m.width == pytest.approx(81 * C0)
    assert m.height == pytest.approx(176.8463, abs=1e-3)


# ---------------------------------------------------------------------------
# 上下固定の縮小（C14）
# ---------------------------------------------------------------------------


def exact_512_measure(text, font_name, weight, size_px):
    return 512.0 if size_px == 27 else fw_measure(text, font_name, weight, size_px)


def test_resize_not_applied_at_exact_limit():
    m = _measure(["X"], ["ue"], measure=exact_512_measure)
    assert m.char_size == pytest.approx(33.9823, abs=1e-4)
    assert m.line_widths == [512]


def test_resize_not_applied_to_naka():
    m = _measure(["あ" * 19], ["naka"])
    assert m.line_widths == [513]


def test_resize_one_over_steps_down_by_one():
    m = _measure(["あ" * 19], ["ue"])
    assert m.char_size == pytest.approx(32.9161, abs=1e-4)
    assert m.line_height == pytest.approx(28.0195, abs=1e-4)
    assert (m.font_px, m.scale) == (26, 1)
    assert m.line_widths == [494]
    assert m.width == pytest.approx(494 * C0)


def test_resize_far_over_keeps_last_fitting_size():
    m = _measure(["あ" * 200], ["shita"])
    assert m.char_size == pytest.approx(3.2220, abs=1e-4)
    assert m.font_px == 10
    assert m.scale == pytest.approx(0.2)
    assert m.line_widths == [400]


def stepped_measure(text, font_name, weight, size_px):
    """縮小の増やす側のループ用: 23px で 500、24px でちょうど 512、25px で 600。"""
    return {27: 600.0, 23: 500.0, 24: 512.0, 25: 600.0}[size_px]


def test_resize_grow_stops_before_reaching_limit():
    # 600 → 512/600 倍で 28.998（23px、500）。+1 の 29.998 も 23px で 500、
    # +1 の 30.998 は 24px でちょうど 512 になり、増やすのを止めて 1 つ前を採る
    m = _measure(["X"], ["ue"], measure=stepped_measure)
    assert m.char_size == pytest.approx(29.9982, abs=1e-4)
    assert m.font_px == 23
    assert m.line_widths == [500]


def test_resize_judges_width_after_font_scale():
    assert _measure(["あ" * 15], ["ue"]).line_widths == [405]
    m = _measure(["あ" * 15], ["ue"], font_scale=1.5)
    assert m.char_size == pytest.approx(28.6402, abs=1e-4)
    assert m.font_px == 22
    assert m.line_widths == [330]
    assert m.width == pytest.approx(330 * C0 * 1.5)


# ---------------------------------------------------------------------------
# 速さと横位置（C11）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "long", "expected"),
    [(0, 300, 3.825), (300, 300, 4.5375), (0, 500, 2.55)],
    ids=["zero", "wide", "long"],
)
def test_naka_speed(width, long, expected):
    assert nico_ass.naka_speed(width, long) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("width", "elapsed", "expected"),
    [(300, 0, 1271.25), (0, -100, 1725.0), (300, 400, -543.75)],
    ids=["start", "origin", "late"],
)
def test_naka_x(width, elapsed, expected):
    assert nico_ass.naka_x(width, 300, elapsed) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 配置（C12）
# ---------------------------------------------------------------------------


def item(loc="naka", vpos=0, long=300, width=300.0, height=100.0, commands=()):
    return LayoutItem(
        loc=loc,
        vpos=vpos,
        long=long,
        width=width,
        height=height,
        commands=tuple(commands),
    )


def test_layout_fixed_same_time_stacks():
    assert nico_ass.layout([item("ue"), item("ue")], ScriptedRng([0.0])) == [0, 100]


@pytest.mark.parametrize(
    ("second_vpos", "expected"),
    [(280, 100), (281, 0)],
    ids=["lastframe", "released"],
)
def test_layout_fixed_collision_ends_at_long_minus_20(second_vpos, expected):
    result = nico_ass.layout(
        [item("ue"), item("ue", vpos=second_vpos)], ScriptedRng([0.0])
    )
    assert result == [0, expected]


def test_layout_ue_and_shita_are_independent():
    assert nico_ass.layout([item("ue"), item("shita")], ScriptedRng([0.0])) == [0, 0]


def test_layout_fixed_full_rows_go_random_and_retry_ten_passes():
    rng = ScriptedRng([0.1] * 9 + [0.25])
    items = [item("ue", height=400), item("ue", height=400), item("ue", height=400)]
    assert nico_ass.layout(items, rng) == [0, 400, 170]  # floor(0.25 × 680)
    assert rng.draws == 10


def test_layout_naka_same_time_stacks():
    assert nico_ass.layout([item(), item()], ScriptedRng([0.0])) == [0, 100]


@pytest.mark.parametrize(
    ("second_vpos", "expected"),
    [(64, 100), (65, 0), (1000, 0)],
    ids=["rightline", "released", "far"],
)
def test_layout_naka_right_line_with_padding(second_vpos, expected):
    result = nico_ass.layout([item(), item(vpos=second_vpos)], ScriptedRng([0.0]))
    assert result == [0, expected]


def test_layout_naka_left_line_only_collision():
    # 幅の広い速いコメントが、左の判定線で先のコメントに追いつく
    # （右の判定線では重ならない）
    items = [item(width=100.0), item(vpos=100, width=1500.0)]
    assert nico_ass.layout(items, ScriptedRng([0.0])) == [0, 100]


def test_layout_naka_different_long_trajectories_cross():
    # 遅い（long 1000）コメントを、後から出た速いコメントが判定線の間で追い越す
    items = [item(long=1000), item(vpos=300)]
    assert nico_ass.layout(items, ScriptedRng([0.0])) == [0, 100]


def test_layout_naka_full_rows_go_random_once():
    rng = ScriptedRng([0.5])
    items = [item(height=400), item(height=400), item(height=400)]
    assert nico_ass.layout(items, rng) == [0, 400, 340]
    assert rng.draws == 1


def test_layout_ignores_negative_posy():
    items = [item(height=1200), item()]
    assert nico_ass.layout(items, ScriptedRng([0.0])) == [-60, 0]


# ---------------------------------------------------------------------------
# フォント（C9）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "font", "expected"),
    [
        ("windows", "defont", (FontFace("Arial", 600), FontFace("MS PGothic", 600))),
        ("windows", "gothic", (FontFace("Yu Gothic", 400),)),
        ("windows", "mincho", (FontFace("Yu Mincho", 400),)),
        ("macos", "defont", (FontFace("Hiragino Sans", 600),)),
        ("macos", "gothic", (FontFace("YuGothic", 400),)),
        ("macos", "mincho", (FontFace("YuMincho", 400),)),
        ("other", "defont", (FontFace("sans-serif", 600),)),
        ("other", "gothic", (FontFace("sans-serif", 400),)),
        ("other", "mincho", (FontFace("serif", 400),)),
    ],
    ids=[
        "windefont",
        "wingothic",
        "winmincho",
        "macdefont",
        "macgothic",
        "macmincho",
        "otherdefont",
        "othergothic",
        "othermincho",
    ],
)
def test_font_candidates(platform, font, expected):
    assert nico_ass.font_candidates(font, platform) == expected


def test_font_runs_windows_defont_splits_latin():
    arial, gothic = FontFace("Arial", 600), FontFace("MS PGothic", 600)
    assert nico_ass.font_runs("ab éɏあḀ", "defont", "windows") == [
        ("ab éɏ", arial),
        ("あḀ", gothic),
    ]


def test_font_runs_single_font_elsewhere():
    face = FontFace("Hiragino Sans", 600)
    assert nico_ass.font_runs("abあ", "defont", "macos") == [("abあ", face)]


# ---------------------------------------------------------------------------
# ASS の生成（C2 / C3 / C8 / C9 / C10 / C11 / C13 / C16 / C17）
# ---------------------------------------------------------------------------

# medium、posY 0 の 1 行目: ベースライン 75.4123、em 75.9004
UE_Y = 14.6920  # 75.4123 - 75.9004 × 0.8（MS PGothic の ascent）


def test_convert_header():
    ass = run([]).ass
    lines = ass.splitlines()
    assert not ass.startswith("\ufeff")
    assert "[Script Info]" in lines
    for expected in (
        "PlayResX: 1920",
        "PlayResY: 1080",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: None",
    ):
        assert expected in lines
    style = next(line for line in lines if line.startswith("Style:"))
    values = style[len("Style:") :].split(",")
    assert values[7].strip() == "0"  # Bold
    assert values[17].strip() == "0"  # Shadow
    assert dialogues(ass) == []


def test_convert_ue_position_time_and_font():
    start, end, text = fields(dialogues(run([row(commands=["ue"])]).ass)[0])
    assert (start, end) == ("0:00:10.00", "0:00:13.00")
    assert "\\an8" in text
    assert tag_numbers(text, "pos") == pytest.approx([960, UE_Y], abs=0.006)
    assert runs_of(text) == [("MS PGothic", pytest.approx(75.90, abs=0.006), "あ")]
    assert tag_value(text, "b") == "600"


def test_convert_shita_anchors_bottom():
    text = fields(dialogues(run([row(commands=["shita"])]).ass)[0])[2]
    assert "\\an2" in text
    assert tag_numbers(text, "pos") == pytest.approx([960, 1075.0638], abs=0.006)


def test_convert_naka_moves_between_video_edges():
    start, end, text = fields(dialogues(run([row()]).ass)[0])
    assert (start, end) == ("0:00:08.51", "0:00:13.50")
    assert "\\an7" in text
    assert tag_numbers(text, "move") == pytest.approx(
        [1921.2579, UE_Y, -77.3686, UE_Y], abs=0.006
    )


def test_convert_naka_start_clamped_to_zero():
    start, _, text = fields(dialogues(run([row(vpos_ms=0)]).ass)[0])
    assert start == "0:00:00.00"
    assert tag_numbers(text, "move")[0] == pytest.approx(1324.4736, abs=0.006)


@pytest.mark.parametrize(
    ("width", "start", "x1"),
    [(2520, "0:00:07.76", 2521.6527), (1440, "0:00:09.11", 1440.9421)],
    ids=["wide", "narrow"],
)
def test_convert_naka_enters_from_video_edge(width, start, x1):
    got_start, _, text = fields(dialogues(run([row()], width=width).ass)[0])
    assert got_start == start
    assert tag_numbers(text, "move")[0] == pytest.approx(x1, abs=0.006)


def test_convert_scales_to_playres():
    text = fields(
        dialogues(run([row(commands=["ue"])], width=1280, height=720).ass)[0]
    )[2]
    assert tag_numbers(text, "pos") == pytest.approx([640, 9.7946], abs=0.006)
    assert runs_of(text)[0][1] == pytest.approx(50.60, abs=0.006)


def test_convert_vertical_video_uses_width_based_stage():
    text = fields(
        dialogues(run([row(commands=["ue"])], width=1080, height=1920).ass)[0]
    )[2]
    assert tag_numbers(text, "pos") == pytest.approx([540, 664.5142], abs=0.006)


@pytest.mark.parametrize(
    ("commands", "fs"),
    [(["ue", "big"], 109.63), (["ue", "small"], 50.60)],
    ids=["big", "small"],
)
def test_convert_size_font_size(commands, fs):
    text = fields(dialogues(run([row(commands=commands)]).ass)[0])[2]
    assert runs_of(text)[0][1] == pytest.approx(fs, abs=0.006)


def test_convert_font_scale_percent():
    text = fields(
        dialogues(run([row(commands=["ue"])], font_scale_percent=150).ass)[0]
    )[2]
    assert runs_of(text)[0][1] == pytest.approx(113.85, abs=0.006)


def test_convert_windows_defont_runs_use_each_font_coefficient():
    text = fields(dialogues(run([row(body="abあ", commands=["ue"])]).ass)[0])[2]
    assert runs_of(text) == [
        ("Arial", pytest.approx(83.49, abs=0.006), "ab"),
        ("MS PGothic", pytest.approx(75.90, abs=0.006), "あ"),
    ]
    # 行の上端は最大の ascent（Arial 0.9）で決まる
    assert tag_numbers(text, "pos")[1] == pytest.approx(7.1019, abs=0.006)


def test_convert_gothic_weight_and_font():
    text = fields(dialogues(run([row(commands=["ue", "gothic"])]).ass)[0])[2]
    assert tag_value(text, "b") == "400"
    assert runs_of(text)[0][0] == "Yu Gothic"


def test_convert_missing_metrics_falls_back_to_372_ratio():
    text = fields(dialogues(run([row(commands=["ue"])], metrics=no_metrics).ass)[0])[2]
    assert runs_of(text)[0][1] == pytest.approx(97.2, abs=0.006)


@pytest.mark.parametrize(
    ("commands", "fill", "stroke"),
    [([], "&H33&", "&HAD&"), (["_live"], "&H99&", "&HD6&")],
    ids=["normal", "live"],
)
def test_convert_opacity(commands, fill, stroke):
    text = fields(
        dialogues(run([row(commands=["ue", *commands])], opacity=0.8).ass)[0]
    )[2]
    assert tag_value(text, "1a") == fill
    assert tag_value(text, "3a") == stroke


@pytest.mark.parametrize(
    ("commands", "premium", "fill", "stroke"),
    [
        (["red"], False, "&H0000FF&", "&H000000&"),
        (["black"], False, "&H000000&", "&HFFFFFF&"),
        (["#000"], True, "&H000000&", "&H000000&"),
    ],
    ids=["red", "black", "shortblack"],
)
def test_convert_colors_and_stroke_color(commands, premium, fill, stroke):
    text = fields(
        dialogues(run([row(commands=["ue", *commands], premium=premium)]).ass)[0]
    )[2]
    assert tag_value(text, "c") == fill
    assert tag_value(text, "3c") == stroke


def test_convert_border_width():
    text = fields(dialogues(run([row(commands=["ue"])]).ass)[0])[2]
    assert float(tag_value(text, "bord")) == pytest.approx(3.94, abs=0.006)


def test_convert_border_width_follows_min_font_scale():
    text = fields(dialogues(run([row(body="あ" * 200, commands=["ue"])]).ass)[0])[2]
    assert float(tag_value(text, "bord")) == pytest.approx(0.79, abs=0.006)


def test_convert_multiline_one_dialogue_per_line_left_aligned():
    lines = dialogues(run([row(body="ab\nあいう", commands=["ue"])]).ass)
    assert len(lines) == 2
    first, second = fields(lines[0])[2], fields(lines[1])[2]
    assert tag_numbers(first, "pos") == pytest.approx([884.0996, 7.1019], abs=0.006)
    assert tag_numbers(second, "pos") == pytest.approx([960.0, 96.0097], abs=0.006)
    assert "\\N" not in first + second


def test_convert_escapes_braces_backslash_and_spaces():
    text = fields(dialogues(run([row(body="a{b}\\c d", commands=["ue"])]).ass)[0])[2]
    assert runs_of(text)[0][2] == "a｛b｝＼c\\hd"


def test_convert_invisible_not_output_and_not_placed():
    rows = [
        row(body="x", commands=["ue", "invisible"]),
        row(body="/x", commands=["ue"]),
        row(commands=["ue"]),
    ]
    lines = dialogues(run(rows).ass)
    assert len(lines) == 1
    assert tag_numbers(fields(lines[0])[2], "pos")[1] == pytest.approx(UE_Y, abs=0.006)


def test_convert_orders_by_vpos_then_posted_then_input():
    rows = [
        row(body="あい", commands=["ue"], posted="2020-01-02T00:00:00+09:00"),
        row(body="あ", commands=["ue"], posted="2020-01-01T00:00:00+09:00"),
        row(body="あいう", commands=["ue"], posted="2020-01-02T00:00:00+09:00"),
    ]
    lines = [fields(d)[2] for d in dialogues(run(rows).ass)]
    assert [runs_of(t)[0][2] for t in lines] == ["あ", "あい", "あいう"]
    ys = [tag_numbers(t, "pos")[1] for t in lines]
    assert ys == pytest.approx([UE_Y, 110.2205, 205.7491], abs=0.006)


def test_convert_vpos_ms_floors_to_centiseconds():
    start, _, _ = fields(dialogues(run([row(commands=["ue"], vpos_ms=1239)]).ass)[0])
    assert start == "0:00:01.23"


def test_convert_skips_invalid_rows_and_counts():
    good = row(commands=["ue"])
    bad = [
        {k: v for k, v in good.items() if k != "body"},
        {**good, "commands": "ue"},
        {**good, "vposMs": "100"},
        {**good, "vposMs": True},
        {k: v for k, v in good.items() if k != "isPremium"},
        {**good, "postedAt": "not a date"},
        "not an object",
    ]
    result = run([*bad, good])
    assert result.skipped == 7
    assert len(dialogues(result.ass)) == 1


@pytest.mark.parametrize("text", ["{", '{"a": 1}'], ids=["broken", "notlist"])
def test_convert_raises_when_whole_json_unreadable(text):
    with pytest.raises(ValueError):
        nico_ass.convert(
            text,
            width=1920,
            height=1080,
            font_scale_percent=100,
            opacity=0.8,
            platform="windows",
            measure=fw_measure,
            metrics=fake_metrics,
            rng=random.Random(0),
        )


def _excerpt() -> list[dict]:
    rows: list[dict] = json.loads(
        (DATA / "sm31143779.comments.excerpt.json").read_text(encoding="utf-8")
    )
    return rows


def test_convert_real_excerpt_is_deterministic():
    rows = _excerpt()
    first = run(rows, rng=random.Random(42))
    second = run(rows, rng=random.Random(42))
    assert first.skipped == 0
    assert first.ass == second.ass
    assert len(dialogues(first.ass)) == len(rows)


def test_full_fixture_matches_recorded_hash():
    # C20 / C21 で使う実物（sm31143779、2026-11-14 取得、1,432 件）。
    # 抜粋と同じキーだけ残した
    import hashlib

    raw = gzip.decompress((DATA / "sm31143779.comments.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == "2118f138cc63234970e301adeeac10bc111f564ae27c162eb031e46e44f38c79"
    )
    assert len(json.loads(raw)) == 1432


# ---------------------------------------------------------------------------
# 測定器と寸法（C15 / C16）
# ---------------------------------------------------------------------------


def test_approx_measurer():
    assert nico_ass.approx_measurer("aあ", "Arial", 600, 20) == pytest.approx(30)


def test_pillow_measurer_falls_back_without_pillow(monkeypatch):
    nico_ass.pillow_measurer.cache_clear()
    nico_ass.font_metrics.cache_clear()
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.ImageFont", None)
    try:
        measure = nico_ass.pillow_measurer("windows")
        assert measure("aあ", "Arial", 600, 20) == pytest.approx(30)
        assert nico_ass.font_metrics("windows")("Arial", 600) is None
    finally:
        nico_ass.pillow_measurer.cache_clear()
        nico_ass.font_metrics.cache_clear()


def test_pillow_measurer_unknown_font_falls_back():
    measure = nico_ass.pillow_measurer("windows")
    assert measure("aあ", "No Such Font", 400, 20) == pytest.approx(30)
    assert nico_ass.font_metrics("windows")("No Such Font", 400) is None


def _arial_available() -> bool:
    return sys.platform == "win32" and Path(r"C:\Windows\Fonts\arial.ttf").exists()


@pytest.mark.skipif(not _arial_available(), reason="Arial が無い環境")
def test_pillow_measurer_measures_real_font():
    pytest.importorskip("PIL.ImageFont")
    measure = nico_ass.pillow_measurer("windows")
    wide = measure("WWWW", "Arial", 600, 27)
    narrow = measure("iiii", "Arial", 600, 27)
    assert wide > narrow > 0
    assert measure("WWWW", "Arial", 600, 54) == pytest.approx(wide * 2, rel=0.02)
    metrics = nico_ass.font_metrics("windows")("Arial", 600)
    assert metrics is not None
    assert metrics.ascent + metrics.descent > 1.0
