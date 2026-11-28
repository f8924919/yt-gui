"""`scripts/download_binaries.py` のピン留め・sha256 検証ロジックのテスト。

`scripts/` はパッケージではないため、ファイルパスから直接ロードする。
"""

import datetime
import email.message
import hashlib
import http.server
import importlib.util
import io
import os
import shutil
import tarfile
import threading
import urllib.error
import zipfile
from typing import ClassVar

import pytest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "download_binaries.py",
)
_spec = importlib.util.spec_from_file_location("download_binaries", _SCRIPT)
assert _spec is not None and _spec.loader is not None
download_binaries = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(download_binaries)


# --- sha256 検証ヘルパー ---------------------------------------------------


def test_verify_sha256_accepts_matching_hash(tmp_path):
    """ハッシュが一致すれば例外を送出せず、ファイルも残る。"""
    f = tmp_path / "blob.bin"
    f.write_bytes(b"hello world")
    digest = hashlib.sha256(b"hello world").hexdigest()
    download_binaries._verify_sha256(str(f), digest, "test")  # 例外が出ないこと
    assert f.exists()


def test_verify_sha256_is_case_insensitive(tmp_path):
    """期待値が大文字でも一致と判定する（deno の sha256sum は大文字）。"""
    f = tmp_path / "blob.bin"
    f.write_bytes(b"data")
    digest = hashlib.sha256(b"data").hexdigest().upper()
    download_binaries._verify_sha256(str(f), digest, "test")
    assert f.exists()


def test_verify_sha256_rejects_mismatch_and_removes_file(tmp_path):
    """不一致なら RuntimeError を送出し、取得物を削除する。"""
    f = tmp_path / "blob.bin"
    f.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="sha256"):
        download_binaries._verify_sha256(str(f), "0" * 64, "test")
    assert not f.exists()


def test_verify_sha256_rejects_missing_expected(tmp_path):
    """期待値が未設定（None / 空）なら RuntimeError を送出する。"""
    f = tmp_path / "blob.bin"
    f.write_bytes(b"data")
    with pytest.raises(RuntimeError, match=r"pins\.json"):
        download_binaries._verify_sha256(str(f), None, "test")


# --- 取得リトライ・診断情報（#265） ----------------------------------------


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _FakeDownload:
    """`_download` の差し替え。要素が bytes なら書き込み、Exception なら送出する。"""

    def __init__(self, results: list[bytes | Exception]) -> None:
        self._results = results
        self.calls: list[str] = []

    def __call__(self, url: str, dest: str) -> int:
        result = self._results[len(self.calls)]
        self.calls.append(url)
        if isinstance(result, Exception):
            raise result
        with open(dest, "wb") as fh:
            fh.write(result)
        return len(result)


def test_download_verified_retries_then_succeeds(tmp_path, monkeypatch):
    """1 回目の sha256 不一致は再取得し、2 回目の成功で正常続行する。"""
    good = b"good content"
    fake = _FakeDownload([b"corrupted", good])
    monkeypatch.setattr(download_binaries, "_download", fake)
    sleeps: list[float] = []
    dest = tmp_path / "blob.bin"
    download_binaries._download_verified(
        "https://example.invalid/blob",
        str(dest),
        _digest(good),
        "test",
        retries=3,
        backoff_initial_sec=2.0,
        sleep=sleeps.append,
    )
    assert dest.read_bytes() == good
    assert len(fake.calls) == 2
    assert sleeps == [2.0]


def test_download_verified_exhausts_retries_and_raises(tmp_path, monkeypatch):
    """全滅時は従来どおり RuntimeError で中断し、最終試行後には待機しない。"""
    fake = _FakeDownload([b"bad1", b"bad2", b"bad3"])
    monkeypatch.setattr(download_binaries, "_download", fake)
    sleeps: list[float] = []
    dest = tmp_path / "blob.bin"
    with pytest.raises(RuntimeError, match="sha256"):
        download_binaries._download_verified(
            "https://example.invalid/blob",
            str(dest),
            "0" * 64,
            "test",
            retries=3,
            backoff_initial_sec=2.0,
            sleep=sleeps.append,
        )
    assert len(fake.calls) == 3
    assert sleeps == [2.0, 4.0]  # 指数バックオフ・最終試行後は sleep しない
    assert not dest.exists()  # _verify_sha256 の削除（fail-closed）は維持


def test_download_verified_retries_on_download_error(tmp_path, monkeypatch):
    """取得時の例外（接続断・タイムアウト等）もリトライ対象。"""
    good = b"payload"
    fake = _FakeDownload([OSError("reset"), TimeoutError("stall"), good])
    monkeypatch.setattr(download_binaries, "_download", fake)
    sleeps: list[float] = []
    dest = tmp_path / "blob.bin"
    download_binaries._download_verified(
        "https://example.invalid/blob",
        str(dest),
        _digest(good),
        "test",
        retries=3,
        backoff_initial_sec=2.0,
        sleep=sleeps.append,
    )
    assert dest.read_bytes() == good
    assert len(fake.calls) == 3
    assert sleeps == [2.0, 4.0]


def test_download_verified_missing_expected_does_not_retry(tmp_path, monkeypatch):
    """sha256 未設定は台帳の設定エラーであり、リトライせず即時中断する。"""
    fake = _FakeDownload([b"data", b"data", b"data"])
    monkeypatch.setattr(download_binaries, "_download", fake)
    sleeps: list[float] = []
    dest = tmp_path / "blob.bin"
    with pytest.raises(RuntimeError, match=r"pins\.json"):
        download_binaries._download_verified(
            "https://example.invalid/blob",
            str(dest),
            None,
            "test",
            retries=3,
            backoff_initial_sec=2.0,
            sleep=sleeps.append,
        )
    assert len(fake.calls) == 1
    assert sleeps == []


def test_download_verified_prints_diagnostics_on_mismatch(
    tmp_path, monkeypatch, capsys
):
    """不一致の失敗時にサイズ・Content-Length・先頭 16 バイト hex を出力する。"""
    data = b"BAD CONTENT 0123456789"
    fake = _FakeDownload([data])
    monkeypatch.setattr(download_binaries, "_download", fake)
    dest = tmp_path / "blob.bin"
    with pytest.raises(RuntimeError):
        download_binaries._download_verified(
            "https://example.invalid/blob",
            str(dest),
            "0" * 64,
            "test",
            retries=1,
            backoff_initial_sec=0.0,
            sleep=lambda _s: None,
        )
    out = capsys.readouterr().out
    assert f"サイズ={len(data)}" in out
    assert f"Content-Length={len(data)}" in out
    assert data[:16].hex() in out


def test_download_verified_prints_diagnostics_when_file_missing(
    tmp_path, monkeypatch, capsys
):
    """取得自体の失敗（ファイル不存在）でもその旨を診断出力する。"""
    fake = _FakeDownload([OSError("boom")])
    monkeypatch.setattr(download_binaries, "_download", fake)
    dest = tmp_path / "blob.bin"
    with pytest.raises(OSError):
        download_binaries._download_verified(
            "https://example.invalid/blob",
            str(dest),
            "0" * 64,
            "test",
            retries=1,
            backoff_initial_sec=0.0,
            sleep=lambda _s: None,
        )
    out = capsys.readouterr().out
    assert "サイズ=なし" in out


# --- ピン留め台帳 ----------------------------------------------------------


def test_pins_json_is_valid_and_complete():
    """bin/pins.json が読み込めて主要コンポーネントを網羅している。"""
    pins = download_binaries._load_pins()
    for key in ("deno", "ffmpeg-win", "ffmpeg-mac", "ffmpeg-linux", "danmaku2ass"):
        assert key in pins

    # deno: 全アセットに 64 桁 hex の sha256 が入っている
    for sha in pins["deno"]["assets"].values():
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha.lower())

    # ffmpeg-win / ffmpeg-mac / ffmpeg-linux は sha256 が確定済み（null 不可）
    assert len(pins["ffmpeg-win"]["sha256"]) == 64
    # ffmpeg-mac は arch 別（x86_64 / arm64）に ffmpeg/ffprobe を持つ
    for arch in ("x86_64", "arm64"):
        for tool in ("ffmpeg", "ffprobe"):
            assert len(pins["ffmpeg-mac"][arch][tool]["sha256"]) == 64
    for entry in pins["ffmpeg-linux"]["assets"].values():
        assert len(entry["sha256"]) == 64

    # BtbN（win / linux）は不変 autobuild-* タグ配下の URL であること
    # （ローリングの latest 参照は sha256 ドリフトを起こすため不可。#72 / #272）
    assert "/releases/download/autobuild-" in pins["ffmpeg-win"]["url"]
    for entry in pins["ffmpeg-linux"]["assets"].values():
        assert "/releases/download/autobuild-" in entry["url"]

    # danmaku2ass は git の SHA 固定（sha256 検証対象外）
    assert len(pins["danmaku2ass"]["ref"]) == 40


def test_danmaku2ass_constants_come_from_pins():
    """モジュール定数がピン台帳由来であること（単一ソース）。"""
    pins = download_binaries._load_pins()
    assert pins["danmaku2ass"]["ref"] == download_binaries.DANMAKU2ASS_REF
    assert pins["danmaku2ass"]["repo"] == download_binaries.DANMAKU2ASS_REPO


# --- ffmpeg-linux（BtbN tar.xz）の展開 -------------------------------------
# フィクスチャは BtbN 実アーカイブ（autobuild-2026-07-19-13-12 の linux64-gpl）で
# 確認した構成を再現する: `ffmpeg-<version>/` 直下に LICENSE.txt、`bin/` 配下に
# ffmpeg / ffprobe / ffplay（#272 で実物を取得して裏取り）。

_BTBN_ROOT = "ffmpeg-n8.1.2-22-g94138f6973-linux64-gpl-8.1"


def _make_btbn_linux_tarball(path: str, with_binaries: bool = True) -> None:
    """BtbN linux64-gpl 構成を模した tar.xz を生成する。"""
    with tarfile.open(path, "w:xz") as t:

        def add(name: str, data: bytes, mode: int = 0o644) -> None:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            t.addfile(info, io.BytesIO(data))

        add(f"{_BTBN_ROOT}/LICENSE.txt", b"GNU GENERAL PUBLIC LICENSE")
        add(f"{_BTBN_ROOT}/doc/ffmpeg.html", b"<html></html>")
        if with_binaries:
            add(f"{_BTBN_ROOT}/bin/ffmpeg", b"\x7fELF ffmpeg", 0o755)
            add(f"{_BTBN_ROOT}/bin/ffprobe", b"\x7fELF ffprobe", 0o755)
            add(f"{_BTBN_ROOT}/bin/ffplay", b"\x7fELF ffplay", 0o755)


@pytest.fixture
def _linux_env(tmp_path, monkeypatch):
    """BIN_DIR / LICENSES_DIR / 台帳 / ダウンロードを tmp_path 内に閉じ込める。"""
    bin_dir = tmp_path / "bin"
    ffmpeg_dir = bin_dir / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True)
    monkeypatch.setattr(download_binaries, "BIN_DIR", str(bin_dir))
    monkeypatch.setattr(download_binaries, "LICENSES_DIR", str(bin_dir / "licenses"))
    archive = tmp_path / "src.tar.xz"
    pins = {
        "ffmpeg-linux": {
            "version": "n8.1.2-22-g94138f6973",
            "assets": {
                "amd64": {"url": "https://example.invalid/x.tar.xz", "sha256": "0" * 64}
            },
        }
    }
    monkeypatch.setattr(download_binaries, "_load_pins", lambda: pins)

    def fake_download_verified(url, dest, expected, label, **kwargs):
        shutil.copyfile(str(archive), dest)

    monkeypatch.setattr(download_binaries, "_download_verified", fake_download_verified)
    return archive, ffmpeg_dir


def test_download_ffmpeg_linux_extracts_btbn_nested_layout(_linux_env):
    """BtbN の `ffmpeg-*/bin/` ネスト構成から ffmpeg / ffprobe を配置し、
    ライセンス本文を抽出する。ffplay は同梱しない。"""
    archive, ffmpeg_dir = _linux_env
    _make_btbn_linux_tarball(str(archive))
    ffmpeg_path = ffmpeg_dir / "ffmpeg"
    ffprobe_path = ffmpeg_dir / "ffprobe"
    download_binaries._download_ffmpeg_linux(
        "x86_64", str(ffmpeg_dir), str(ffmpeg_path), str(ffprobe_path)
    )
    assert ffmpeg_path.read_bytes() == b"\x7fELF ffmpeg"
    assert ffprobe_path.read_bytes() == b"\x7fELF ffprobe"
    assert not (ffmpeg_dir / "ffplay").exists()
    license_path = ffmpeg_dir.parent / "licenses" / "ffmpeg" / "LICENSE.txt"
    assert license_path.read_bytes() == b"GNU GENERAL PUBLIC LICENSE"


def test_download_ffmpeg_linux_raises_when_binaries_missing(_linux_env):
    """想定外レイアウト（bin/ 配下に ffmpeg が無い）では silent skip せず中断する。"""
    archive, ffmpeg_dir = _linux_env
    _make_btbn_linux_tarball(str(archive), with_binaries=False)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        download_binaries._download_ffmpeg_linux(
            "x86_64",
            str(ffmpeg_dir),
            str(ffmpeg_dir / "ffmpeg"),
            str(ffmpeg_dir / "ffprobe"),
        )


# --- THIRD-PARTY-NOTICES 生成 ---------------------------------------------


def test_write_third_party_notices_lists_all_components(tmp_path):
    """全コンポーネントの名称・ライセンス・対応ソースが告知に含まれる。"""
    out = download_binaries.write_third_party_notices(str(tmp_path))
    assert os.path.basename(out) == "THIRD-PARTY-NOTICES.md"
    with open(out, encoding="utf-8") as fh:
        text = fh.read()
    for component in download_binaries.COMPONENTS:
        assert component["name"] in text
        assert component["license"] in text
        # 対応ソース入手先（GPL の書面オファー）が記載される
        assert component["source"].split(" ")[0] in text
    # GPL / MIT の主要コンポーネントを網羅している
    assert "FFmpeg" in text and "danmaku2ass" in text and "Deno" in text


def test_third_party_notices_include_niconicomments_mit_full_text(tmp_path):
    """niconicomments（#387 で式を移植）の MIT 許諾表示の全文が告知に載る（C22）。"""
    from yt_gui import nico_ass

    component = next(
        c for c in download_binaries.COMPONENTS if c["name"] == "niconicomments"
    )
    assert component["license"] == "MIT"
    assert "899203436285" in component["source"]
    license_text = component["license_text"]
    assert license_text.startswith("MIT License\n\nCopyright (c) 2022 xpadev-net\n")
    assert "Permission is hereby granted, free of charge" in license_text
    assert license_text.endswith("SOFTWARE.")
    # モジュール冒頭の許諾表示と同じ全文
    assert license_text == nico_ass.NICONICOMMENTS_LICENSE

    out = download_binaries.write_third_party_notices(str(tmp_path))
    with open(out, encoding="utf-8") as fh:
        text = fh.read()
    assert license_text in text


def test_third_party_notices_ffmpeg_linux_points_to_btbn(tmp_path):
    """ffmpeg (Linux) の配布元が BtbN であり、旧取得元が残っていない（#272）。"""
    out = download_binaries.write_third_party_notices(str(tmp_path))
    with open(out, encoding="utf-8") as fh:
        text = fh.read()
    assert "Linux: https://github.com/BtbN/FFmpeg-Builds" in text
    assert "johnvansickle" not in text


def test_is_license_name_matches_common_filenames():
    assert download_binaries._is_license_name("foo/bin/LICENSE.txt")
    assert download_binaries._is_license_name("GPLv3.txt")
    assert download_binaries._is_license_name("COPYING")
    assert not download_binaries._is_license_name("ffmpeg.exe")
    assert not download_binaries._is_license_name("README.md")


# --- 429 / 503 の Retry-After と macOS arm64 の取り直し（#413） -------------
# 仕様: docs/build.md「ピン留めと sha256 検証」のリトライの段落。

_URL = "https://example.invalid/blob"


def _http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    """本物の HTTPError（headers は email.message.Message）を作る。"""
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError(_URL, code, "x", hdrs, None)


def _run_retrying(tmp_path, monkeypatch, results, **kw):
    sleeps: list[float] = []
    fake = _FakeDownload(results)
    monkeypatch.setattr(download_binaries, "_download", fake)
    download_binaries._download_retrying(
        _URL,
        str(tmp_path / "blob.bin"),
        "test",
        check=kw.get("check"),
        retries=kw.get("retries", 3),
        backoff_initial_sec=2.0,
        sleep=sleeps.append,
        now=kw.get("now", lambda: 0.0),
    )
    return fake, sleeps


def _run_retrying_raises(tmp_path, monkeypatch, results, exc_type, **kw):
    sleeps: list[float] = []
    fake = _FakeDownload(results)
    monkeypatch.setattr(download_binaries, "_download", fake)
    with pytest.raises(exc_type) as info:
        download_binaries._download_retrying(
            _URL,
            str(tmp_path / "blob.bin"),
            "test",
            check=kw.get("check"),
            retries=kw.get("retries", 3),
            backoff_initial_sec=2.0,
            sleep=sleeps.append,
            now=kw.get("now", lambda: 0.0),
        )
    return fake, sleeps, info


# C4・C5 の定数。テストではリテラルで確かめる（定数どうしを比べると定数の変異を見逃す）


def test_throttle_constants():
    assert frozenset({429, 503}) == download_binaries._THROTTLE_STATUSES
    assert download_binaries._THROTTLE_WAITS_SEC == (30.0, 60.0, 120.0, 120.0)
    assert download_binaries._THROTTLE_MAX_WAIT_SEC == 120.0
    assert download_binaries._THROTTLE_ATTEMPTS == 5


# C2 Retry-After の秒数（既定の待ちが下限）


@pytest.mark.parametrize("code", [429, 503])
def test_retry_after_seconds_longer_than_default_is_used(tmp_path, monkeypatch, code):
    fake, sleeps = _run_retrying(
        tmp_path, monkeypatch, [_http_error(code, "45"), b"ok"]
    )
    assert len(fake.calls) == 2
    assert sleeps == [45.0]


@pytest.mark.parametrize("code", [429, 503])
def test_retry_after_shorter_than_default_uses_default(tmp_path, monkeypatch, code):
    """短い指定（7 秒）は既定の待ち（1 回目 30 秒）を下限にする。"""
    _fake, sleeps = _run_retrying(
        tmp_path, monkeypatch, [_http_error(code, "7"), b"ok"]
    )
    assert sleeps == [30.0]


@pytest.mark.parametrize("value", ["+7", "1_000", "7.5", "abc", "", "-5", "0"])
def test_retry_after_unparseable_uses_default(tmp_path, monkeypatch, value):
    """数字だけでない値・0 以下は解釈できない値として、既定の待ちだけを使う。"""
    _fake, sleeps = _run_retrying(
        tmp_path, monkeypatch, [_http_error(429, value), b"ok"]
    )
    assert sleeps == [30.0]


def test_retry_after_sec_parses_digits_with_surrounding_space():
    assert (
        download_binaries._retry_after_sec(_http_error(429, " 45 "), lambda: 0.0)
        == 45.0
    )


# C3 Retry-After の HTTP 日付


_NOW = datetime.datetime(2026, 11, 28, 5, 0, 0, tzinfo=datetime.UTC).timestamp()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Sat, 28 Nov 2026 05:00:40 GMT", 40.0),
        ("Sat, 28 Nov 2026 05:00:40 -0000", 40.0),  # タイムゾーン無し → UTC とみなす
        ("Sat, 28 Nov 2026 05:00:39 GMT", 39.0),
        ("Sat, 28 Nov 2026 04:59:00 GMT", None),  # 過去
        ("Sat, 28 Nov 2026 05:00:00 GMT", None),  # 0
        ("not a date", None),
    ],
)
def test_retry_after_sec_http_date(value, expected):
    assert (
        download_binaries._retry_after_sec(_http_error(429, value), lambda: _NOW)
        == expected
    )


def test_retry_after_sec_rounds_up_fraction():
    got = download_binaries._retry_after_sec(
        _http_error(429, "Sat, 28 Nov 2026 05:00:40 GMT"), lambda: _NOW + 0.5
    )
    assert got == 40.0  # 39.5 秒 → 切り上げ


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.HTTPError(_URL, 429, "x", None, None),  # type: ignore[arg-type]
        _http_error(429),  # ヘッダ無し
        OSError("reset"),
    ],
    ids=["headers_none", "no_header", "not_http_error"],
)
def test_retry_after_sec_returns_none_without_header(exc):
    assert download_binaries._retry_after_sec(exc, lambda: _NOW) is None


def test_retry_after_http_date_goes_through_retry(tmp_path, monkeypatch):
    """日付の Retry-After が（日付 − 現在）秒に換算され、既定との長いほうを待つ。"""
    _fake, sleeps = _run_retrying(
        tmp_path,
        monkeypatch,
        [_http_error(429, "Sat, 28 Nov 2026 05:00:45 GMT"), b"ok"],
        now=lambda: _NOW,
    )
    assert sleeps == [45.0]


# C4 Retry-After が無いときの待ちの列 / C5 上限


@pytest.mark.parametrize("code", [429, 503])
def test_throttle_default_waits(tmp_path, monkeypatch, code):
    fake, sleeps = _run_retrying(
        tmp_path, monkeypatch, [_http_error(code)] * 4 + [b"ok"]
    )
    assert len(fake.calls) == 5
    assert sleeps == [30.0, 60.0, 120.0, 120.0]


@pytest.mark.parametrize(("value", "expected"), [("120", 120.0), ("121", 120.0)])
def test_throttle_wait_is_capped(tmp_path, monkeypatch, value, expected):
    _fake, sleeps = _run_retrying(
        tmp_path, monkeypatch, [_http_error(429, value), b"ok"]
    )
    assert sleeps == [expected]


def test_throttle_wait_cap_applies_to_http_date(tmp_path, monkeypatch):
    _fake, sleeps = _run_retrying(
        tmp_path,
        monkeypatch,
        [_http_error(429, "Sat, 28 Nov 2026 05:10:00 GMT"), b"ok"],
        now=lambda: _NOW,
    )
    assert sleeps == [120.0]


def test_throttle_gives_up_after_five_attempts(tmp_path, monkeypatch):
    """429 / 503 が続くときは 5 回で止め、5 回目の後は待たない。"""
    fake, sleeps, info = _run_retrying_raises(
        tmp_path, monkeypatch, [_http_error(429)] * 6, urllib.error.HTTPError
    )
    assert len(fake.calls) == 5
    assert sleeps == [30.0, 60.0, 120.0, 120.0]
    assert info.value.code == 429


def test_mixed_failures_worst_case_is_seven_attempts(tmp_path, monkeypatch):
    """2 種類の失敗は別々に数える。最悪は取得 7 回・待ち 486 秒。"""
    results: list[bytes | Exception] = [OSError("a"), OSError("b")]
    results += [_http_error(429)] * 4 + [b"ok"]
    fake, sleeps = _run_retrying(tmp_path, monkeypatch, results)
    assert len(fake.calls) == 7
    assert sleeps == [2.0, 4.0, 30.0, 60.0, 120.0, 120.0]
    assert sum(sleeps) == 336.0
    # 最悪（Retry-After が上限を超える 429 が 4 回）の待ちの合計
    worst = 4 * download_binaries._THROTTLE_MAX_WAIT_SEC + 2.0 + 4.0
    assert worst == 486.0


def test_mixed_failures_other_failures_still_stop_at_three(tmp_path, monkeypatch):
    results = [
        OSError("a"),
        _http_error(429),
        OSError("b"),
        _http_error(503),
        OSError("c"),
    ]
    fake, sleeps, _info = _run_retrying_raises(tmp_path, monkeypatch, results, OSError)
    assert len(fake.calls) == 5
    assert sleeps == [2.0, 30.0, 4.0, 60.0]


# C6 対象外の失敗は今のまま


@pytest.mark.parametrize(
    "exc",
    [_http_error(502, "45"), _http_error(408), _http_error(404), _http_error(410)],
    ids=["502_with_retry_after", "408", "404", "410"],
)
def test_other_http_errors_keep_short_retry(tmp_path, monkeypatch, exc):
    fake, sleeps, _info = _run_retrying_raises(
        tmp_path, monkeypatch, [exc, exc, exc], urllib.error.HTTPError
    )
    assert len(fake.calls) == 3
    assert sleeps == [2.0, 4.0]


# C7 取り尽くしたときの診断


def test_exhausted_throttle_reports_status_retry_after_and_total(
    tmp_path, monkeypatch, capsys
):
    _fake, sleeps, _info = _run_retrying_raises(
        tmp_path, monkeypatch, [_http_error(429, "45")] * 5, urllib.error.HTTPError
    )
    out = capsys.readouterr().out
    # 毎試行の行（「最後の状態=」の行とは別に確かめる）
    assert " 状態=429 Retry-After=45 " in out
    assert "最後の状態=429" in out
    assert f"待った合計={sum(sleeps):g} 秒" in out
    assert "取得を断念" in out


def test_exhausted_without_http_status_reports_none(tmp_path, monkeypatch, capsys):
    _fake, _sleeps, _info = _run_retrying_raises(
        tmp_path, monkeypatch, [OSError("x")] * 3, OSError
    )
    out = capsys.readouterr().out
    assert " 状態=なし Retry-After=なし " in out
    assert "最後の状態=なし" in out
    assert "待った合計=6 秒" in out


def test_retry_after_raw_is_sanitized():
    exc = _http_error(429, "7\x1b[31m" + "x" * 100)
    raw = download_binaries._retry_after_raw(exc)
    assert "\x1b" not in raw and len(raw) <= 40


# C9 sha256 未設定は専用の例外で即時中断（取得の失敗は取り直す）


def test_pin_config_error_is_runtime_error():
    assert issubclass(download_binaries.PinConfigError, RuntimeError)


def test_missing_expected_after_throttle_still_aborts_without_retry(
    tmp_path, monkeypatch
):
    """取得の 429 は取り直し、取得できた後の sha256 未設定は取り直さない。"""
    sleeps: list[float] = []
    fake = _FakeDownload([_http_error(429), b"data", b"data"])
    monkeypatch.setattr(download_binaries, "_download", fake)
    with pytest.raises(download_binaries.PinConfigError, match=r"pins\.json"):
        download_binaries._download_verified(
            _URL, str(tmp_path / "blob.bin"), None, "test", sleep=sleeps.append
        )
    assert len(fake.calls) == 2
    assert sleeps == [30.0]


# C8 macOS arm64


def _zip_bytes(tool: str, data: bytes, *, with_member: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr(f"__MACOSX/._{tool}", b"appledouble")
        if with_member:
            z.writestr(tool, data)
    return buf.getvalue()


def _corrupt(zip_data: bytes, payload: bytes) -> bytes:
    """格納されたデータを 1 バイト書き換えて CRC を合わなくする。"""
    i = zip_data.rindex(payload)
    return zip_data[:i] + bytes([zip_data[i] ^ 0xFF]) + zip_data[i + 1 :]


_FF = b"\xcf\xfa\xed\xfe ffmpeg arm64"
_FP = b"\xcf\xfa\xed\xfe ffprobe arm64"


@pytest.fixture
def _mac_arm64_env(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    ffmpeg_dir = bin_dir / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True)
    monkeypatch.setattr(download_binaries, "BIN_DIR", str(bin_dir))
    monkeypatch.setattr(download_binaries.platform, "machine", lambda: "arm64")
    pins = {
        "ffmpeg-mac": {
            "arm64": {
                "version": "9.1",
                "verify": "binary",
                "ffmpeg": {
                    "url": "https://example.invalid/ff.zip",
                    "sha256": _digest(_FF),
                },
                "ffprobe": {
                    "url": "https://example.invalid/fp.zip",
                    "sha256": _digest(_FP),
                },
            }
        }
    }
    monkeypatch.setattr(download_binaries, "_load_pins", lambda: pins)
    sleeps: list[float] = []
    monkeypatch.setattr(download_binaries.time, "sleep", sleeps.append)
    return pins, ffmpeg_dir, sleeps


def _run_mac(monkeypatch, ffmpeg_dir, results):
    fake = _FakeDownload(results)
    monkeypatch.setattr(download_binaries, "_download", fake)
    download_binaries._download_ffmpeg_macos(
        str(ffmpeg_dir), str(ffmpeg_dir / "ffmpeg"), str(ffmpeg_dir / "ffprobe")
    )
    return fake


def test_mac_arm64_retries_throttled_download(_mac_arm64_env, monkeypatch):
    _pins, ffmpeg_dir, sleeps = _mac_arm64_env
    fake = _run_mac(
        monkeypatch,
        ffmpeg_dir,
        [_http_error(429), _zip_bytes("ffmpeg", _FF), _zip_bytes("ffprobe", _FP)],
    )
    assert len(fake.calls) == 3
    assert sleeps == [30.0]
    assert (ffmpeg_dir / "ffmpeg").read_bytes() == _FF
    assert (ffmpeg_dir / "ffprobe").read_bytes() == _FP


def test_mac_arm64_retries_short_failure(_mac_arm64_env, monkeypatch):
    _pins, ffmpeg_dir, sleeps = _mac_arm64_env
    fake = _run_mac(
        monkeypatch,
        ffmpeg_dir,
        [OSError("reset"), _zip_bytes("ffmpeg", _FF), _zip_bytes("ffprobe", _FP)],
    )
    assert len(fake.calls) == 3
    assert sleeps == [2.0]


@pytest.mark.parametrize(
    "broken",
    [
        _corrupt(_zip_bytes("ffmpeg", _FF), _FF),  # CRC が合わない
        _zip_bytes("ffmpeg", _FF, with_member=False),  # 対象のファイルが無い
        _zip_bytes("ffmpeg", _FF)[:40],  # 途中で切れた
    ],
    ids=["bad_crc", "missing_member", "truncated"],
)
def test_mac_arm64_retries_broken_zip(_mac_arm64_env, monkeypatch, broken):
    _pins, ffmpeg_dir, sleeps = _mac_arm64_env
    fake = _run_mac(
        monkeypatch,
        ffmpeg_dir,
        [broken, _zip_bytes("ffmpeg", _FF), _zip_bytes("ffprobe", _FP)],
    )
    assert len(fake.calls) == 3
    assert sleeps == [2.0]
    assert (ffmpeg_dir / "ffmpeg").read_bytes() == _FF


def test_mac_arm64_sha_mismatch_after_extract_is_not_retried(
    _mac_arm64_env, monkeypatch
):
    """展開後の sha256 不一致は差し替え・改ざんの疑いなので取り直さない。"""
    pins, ffmpeg_dir, sleeps = _mac_arm64_env
    pins["ffmpeg-mac"]["arm64"]["ffmpeg"]["sha256"] = "0" * 64
    fake = _FakeDownload([_zip_bytes("ffmpeg", _FF)] * 3)
    monkeypatch.setattr(download_binaries, "_download", fake)
    with pytest.raises(RuntimeError, match="sha256"):
        download_binaries._download_ffmpeg_macos(
            str(ffmpeg_dir), str(ffmpeg_dir / "ffmpeg"), str(ffmpeg_dir / "ffprobe")
        )
    assert len(fake.calls) == 1
    assert sleeps == []
    assert not (ffmpeg_dir / "ffmpeg").exists()


def test_mac_arm64_missing_sha_is_not_retried(_mac_arm64_env, monkeypatch):
    pins, ffmpeg_dir, sleeps = _mac_arm64_env
    pins["ffmpeg-mac"]["arm64"]["ffmpeg"]["sha256"] = None
    fake = _FakeDownload([_zip_bytes("ffmpeg", _FF)] * 3)
    monkeypatch.setattr(download_binaries, "_download", fake)
    with pytest.raises(RuntimeError, match=r"pins\.json"):
        download_binaries._download_ffmpeg_macos(
            str(ffmpeg_dir), str(ffmpeg_dir / "ffmpeg"), str(ffmpeg_dir / "ffprobe")
        )
    assert len(fake.calls) == 1
    assert sleeps == []


# C10 実物との突き合わせ（ローカルの http.server で urlopen の経路ごと通す）


class _ThrottleOnceHandler(http.server.BaseHTTPRequestHandler):
    body = b"real payload over http"
    hits: ClassVar[list[str]] = []  # テストごとに入れ替える記録用

    def do_GET(self):
        type(self).hits.append(self.path)
        if len(type(self).hits) == 1:
            self.send_response(429)
            self.send_header("Retry-After", "1")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


def test_download_verified_over_real_http_429(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setattr(download_binaries, "_DOWNLOAD_TIMEOUT_SEC", 5)
    _ThrottleOnceHandler.hits = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _ThrottleOnceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/blob"
        sleeps: list[float] = []
        dest = tmp_path / "blob.bin"
        download_binaries._download_verified(
            url,
            str(dest),
            _digest(_ThrottleOnceHandler.body),
            "test",
            sleep=sleeps.append,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert dest.read_bytes() == _ThrottleOnceHandler.body
    assert len(_ThrottleOnceHandler.hits) == 2
    assert sleeps == [30.0]  # Retry-After: 1 は既定の待ち（30 秒）が下限
