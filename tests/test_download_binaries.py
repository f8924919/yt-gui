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
    with pytest.raises(RuntimeError, match="pins.json"):
        download_binaries._verify_sha256(str(f), None, "test")


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
    assert download_binaries.DANMAKU2ASS_REF == pins["danmaku2ass"]["ref"]
    assert download_binaries.DANMAKU2ASS_REPO == pins["danmaku2ass"]["repo"]


# --- THIRD-PARTY-NOTICES 生成 ---------------------------------------------


def test_write_third_party_notices_lists_all_components(tmp_path):
    """全コンポーネントの名称・ライセンス・対応ソースが告知に含まれる。"""
    out = download_binaries.write_third_party_notices(str(tmp_path))
    assert os.path.basename(out) == "THIRD-PARTY-NOTICES.md"
    text = open(out, encoding="utf-8").read()
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
