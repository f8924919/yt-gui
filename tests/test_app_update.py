"""yt_gui.app_update のテスト。

対応 spec: [アプリ本体の更新](../docs/spec/features/app-update.md)。
対応 arch: [app_update.md](../docs/arch/app_update.md)。

照会・解析ロジックは UI 非依存の純関数なので Qt なしで検証する。HTTP は
`fetch` 引数で差し替えてオフラインで完結させる。
"""

import json

import pytest

from yt_gui.app_update import (
    GITHUB_LATEST_RELEASE_URL,
    check_for_update,
    parse_latest_version,
    should_check_on_startup,
    should_notify,
)
from yt_gui.yt_dlp_update import UpdateCheckResult, UpdateStatus


def _github_payload(tag_name: str) -> bytes:
    return json.dumps({"tag_name": tag_name}).encode("utf-8")


def test_parse_latest_version_strips_v_prefix() -> None:
    assert parse_latest_version(_github_payload("v0.4.0")) == "0.4.0"


@pytest.mark.parametrize(
    "payload",
    [
        b"{}",
        b"not json",
        b'{"tag_name": ""}',
        b'{"tag_name": "0.4.0"}',
        b'{"tag_name": 40}',
    ],
    ids=["no_tag_name", "invalid_json", "empty_tag", "no_v_prefix", "non_string"],
)
def test_parse_latest_version_raises_on_malformed(payload: bytes) -> None:
    with pytest.raises((ValueError, KeyError)):
        parse_latest_version(payload)


def test_check_for_update_returns_update_available_with_injected_fetch() -> None:
    result = check_for_update("0.4.0", fetch=lambda url: _github_payload("v0.5.0"))
    assert result.current == "0.4.0"
    assert result.latest == "0.5.0"
    assert result.status is UpdateStatus.UPDATE_AVAILABLE


def test_check_for_update_returns_up_to_date_with_injected_fetch() -> None:
    result = check_for_update("0.4.0", fetch=lambda url: _github_payload("v0.4.0"))
    assert result.status is UpdateStatus.UP_TO_DATE


def test_check_for_update_treats_newer_local_as_up_to_date() -> None:
    # 現バージョンが最新リリースより新しい（開発版など）場合は最新扱い。
    result = check_for_update("0.5.0.dev1", fetch=lambda url: _github_payload("v0.4.0"))
    assert result.status is UpdateStatus.UP_TO_DATE


def test_check_for_update_queries_github_latest_release_url() -> None:
    seen: list[str] = []

    def fake_fetch(url: str) -> bytes:
        seen.append(url)
        return _github_payload("v0.4.0")

    check_for_update("0.4.0", fetch=fake_fetch)
    assert seen == [GITHUB_LATEST_RELEASE_URL]
    assert seen == ["https://api.github.com/repos/f8924919/yt-gui/releases/latest"]


def test_check_for_update_propagates_fetch_error() -> None:
    def failing_fetch(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(OSError):
        check_for_update("0.4.0", fetch=failing_fetch)


def test_check_for_update_raises_on_invalid_version_tag() -> None:
    # タグがバージョンとして不正な場合も「照会失敗」（例外）として扱う。
    with pytest.raises(ValueError):
        check_for_update("0.4.0", fetch=lambda url: _github_payload("vnot-a-version"))


@pytest.mark.parametrize(
    "enabled, current, expected",
    [
        (True, "0.4.0", True),
        (False, "0.4.0", False),
        # メタデータ未解決（開発環境等）は自動チェックをスキップする。
        (True, "unknown", False),
        (False, "unknown", False),
    ],
    ids=["enabled", "opted_out", "unknown_version", "opted_out_and_unknown"],
)
def test_should_check_on_startup(enabled: bool, current: str, expected: bool) -> None:
    assert should_check_on_startup(enabled=enabled, current=current) is expected


@pytest.mark.parametrize(
    "status, expected",
    [
        (UpdateStatus.UPDATE_AVAILABLE, True),
        (UpdateStatus.UP_TO_DATE, False),
    ],
    ids=["update_available", "up_to_date"],
)
def test_should_notify_only_on_update_available(
    status: UpdateStatus, expected: bool
) -> None:
    result = UpdateCheckResult(current="0.4.0", latest="0.5.0", status=status)
    assert should_notify(result) is expected
