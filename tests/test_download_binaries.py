"""`scripts/download_binaries.py` のピン留め・sha256 検証ロジックのテスト。

`scripts/` はパッケージではないため、ファイルパスから直接ロードする。
"""

import hashlib
import importlib.util
import os

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

    # danmaku2ass は git の SHA 固定（sha256 検証対象外）
    assert len(pins["danmaku2ass"]["ref"]) == 40


def test_danmaku2ass_constants_come_from_pins():
    """モジュール定数がピン台帳由来であること（単一ソース）。"""
    pins = download_binaries._load_pins()
    assert pins["danmaku2ass"]["ref"] == download_binaries.DANMAKU2ASS_REF
    assert pins["danmaku2ass"]["repo"] == download_binaries.DANMAKU2ASS_REPO


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


def test_is_license_name_matches_common_filenames():
    assert download_binaries._is_license_name("foo/bin/LICENSE.txt")
    assert download_binaries._is_license_name("GPLv3.txt")
    assert download_binaries._is_license_name("COPYING")
    assert not download_binaries._is_license_name("ffmpeg.exe")
    assert not download_binaries._is_license_name("README.md")
