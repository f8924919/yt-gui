"""`scripts/download_binaries.py` の BtbN ffmpeg アセット解決ロジックのテスト。

`scripts/` はパッケージではないため、ファイルパスから直接ロードする。
"""

import importlib.util
import os

import pytest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "download_binaries.py",
)
_spec = importlib.util.spec_from_file_location("download_binaries", _SCRIPT)
download_binaries = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(download_binaries)

_select = download_binaries._select_btbn_win64_gpl_asset


def _asset(name: str) -> dict:
    return {"name": name, "browser_download_url": f"https://example/{name}"}


def test_selects_master_latest_static_gpl():
    """現行の固定名 `ffmpeg-master-latest-win64-gpl.zip` を選ぶ。"""
    assets = [
        _asset("ffmpeg-master-latest-win64-gpl-shared.zip"),
        _asset("ffmpeg-master-latest-win64-gpl.zip"),
        _asset("ffmpeg-n7.1-latest-win64-gpl-7.1.zip"),
        _asset("ffmpeg-n8.1-latest-win64-gpl-8.1.zip"),
    ]
    assert _select(assets) == "https://example/ffmpeg-master-latest-win64-gpl.zip"


def test_selects_hash_named_form():
    """過去のコミットハッシュ付き名にも対応する。"""
    assets = [
        _asset("ffmpeg-N-118037-g1234abcd-win64-gpl-shared.zip"),
        _asset("ffmpeg-N-118037-g1234abcd-win64-gpl.zip"),
    ]
    assert _select(assets) == "https://example/ffmpeg-N-118037-g1234abcd-win64-gpl.zip"


def test_excludes_shared_and_stable():
    """shared 版・安定版 nX.Y のみの場合はマッチせず RuntimeError。"""
    assets = [
        _asset("ffmpeg-master-latest-win64-gpl-shared.zip"),
        _asset("ffmpeg-n7.1-latest-win64-gpl-7.1.zip"),
        _asset("ffmpeg-master-latest-win64-lgpl.zip"),
    ]
    with pytest.raises(RuntimeError):
        _select(assets)


def test_empty_assets_raises():
    with pytest.raises(RuntimeError):
        _select([])
