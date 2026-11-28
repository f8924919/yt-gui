"""`scripts/refresh_pins.py` の純粋ロジック（解析・選択・サマリ）のテスト。

ネットワークアクセスを伴う関数は対象外（CI / 実機で検証する）。
"""

import importlib.util
import json
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


# --- macOS arm64 のピンの古さの検査（#412） ---------------------------------
# 仕様: docs/build.md「macOS arm64 のピンの古さの検知」。フィクスチャは実物の
# osxexperts.net のページから切り出したもの（出所は各ファイルの先頭に記載）。

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_URL91_FFMPEG = "https://www.osxexperts.net/ffmpeg91arm.zip"
_URL91_FFPROBE = "https://www.osxexperts.net/ffprobe91arm.zip"
_SHA91_FFMPEG = "f3cc9de031a39020b7285a62667b951949a0377483b7cbf708c7126234fda34f"
_SHA91_FFPROBE = "a663dbfafcd144f441834bc4af50077ccb969b635775612e5eddb6574f2caed0"
_SHA90_FFMPEG = "591260c945d0eef150e3bf82b0ef988bd36a9cecc18ff05d6679617159f0a95e"
_SHA90_FFPROBE = "e11c17e8200b3ee4c4c186d245e2b4053f01d56957336c1817fca0b997469106"


def _page(version: str) -> str:
    with open(
        os.path.join(_DATA, f"osxexperts_arm64_{version}.html"), encoding="utf-8"
    ) as f:
        return f.read()


def _arm_pin_91() -> dict:
    return {
        "version": "9.1",
        "source": "osxexperts.net",
        "verify": "binary",
        "ffmpeg": {"url": _URL91_FFMPEG, "sha256": _SHA91_FFMPEG},
        "ffprobe": {"url": _URL91_FFPROBE, "sha256": _SHA91_FFPROBE},
    }


def _check(pin: dict, page: str, url_ok=lambda url: "ok") -> list[str]:
    # refresh_pins は importlib で読むため型は Any になる。戻り値の型をここで固める。
    alerts: list[str] = refresh_pins.check_ffmpeg_mac_arm64(
        pin, fetch_text=lambda url: page, url_ok=url_ok
    )
    return alerts


def _stale(alerts: list[str]) -> list[str]:
    return [a for a in alerts if a.startswith(refresh_pins._ALERT_STALE)]


def _unchecked(alerts: list[str]) -> list[str]:
    return [a for a in alerts if a.startswith(refresh_pins._ALERT_UNCHECKED)]


# C1 版の読み取り


def test_parse_osxexperts_reads_apple_silicon_91():
    """現行ページ（9.1）から Apple Silicon 版の版と URL を読む。

    Intel 版と ffplay は拾わない。
    """
    got = refresh_pins._parse_osxexperts_arm64(_page("9.1"))
    assert got == {
        "ffmpeg": ("9.1", _URL91_FFMPEG),
        "ffprobe": ("9.1", _URL91_FFPROBE),
    }


def test_parse_osxexperts_accepts_dropped_trailing_zero_in_link():
    """9.0 はリンクが `ffmpeg9arm.zip`（末尾 .0 を省く）でも一致とみなす。"""
    got = refresh_pins._parse_osxexperts_arm64(_page("9.0"))
    assert got == {
        "ffmpeg": ("9.0", "https://www.osxexperts.net/ffmpeg9arm.zip"),
        "ffprobe": ("9.0", "https://www.osxexperts.net/ffprobe9arm.zip"),
    }


@pytest.mark.parametrize(
    "mutate",
    [
        # リンクだけ（文言が無い）
        lambda h: h.replace("Download ffmpeg 9.1 (Apple Silicon)", "Download"),
        # 文言だけ（リンクが無い）
        lambda h: h.replace("ffmpeg91arm.zip", "ffmpeg-latest.zip"),
        # リンクと文言の版が食い違う
        lambda h: h.replace("ffmpeg91arm.zip", "ffmpeg92arm.zip"),
        # Apple Silicon 版のリンクが 2 本ある
        lambda h: h.replace("ffmpeg80intel.zip", "ffmpeg91arm.zip"),
    ],
    ids=["link_only", "text_only", "link_text_mismatch", "duplicate_link"],
)
def test_parse_osxexperts_rejects_broken_structure(mutate):
    """リンクと文言がそろわない・食い違う・重複するときは ArmPageError。"""
    with pytest.raises(refresh_pins.ArmPageError):
        refresh_pins._parse_osxexperts_arm64(mutate(_page("9.1")))


def test_same_version_ignores_trailing_zero():
    assert refresh_pins._same_version("9", "9.0")
    assert refresh_pins._same_version("9.0", "9")
    assert refresh_pins._same_version("9.1", "9.1")
    assert not refresh_pins._same_version("9.1", "9.0")
    assert not refresh_pins._same_version("10", "1.0")


# C2 古さの判定 / C12 sha256 がページに載っているか


def test_check_arm64_current_pin_has_no_alerts():
    """#411 後のピン（9.1）と現行ページの組では警告しない。"""
    assert _check(_arm_pin_91(), _page("9.1")) == []


def test_check_arm64_pin_90_written_as_9_matches_90_page():
    """ピンの版が "9"、ページが 9.0 でも同じ版とみなす。"""
    pin = {
        "version": "9",
        "ffmpeg": {
            "url": "https://www.osxexperts.net/ffmpeg9arm.zip",
            "sha256": _SHA90_FFMPEG,
        },
        "ffprobe": {
            "url": "https://www.osxexperts.net/ffprobe9arm.zip",
            "sha256": _SHA90_FFPROBE,
        },
    }
    assert _check(pin, _page("9.0")) == []


def test_check_arm64_old_pin_is_stale():
    """ピンが 9.0 のままでページが 9.1 なら「古い」。ページとピンの版を出す。"""
    pin = {
        "version": "9.0",
        "ffmpeg": {
            "url": "https://www.osxexperts.net/ffmpeg9arm.zip",
            "sha256": _SHA90_FFMPEG,
        },
        "ffprobe": {
            "url": "https://www.osxexperts.net/ffprobe9arm.zip",
            "sha256": _SHA90_FFPROBE,
        },
    }
    alerts = _check(pin, _page("9.1"))
    stale = _stale(alerts)
    assert stale, alerts
    assert any("9.1" in a and "9.0" in a for a in stale)
    assert not _unchecked(alerts)


def test_check_arm64_url_differs_from_page_is_stale():
    """版は同じでもピンの URL がページの URL と違えば「古い」。"""
    pin = _arm_pin_91()
    pin["ffprobe"]["url"] = "https://www.osxexperts.net/ffprobe91arm-old.zip"
    stale = _stale(_check(pin, _page("9.1")))
    assert any("ffprobe" in a for a in stale)
    # C2: ページの版・ピンの版を含む（版が同じで URL だけ違うときも）
    assert any("ページ 9.1" in a and "ピン 9.1" in a for a in stale), stale


def test_check_arm64_sha_missing_from_page_is_stale():
    """ピンの sha256 がページに載っていなければ「古い（差し替えの可能性）」。"""
    pin = _arm_pin_91()
    pin["ffmpeg"]["sha256"] = "0" * 64
    stale = _stale(_check(pin, _page("9.1")))
    assert any("ffmpeg" in a and "sha256" in a for a in stale)


def test_check_arm64_sha_comparison_is_case_insensitive():
    pin = _arm_pin_91()
    pin["ffmpeg"]["sha256"] = _SHA91_FFMPEG.upper()
    assert _check(pin, _page("9.1")) == []


def test_check_arm64_ffmpeg_ffprobe_version_split_is_reported():
    """ページ上で ffmpeg と ffprobe の版が違えば、その旨が分かる警告を出す。"""
    page = (
        _page("9.1")
        .replace("ffprobe91arm.zip", "ffprobe92arm.zip")
        .replace(
            "Download ffprobe 9.1 (Apple Silicon)",
            "Download ffprobe 9.2 (Apple Silicon)",
        )
    )
    alerts = _check(_arm_pin_91(), page)
    assert any("ffmpeg" in a and "ffprobe" in a and "9.2" in a for a in alerts)


def test_refresh_ffmpeg_mac_notes_arch_version_difference(monkeypatch):
    """x86_64 と arm64 の版の差は状況欄の注記だけで、arm64 は書き換えない。"""
    info = {
        "version": "9.2",
        "download": {"zip": {"url": "https://evermeet.cx/ffmpeg/x-9.2.zip", "size": 1}},
    }
    monkeypatch.setattr(refresh_pins, "_http_json", lambda url, headers=None: info)
    monkeypatch.setattr(refresh_pins, "_hashes_of_url", lambda url: ("d" * 64, 1))
    old = {
        "x86_64": {
            "version": "9.1",
            "ffmpeg": {"url": "u", "sha256": "e" * 64},
            "ffprobe": {"url": "u", "sha256": "e" * 64},
        },
        "arm64": _arm_pin_91(),
    }
    new, summary = refresh_pins.refresh_ffmpeg_mac(old)
    assert new["arm64"] == _arm_pin_91()
    assert "x86_64 と版が異なる" in summary


# C3 URL の生存


class _Resp:
    def __init__(self, url: str, status: int = 200, ctype: str = "application/zip"):
        self._url = url
        self.status = status
        self.headers = {"Content-Type": ctype}

    def geturl(self) -> str:
        return self._url

    def read(self, n: int = -1) -> bytes:
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(url: str, code: int):
    import urllib.error

    return urllib.error.HTTPError(url, code, "x", {}, None)  # type: ignore[arg-type]


def _opener(responses: dict):
    """urlopen の代わり。method ごとに応答（_Resp か例外）を返し、method を記録する。"""
    calls: list[str] = []

    def fake(req, timeout=None):
        method = req.get_method()
        calls.append(method)
        r = responses[method]
        if isinstance(r, BaseException):
            raise r
        return r

    return fake, calls


def test_url_ok_head_200_zip():
    fake, calls = _opener({"HEAD": _Resp(_URL91_FFMPEG)})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "ok"
    assert calls == ["HEAD"]


@pytest.mark.parametrize("code", [404, 410])
def test_url_ok_gone_on_404_410(code):
    fake, _ = _opener({"HEAD": _http_error(_URL91_FFMPEG, code)})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "gone"


@pytest.mark.parametrize(
    "exc",
    [
        _http_error(_URL91_FFMPEG, 500),
        _http_error(_URL91_FFMPEG, 503),
        TimeoutError("timed out"),
        OSError("connection refused"),
    ],
    ids=["500", "503", "timeout", "oserror"],
)
def test_url_ok_error_on_server_or_network_failure(exc):
    import urllib.error

    excs = {"HEAD": exc, "GET": exc}
    if isinstance(exc, OSError) and not isinstance(exc, urllib.error.HTTPError):
        excs = {"HEAD": urllib.error.URLError(exc), "GET": urllib.error.URLError(exc)}
    fake, _ = _opener(excs)
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "error"


def test_url_ok_redirect_to_other_url_is_gone():
    """取り下げた zip がトップページへリダイレクトされる形を「古い」とみなす。"""
    fake, _ = _opener({"HEAD": _Resp("https://www.osxexperts.net/", ctype="text/html")})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "gone"


def test_url_ok_non_zip_response_is_gone():
    fake, _ = _opener({"HEAD": _Resp(_URL91_FFMPEG, ctype="text/html; charset=utf-8")})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "gone"


def test_url_ok_falls_back_to_range_get_when_head_not_allowed():
    fake, calls = _opener(
        {"HEAD": _http_error(_URL91_FFMPEG, 405), "GET": _Resp(_URL91_FFMPEG, 206)}
    )
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "ok"
    assert calls == ["HEAD", "GET"]


@pytest.mark.parametrize("tool", ["ffmpeg", "ffprobe"])
def test_check_arm64_gone_url_is_stale_per_tool(tool):
    """ffmpeg だけ・ffprobe だけの URL が消えたときも「古い」とし、ツール名を出す。"""
    gone = _arm_pin_91()[tool]["url"]
    alerts = _check(
        _arm_pin_91(), _page("9.1"), url_ok=lambda u: "gone" if u == gone else "ok"
    )
    stale = _stale(alerts)
    assert len(stale) == 1 and tool in stale[0], alerts
    assert not _unchecked(alerts)


def test_check_arm64_url_check_error_is_unchecked():
    alerts = _check(_arm_pin_91(), _page("9.1"), url_ok=lambda u: "error")
    assert _unchecked(alerts) and not _stale(alerts)


# C4 検査不能の区別 / C13 警告文に入れるもの


def test_check_arm64_fetch_failure_is_unchecked():
    def boom(url):
        raise OSError("<html>blocked</html>\n::error::injected %0A")

    alerts = refresh_pins.check_ffmpeg_mac_arm64(
        _arm_pin_91(), fetch_text=boom, url_ok=lambda u: "ok"
    )
    assert len(_unchecked(alerts)) == 1 and not _stale(alerts)
    assert "OSError" in alerts[0]
    # 例外メッセージの生の文字列（第三者の HTML）は流さない
    assert "<html>" not in alerts[0] and "::error::" not in alerts[0]


def test_check_arm64_structure_change_is_unchecked_and_does_not_leak_html():
    page = "<html><script>alert(1)</script>no links here\n::error::x</html>"
    alerts = _check(_arm_pin_91(), page)
    assert len(_unchecked(alerts)) == 1 and not _stale(alerts)
    assert "<script>" not in alerts[0] and "::error::" not in alerts[0]


def test_check_arm64_unexpected_exception_becomes_unchecked():
    """想定外の入力（ピンのキー欠落など）でも例外を外へ出さず「検査できなかった」にする。"""
    alerts = _check({"version": "9.1"}, _page("9.1"))
    assert len(_unchecked(alerts)) == 1
    assert "KeyError" in alerts[0]


def test_alerts_are_single_line():
    alerts = _check({"version": "9.1"}, _page("9.1"))
    alerts += _check(_arm_pin_91(), _page("9.1"), url_ok=lambda u: "gone")
    assert alerts
    assert all("\n" not in a and "\r" not in a for a in alerts)


def test_write_alerts_uses_lf_and_creates_empty_file(tmp_path):
    path = tmp_path / "alerts.txt"
    refresh_pins._write_alerts(str(path), [])
    assert path.exists() and path.read_bytes() == b""
    refresh_pins._write_alerts(str(path), ["a\r\nb", "c"])
    assert path.read_bytes() == b"a b\nc\n"


# C6 警告の出力


def test_build_summary_puts_alerts_first():
    alerts = [f"{refresh_pins._ALERT_STALE}: ffmpeg（ページ 9.2 / ピン 9.1）"]
    out = refresh_pins._build_summary([], ["deno: v2.8.1（変更なし）"], alerts)
    assert "[!CAUTION]" in out
    assert out.index("[!CAUTION]") < out.index("更新はありません")
    assert alerts[0] in out
    assert "bin/pins.json" in out and "ffmpeg-mac.arm64" in out


def test_build_summary_without_alerts_has_no_caution():
    out = refresh_pins._build_summary([], ["deno: v2.8.1（変更なし）"], [])
    assert "[!CAUTION]" not in out


# C5 検査を先に行い先に書く / C8 sha256 を書き換えない


def _pins_for_run() -> dict:
    return {
        "deno": {"v": 1},
        "ffmpeg-win": {"v": 1},
        "ffmpeg-mac": {"x86_64": {"version": "9.1"}, "arm64": _arm_pin_91()},
        "ffmpeg-linux": {"v": 1},
    }


def test_run_checks_and_writes_alerts_before_refresh(monkeypatch, tmp_path):
    """再ピンが例外になっても、arm64 の警告は先に書き出されている。"""
    order: list[str] = []
    alert = f"{refresh_pins._ALERT_STALE}: ffmpeg"

    def fake_check(pin, **kw):
        order.append("check")
        return [alert]

    def fake_refresh(pins):
        order.append("refresh")
        raise RuntimeError("BtbN down")

    monkeypatch.setattr(refresh_pins, "check_ffmpeg_mac_arm64", fake_check)
    monkeypatch.setattr(refresh_pins, "refresh_pins", fake_refresh)
    path = tmp_path / "alerts.txt"
    with pytest.raises(RuntimeError):
        refresh_pins.run(_pins_for_run(), alerts_out=str(path))
    assert order == ["check", "refresh"]
    assert path.read_text(encoding="utf-8") == alert + "\n"


def test_run_passes_refresh_result_through_and_keeps_arm64(monkeypatch):
    """警告があっても再ピンの結果はそのまま。arm64 のピンは書き換えない。"""
    pins = _pins_for_run()
    before = json.loads(json.dumps(pins))
    sentinel = ({"new": True}, ["c"], ["s"])
    monkeypatch.setattr(refresh_pins, "check_ffmpeg_mac_arm64", lambda pin, **kw: ["x"])
    monkeypatch.setattr(refresh_pins, "refresh_pins", lambda p: sentinel)
    new_pins, changes, statuses, alerts = refresh_pins.run(pins)
    assert (new_pins, changes, statuses) == sentinel
    assert alerts == ["x"]
    assert pins == before


def test_run_with_real_check_does_not_touch_arm64_pin(monkeypatch):
    """実際の検査（古い判定あり）を通しても、arm64 のピンは不変。"""
    pins = _pins_for_run()
    pins["ffmpeg-mac"]["arm64"]["ffmpeg"]["sha256"] = "0" * 64
    before = json.loads(json.dumps(pins))
    monkeypatch.setattr(
        refresh_pins, "_http_text", lambda url, headers=None: _page("9.1")
    )
    monkeypatch.setattr(refresh_pins, "_url_ok", lambda url, **kw: "ok")
    monkeypatch.setattr(refresh_pins, "refresh_pins", lambda p: (p, [], []))
    new_pins, _c, _s, alerts = refresh_pins.run(pins)
    assert _stale(alerts)
    assert pins == before
    assert new_pins["ffmpeg-mac"]["arm64"] == before["ffmpeg-mac"]["arm64"]


def test_real_pins_json_arm64_matches_fixture_page():
    """実物の bin/pins.json の arm64 ピンが、実物から切り出した現行ページと一致する。

    A3（実物との突き合わせ）。arm64 のピンを手で更新したら、フィクスチャ
    `tests/data/osxexperts_arm64_<版>.html` も実物から取り直す（docs/build.md）。
    """
    import download_binaries as db

    arm = db._load_pins()["ffmpeg-mac"]["arm64"]
    # ピンの版のフィクスチャを読む（ピンを上げたのにフィクスチャが無ければここで落ちる）
    assert _check(arm, _page(arm["version"])) == []


def test_check_arm64_fetch_http_error_reports_status_code():
    """ページ取得の HTTPError は状態コードを警告に入れる。

    429 / 403 / 503 を切り分けるため。
    """

    def boom(url):
        raise _http_error(url, 429)

    alerts = refresh_pins.check_ffmpeg_mac_arm64(
        _arm_pin_91(), fetch_text=boom, url_ok=lambda u: "ok"
    )
    assert len(_unchecked(alerts)) == 1
    assert "HTTP 429" in alerts[0]


# main()（警告があっても終了コード 0・本文に載せる・--alerts-out を渡す）


def test_main_exits_zero_with_alerts_and_wires_outputs(monkeypatch, tmp_path):
    """警告があっても main() は 0 で終わる（PR 作成を止めない）。

    止めるのはワークフローの最後のステップ。

    警告は PR 本文用サマリの先頭に載り、`--alerts-out` の指定は run() へ渡る。
    """
    pins = _pins_for_run()
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps(pins), encoding="utf-8")
    summary_path = tmp_path / "body.md"
    alerts_path = tmp_path / "alerts.txt"
    alert = f"{refresh_pins._ALERT_STALE}: ffmpeg（ページ 9.2 / ピン 9.1）"
    received: dict = {}

    def fake_run(p, alerts_out=None):
        received["alerts_out"] = alerts_out
        return p, [], ["deno（変更なし）"], [alert]

    monkeypatch.setattr(
        refresh_pins.db, "_load_pins", lambda: json.loads(json.dumps(pins))
    )
    monkeypatch.setattr(refresh_pins.db, "PINS_PATH", str(pins_path))
    monkeypatch.setattr(refresh_pins, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh_pins.py",
            "--summary-out",
            str(summary_path),
            "--alerts-out",
            str(alerts_path),
        ],
    )
    assert refresh_pins.main() == 0
    assert received["alerts_out"] == str(alerts_path)
    body = summary_path.read_text(encoding="utf-8")
    assert "[!CAUTION]" in body and alert in body


def test_url_ok_redirect_to_other_zip_is_gone():
    """別の zip の URL へリダイレクトされた場合も「古い」。

    Content-Type が zip でも、着いた URL が違えば古いとみなす。
    """
    fake, _ = _opener({"HEAD": _Resp("https://www.osxexperts.net/ffmpeg92arm.zip")})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "gone"


@pytest.mark.parametrize(
    "exc", [TimeoutError("timed out"), ConnectionResetError("reset")], ids=str
)
def test_url_ok_error_on_raw_oserror(exc):
    """URLError に包まれない生の OSError（読み取り中のタイムアウトなど）も "error"。"""
    fake, _ = _opener({"HEAD": exc, "GET": exc})
    assert refresh_pins._url_ok(_URL91_FFMPEG, open_fn=fake) == "error"


def _run_with_real_check(monkeypatch, pins: dict, alerts_out: str | None = None):
    monkeypatch.setattr(
        refresh_pins, "_http_text", lambda url, headers=None: _page("9.1")
    )
    monkeypatch.setattr(refresh_pins, "_url_ok", lambda url, **kw: "ok")
    monkeypatch.setattr(refresh_pins, "refresh_pins", lambda p: (p, [], []))
    return refresh_pins.run(pins, alerts_out=alerts_out)


def test_run_does_not_alert_on_x86_arm_version_difference_alone(monkeypatch):
    """C2: x86_64 が先行して版が違うだけなら警告しない。

    arm64 のピンはページと一致している。
    """
    pins = _pins_for_run()
    pins["ffmpeg-mac"]["x86_64"]["version"] = "9.2"
    _new, _c, _s, alerts = _run_with_real_check(monkeypatch, pins)
    assert alerts == []


def test_run_writes_empty_alerts_file_when_no_alerts(monkeypatch, tmp_path):
    """C6: 警告が無いときも、run() は空の警告ファイルを作る。

    作らないと、ワークフローの失敗ステップが「成功したのにファイルが無い」と
    判定して、警告の無い週も毎週失敗する。
    """
    path = tmp_path / "alerts.txt"
    _new, _c, _s, alerts = _run_with_real_check(
        monkeypatch, _pins_for_run(), alerts_out=str(path)
    )
    assert alerts == []
    assert path.exists() and path.read_bytes() == b""


def test_check_arm64_version_mismatch_alone_is_stale():
    """URL・sha256 がページと同じでも、ピンの version が違えば「古い」。

    版の比較を外すと、URL の比較では拾えない（URL は一致している）。
    """
    pin = _arm_pin_91()
    pin["version"] = "9.0"
    stale = _stale(_check(pin, _page("9.1")))
    assert len(stale) == 2, stale  # ffmpeg・ffprobe
    assert all("ページ 9.1" in a and "ピン 9.0" in a for a in stale)
    assert not any("URL" in a for a in stale)
