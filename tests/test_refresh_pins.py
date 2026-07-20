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

    autobuild タグのアセットは `ffmpeg-nX.Y.Z-<N>-g<hash>-<variant>-X.Y.<ext>` 形式。
    """
    assets = [
        _asset("ffmpeg-N-124739-gbb5c461a47-win64-gpl.zip"),
        _asset("ffmpeg-n7.1.4-7-gadcf20da26-win64-gpl-7.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-8.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-shared-8.1.zip"),
        _asset("ffmpeg-n8.1.1-9-g58d4114d36-win64-lgpl-8.1.zip"),
    ]
    version, url = refresh_pins._select_btbn_versioned_asset(assets, "win64-gpl", "zip")
    assert version == "n8.1.1-9-g58d4114d36"
    assert url == "https://example/ffmpeg-n8.1.1-9-g58d4114d36-win64-gpl-8.1.zip"


def test_select_btbn_compares_minor_numerically():
    """ブランチ X.Y は文字列比較ではなく数値比較（8.10 > 8.9）。"""
    assets = [
        _asset("ffmpeg-n8.9.1-3-gabcdef0123-win64-gpl-8.9.zip"),
        _asset("ffmpeg-n8.10.1-3-gabcdef0123-win64-gpl-8.10.zip"),
    ]
    version, _ = refresh_pins._select_btbn_versioned_asset(assets, "win64-gpl", "zip")
    assert version == "n8.10.1-3-gabcdef0123"


def test_select_btbn_accepts_exact_tag_without_git_describe():
    """git-describe サフィックスが無いタグ直上のアセットも採用する。"""
    assets = [_asset("ffmpeg-n8.1-win64-gpl-8.1.zip")]
    version, _ = refresh_pins._select_btbn_versioned_asset(assets, "win64-gpl", "zip")
    assert version == "n8.1"


def test_select_btbn_raises_when_no_stable():
    with pytest.raises(RuntimeError):
        refresh_pins._select_btbn_versioned_asset(
            [_asset("ffmpeg-N-124739-gbb5c461a47-win64-gpl.zip")], "win64-gpl", "zip"
        )


def test_select_btbn_linux_variants_pick_tar_xz():
    """linux64-gpl / linuxarm64-gpl の tar.xz を variant 別に選べる（#272）。

    `linuxarm64` は `linux64` を部分文字列に含まないため相互に誤爆しない。
    """
    assets = [
        _asset("ffmpeg-n8.1.2-22-g94138f6973-win64-gpl-8.1.zip"),
        _asset("ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz"),
        _asset("ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-shared-8.1.tar.xz"),
        _asset("ffmpeg-n8.1.2-22-g94138f6973-linux64-lgpl-8.1.tar.xz"),
        _asset("ffmpeg-n8.1.2-22-g94138f6973-linuxarm64-gpl-8.1.tar.xz"),
    ]
    version, url = refresh_pins._select_btbn_versioned_asset(
        assets, "linux64-gpl", "tar.xz"
    )
    assert version == "n8.1.2-22-g94138f6973"
    assert url.endswith("-linux64-gpl-8.1.tar.xz")
    version, url = refresh_pins._select_btbn_versioned_asset(
        assets, "linuxarm64-gpl", "tar.xz"
    )
    assert version == "n8.1.2-22-g94138f6973"
    assert url.endswith("-linuxarm64-gpl-8.1.tar.xz")


# --- refresh_ffmpeg_win / refresh_ffmpeg_linux（BtbN 共有リリース注入） -----
# win/linux のタグ・バージョン統一（#272）のため、BtbN の autobuild リリースは
# `refresh_pins()` が 1 回だけ解決し、両 refresher へ引数で注入する契約とする。


def _btbn_release() -> dict:
    return _release(
        "autobuild-2026-07-19-13-12",
        [
            "ffmpeg-n8.1.2-22-g94138f6973-win64-gpl-8.1.zip",
            "ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz",
            "ffmpeg-n8.1.2-22-g94138f6973-linuxarm64-gpl-8.1.tar.xz",
        ],
    )


def _old_linux_pins() -> dict:
    return {
        "version": "git-20240629",
        "comment": "旧 johnvansickle ピン",
        "assets": {
            "amd64": {"url": "https://old.example/amd64.tar.xz", "sha256": "b" * 64},
            "arm64": {"url": "https://old.example/arm64.tar.xz", "sha256": "c" * 64},
        },
    }


def _no_network(monkeypatch):
    """refresher が注入リリース以外でネットワーク解決しないことを保証する。"""
    monkeypatch.setattr(
        refresh_pins,
        "_http_json",
        lambda *a, **k: pytest.fail("注入リリースがあるのに API を呼んだ"),
    )


def test_refresh_ffmpeg_linux_pins_both_arches_from_injected_release(monkeypatch):
    """amd64 / arm64 とも注入された同一リリースの不変 URL・同一版へ再ピンする。"""
    _no_network(monkeypatch)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("a" * 64, 100))
    new, summary = refresh_pins.refresh_ffmpeg_linux(_old_linux_pins(), _btbn_release())
    assert new["version"] == "n8.1.2-22-g94138f6973"
    assert new["assets"]["amd64"]["url"] == (
        "https://example/ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz"
    )
    assert new["assets"]["arm64"]["url"] == (
        "https://example/ffmpeg-n8.1.2-22-g94138f6973-linuxarm64-gpl-8.1.tar.xz"
    )
    assert new["assets"]["amd64"]["sha256"] == "a" * 64
    assert new["assets"]["arm64"]["sha256"] == "a" * 64
    assert "git-20240629" in summary and "n8.1.2-22-g94138f6973" in summary


def test_refresh_ffmpeg_linux_reports_unchanged(monkeypatch):
    """URL・sha256 とも既存ピンと同じなら「変更なし」を報告する。"""
    _no_network(monkeypatch)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("a" * 64, 100))
    old = {
        "version": "n8.1.2-22-g94138f6973",
        "assets": {
            "amd64": {
                "url": "https://example/ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz",
                "sha256": "a" * 64,
            },
            "arm64": {
                "url": "https://example/ffmpeg-n8.1.2-22-g94138f6973-linuxarm64-gpl-8.1.tar.xz",
                "sha256": "a" * 64,
            },
        },
    }
    _new, summary = refresh_pins.refresh_ffmpeg_linux(old, _btbn_release())
    assert "変更なし" in summary


def test_refresh_ffmpeg_linux_raises_when_arch_asset_missing(monkeypatch):
    """リリースに片 arch のアセットが無ければ fail-closed（例外で中断）。"""
    _no_network(monkeypatch)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("a" * 64, 100))
    release = _release(
        "autobuild-2026-07-19-13-12",
        ["ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1.tar.xz"],
    )
    with pytest.raises(RuntimeError):
        refresh_pins.refresh_ffmpeg_linux(_old_linux_pins(), release)


def test_refresh_ffmpeg_linux_raises_on_arch_version_mismatch(monkeypatch):
    """amd64 / arm64 のバージョントークンが食い違えば例外で中断する。"""
    _no_network(monkeypatch)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("a" * 64, 100))
    release = _release(
        "autobuild-2026-07-19-13-12",
        [
            "ffmpeg-n8.1.2-22-gaaaaaaaaaa-linux64-gpl-8.1.tar.xz",
            "ffmpeg-n8.1.1-9-gbbbbbbbbbb-linuxarm64-gpl-8.1.tar.xz",
        ],
    )
    with pytest.raises(RuntimeError):
        refresh_pins.refresh_ffmpeg_linux(_old_linux_pins(), release)


def test_refresh_ffmpeg_win_uses_injected_release(monkeypatch):
    """win も注入リリースから解決する（API を自前で呼ばない）。"""
    _no_network(monkeypatch)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("a" * 64, 100))
    old = {"version": "n8.0", "url": "https://old.example/x.zip", "sha256": "b" * 64}
    new, _summary = refresh_pins.refresh_ffmpeg_win(old, _btbn_release())
    assert new["version"] == "n8.1.2-22-g94138f6973"
    assert new["url"] == (
        "https://example/ffmpeg-n8.1.2-22-g94138f6973-win64-gpl-8.1.zip"
    )
    assert new["sha256"] == "a" * 64


def test_refresh_pins_resolves_btbn_release_once_and_shares_it(monkeypatch):
    """refresh_pins() は BtbN リリース一覧を 1 回だけ取得し、win / linux へ同一
    リリースを渡す（同一タグ・同一バージョンの構造的保証）。"""
    received: list[tuple[str, dict]] = []
    monkeypatch.setitem(
        refresh_pins._REFRESHERS,
        "deno",
        lambda old: (dict(old), "deno（変更なし）"),
    )
    monkeypatch.setitem(
        refresh_pins._REFRESHERS,
        "ffmpeg-mac",
        lambda old: (dict(old), "mac（変更なし）"),
    )

    def fake_win(old: dict, release: dict) -> tuple[dict, str]:
        received.append(("win", release))
        return dict(old), "win"

    def fake_linux(old: dict, release: dict) -> tuple[dict, str]:
        received.append(("linux", release))
        return dict(old), "linux"

    monkeypatch.setitem(refresh_pins._REFRESHERS, "ffmpeg-win", fake_win)
    monkeypatch.setitem(refresh_pins._REFRESHERS, "ffmpeg-linux", fake_linux)
    calls: list[str] = []
    releases = [_release("latest"), _btbn_release()]

    def fake_http_json(url: str, headers: dict | None = None) -> list[dict]:
        calls.append(url)
        return releases

    monkeypatch.setattr(refresh_pins, "_http_json", fake_http_json)
    pins: dict[str, dict] = {
        "deno": {},
        "ffmpeg-win": {},
        "ffmpeg-mac": {},
        "ffmpeg-linux": {},
    }
    refresh_pins.refresh_pins(pins)
    assert len(calls) == 1  # BtbN releases API は 1 回だけ
    assert [name for name, _ in received] == ["win", "linux"]
    assert received[0][1] is received[1][1]  # 同一リリース dict を共有
    assert received[0][1]["tag_name"] == "autobuild-2026-07-19-13-12"


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


def test_build_summary_does_not_mention_removed_supplier():
    """johnvansickle 廃止（#272）後の定型文に旧取得元が残っていない。"""
    out = refresh_pins._build_summary([], ["deno: v2.8.1（変更なし）"])
    assert "johnvansickle" not in out
