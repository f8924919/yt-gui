"""yt_gui.yt_dlp_update のテスト。

対応 spec: [yt-dlp 本体の更新](../docs/spec/features/yt-dlp-update.md) の Phase A。
対応 arch: [yt_dlp_update.md](../docs/arch/yt_dlp_update.md) の Phase A。

照会・比較ロジックは UI 非依存の純関数なので Qt なしで検証する。HTTP は
`fetch` 引数で差し替えてオフラインで完結させる。
"""

import json

import pytest

from yt_gui.yt_dlp_update import (
    UpdateStatus,
    check_for_update,
    compare_versions,
    parse_latest_version,
)


def _pypi_payload(version: str) -> bytes:
    return json.dumps({"info": {"version": version}}).encode("utf-8")


def test_parse_latest_version_extracts_info_version() -> None:
    assert parse_latest_version(_pypi_payload("2026.06.09")) == "2026.06.09"


@pytest.mark.parametrize(
    "payload",
    [b"{}", b'{"info": {}}', b"not json", b'{"info": {"version": ""}}'],
    ids=["no_info", "no_version", "invalid_json", "empty_version"],
)
def test_parse_latest_version_raises_on_malformed(payload: bytes) -> None:
    with pytest.raises((ValueError, KeyError)):
        parse_latest_version(payload)


@pytest.mark.parametrize(
    "current, latest, expected",
    [
        ("2026.06.09", "2026.06.09", UpdateStatus.UP_TO_DATE),
        ("2026.05.01", "2026.06.09", UpdateStatus.UPDATE_AVAILABLE),
        ("2025.12.31", "2026.01.01", UpdateStatus.UPDATE_AVAILABLE),
        # 同梱版が最新版より新しい（開発版など）場合は最新扱い。
        ("2026.06.10", "2026.06.09", UpdateStatus.UP_TO_DATE),
    ],
    ids=["same", "older", "older_year_boundary", "newer_local"],
)
def test_compare_versions(current: str, latest: str, expected: UpdateStatus) -> None:
    assert compare_versions(current, latest) == expected


def test_check_for_update_returns_update_available_with_injected_fetch() -> None:
    result = check_for_update(
        "2026.05.01", fetch=lambda url: _pypi_payload("2026.06.09")
    )
    assert result.current == "2026.05.01"
    assert result.latest == "2026.06.09"
    assert result.status is UpdateStatus.UPDATE_AVAILABLE


def test_check_for_update_returns_up_to_date_with_injected_fetch() -> None:
    result = check_for_update(
        "2026.06.09", fetch=lambda url: _pypi_payload("2026.06.09")
    )
    assert result.status is UpdateStatus.UP_TO_DATE


def test_check_for_update_queries_pypi_url() -> None:
    seen: list[str] = []

    def fake_fetch(url: str) -> bytes:
        seen.append(url)
        return _pypi_payload("2026.06.09")

    check_for_update("2026.06.09", fetch=fake_fetch)
    assert seen == ["https://pypi.org/pypi/yt-dlp/json"]


def test_check_for_update_propagates_fetch_error() -> None:
    def failing_fetch(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(OSError):
        check_for_update("2026.06.09", fetch=failing_fetch)
