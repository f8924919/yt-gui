"""`scripts/download_binaries.py` のピン留め・sha256 検証ロジックのテスト。

`scripts/` はパッケージではないため、ファイルパスから直接ロードする。
"""

import hashlib
import importlib.util
import io
import os
import shutil
import tarfile

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
