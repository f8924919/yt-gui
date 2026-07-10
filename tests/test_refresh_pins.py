"""`scripts/refresh_pins.py` の純粋ロジック（解析・選択・サマリ）のテスト。

ネットワークアクセスを伴う関数は対象外（CI / 実機で検証する）。
"""

import importlib.util
import os
import sys

import pytest

_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
# refresh_pins は同ディレクトリの download_binaries を import するため path を通す
sys.path.insert(0, _SCRIPTS)
_SCRIPT = os.path.join(_SCRIPTS, "refresh_pins.py")
_spec = importlib.util.spec_from_file_location("refresh_pins", _SCRIPT)
assert _spec is not None and _spec.loader is not None
refresh_pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refresh_pins)


# --- _parse_sha256sum ------------------------------------------------------


def test_parse_sha256sum_plain_form():
    """`<hash>  <path>` 形式を解析する。"""
    text = "2d7bb6195226ac832e0bf7109a115f0af65ee69ac797a4bbde5b27a06cc242d9  deno.zip"
    assert refresh_pins._parse_sha256sum(text) == (
        "2d7bb6195226ac832e0bf7109a115f0af65ee69ac797a4bbde5b27a06cc242d9"
    )


def test_parse_sha256sum_verbose_form_is_lowercased():
    """deno Windows の `Hash : <HASH>` 形式（大文字）も小文字で取り出す。"""
    digest = "5FB5BAC71F609FB91EC8960FB290885AADC27EEB22F07A8ECA0C3DB6BE38B11A"
    text = f"Algorithm : SHA256\nHash : {digest}\n"
    assert refresh_pins._parse_sha256sum(text) == (
        "5fb5bac71f609fb91ec8960fb290885aadc27eeb22f07a8eca0c3db6be38b11a"
    )


def test_parse_sha256sum_rejects_garbage():
    with pytest.raises(RuntimeError):
        refresh_pins._parse_sha256sum("no hash here")


# --- _select_latest_autobuild ---------------------------------------------


def _release(tag: str, names: list[str] | None = None) -> dict:
    return {
        "tag_name": tag,
        "assets": [_asset(n) for n in (names or [])],
    }


def test_select_latest_autobuild_picks_newest_dated_tag():
    """ローリングの latest を除外し、日時タグが最大の autobuild を選ぶ。"""
    releases = [
        _release("latest"),
        _release("autobuild-2026-06-02-14-20"),
        _release("autobuild-2026-05-31-13-22"),
        _release("autobuild-2026-06-01-15-02"),
    ]
    rel = refresh_pins._select_latest_autobuild(releases)
    assert rel["tag_name"] == "autobuild-2026-06-02-14-20"


def test_select_latest_autobuild_raises_when_no_autobuild():
    with pytest.raises(RuntimeError):
        refresh_pins._select_latest_autobuild([_release("latest")])


# --- _select_btbn_versioned_asset -----------------------------------------


def _asset(name: str) -> dict:
    return {"name": name, "browser_download_url": f"https://example/{name}"}


def test_select_btbn_picks_highest_stable_version():
    """master / shared / lgpl を除外し、最大のリリースブランチ X.Y を選ぶ。

    autobuild タグのアセットは `ffmpeg-nX.Y.Z-<N>-g<hash>-win64-gpl-X.Y.zip` 形式。
    """
    assets = [
        _asset("ffmpeg-N-124739-gbb5c461a47-win64-gpl.zip"),
        _asset("ffmpeg-n7.1.4-7-gadcf20da26-win64-gpl-7.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-8.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-shared-8.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-lgpl-8.1.zip"),
    ]
    version, url = refresh_pins._select_btbn_versioned_asset(assets)
    assert version == "n8.1.1-9-g58d4114d36"
    assert url == "https://example/ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-8.1.zip"


def test_select_btbn_compares_minor_numerically():
    """ブランチ X.Y は文字列比較ではなく数値比較（8.10 > 8.9）。"""
    assets = [
        _asset("ffmpeg-n8.9.1-3-gabcdef0123-win64-gpl-8.9.zip"),
        _asset("ffmpeg-n8.10.1-3-gabcdef0123-win64-gpl-8.10.zip"),
    ]
    version, _ = refresh_pins._select_btbn_versioned_asset(assets)
    assert version == "n8.10.1-3-gabcdef0123"


def test_select_btbn_accepts_exact_tag_without_git_describe():
    """git-describe サフィックスが無いタグ直上のアセットも採用する。"""
    assets = [_asset("ffmpeg-n8.1-win64-gpl-8.1.zip")]
    version, _ = refresh_pins._select_btbn_versioned_asset(assets)
    assert version == "n8.1"


def test_select_btbn_raises_when_no_stable():
    with pytest.raises(RuntimeError):
        refresh_pins._select_btbn_versioned_asset(
            [_asset("ffmpeg-N-124739-gbb5c461a47-win64-gpl.zip")]
        )


# --- _parse_jvs_version ----------------------------------------------------


def test_parse_jvs_version_extracts_date():
    readme = "  build: ffmpeg-git-20240629-amd64-static.tar.xz\n  version: d5e603d\n"
    assert refresh_pins._parse_jvs_version(readme) == "git-20240629"


def test_parse_jvs_version_falls_back():
    assert refresh_pins._parse_jvs_version("no build line") == "git"


# --- _build_summary --------------------------------------------------------


def test_build_summary_with_changes():
    out = refresh_pins._build_summary(
        ["deno: v2.8.1 → v2.9.0（上流 .sha256sum と照合）"],
        ["deno: v2.8.1 → v2.9.0", "ffmpeg-win: n8.1（変更なし）"],
    )
    assert "ピン更新" in out
    assert "v2.9.0" in out
    assert "変更なし" in out  # 状況セクションに全件が載る


def test_build_summary_no_changes():
    out = refresh_pins._build_summary([], ["deno: v2.8.1（変更なし）"])
    assert "更新はありません" in out
