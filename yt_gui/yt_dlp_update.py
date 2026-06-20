"""yt-dlp 同梱版のバージョン照会・更新チェック（Phase A）。

UI 非依存の純関数として、最新版の照会・解析・比較を提供する。最新版は
PyPI JSON API（`pypi.org/pypi/yt-dlp/json` の `info.version`）を stdlib
`urllib` で取得し、比較は `packaging.version` で行う。HTTP 部分は `fetch`
引数で差し替え可能にしてオフラインで単体テストできる形にしている。

設計の意図・接続点は [docs/arch/yt_dlp_update.md](../../docs/arch/yt_dlp_update.md)
の Phase A 節を参照。実体更新（side-load）は Phase B（別 Issue）で扱う。
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from packaging.version import Version

# 最新版の照会先（PyPI JSON API）。
PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
# 古い版のときに案内するリリースページ（yt-dlp 公式 GitHub releases）。
RELEASES_URL = "https://github.com/yt-dlp/yt-dlp/releases"


class UpdateStatus(Enum):
    """同梱版と最新版の比較結果。"""

    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"


@dataclass(frozen=True)
class UpdateCheckResult:
    """更新チェックの結果（同梱版・最新版・判定）。"""

    current: str
    latest: str
    status: UpdateStatus


def parse_latest_version(payload: str | bytes) -> str:
    """PyPI JSON レスポンスから `info.version` を取り出す純関数。

    JSON でない、`info` / `version` が無い、空文字などの不正な入力では
    `ValueError` / `KeyError` を送出する。
    """
    data = json.loads(payload)
    version = data["info"]["version"]
    if not isinstance(version, str) or not version:
        raise ValueError("PyPI レスポンスの info.version が不正です。")
    return version


def compare_versions(current: str, latest: str) -> UpdateStatus:
    """同梱版と最新版を比較し更新有無を返す純関数。

    日付ベースの yt-dlp バージョン（例 `2026.06.09`）を `packaging.version`
    で比較する。最新版が同梱版より新しいときだけ更新ありと判定し、同梱版が
    最新版以上（開発版など）の場合は最新扱いとする。
    """
    if Version(latest) > Version(current):
        return UpdateStatus.UPDATE_AVAILABLE
    return UpdateStatus.UP_TO_DATE


def _default_fetch(url: str) -> bytes:
    """stdlib `urllib` で URL を GET して本文を返す（既定の HTTP 実装）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "yt-gui"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return bytes(resp.read())


def check_for_update(
    current: str,
    *,
    fetch: Callable[[str], bytes] = _default_fetch,
) -> UpdateCheckResult:
    """最新版を照会し同梱版 `current` と比較する。

    HTTP は `fetch` 引数で差し替え可能（オフライン単体テスト用）。照会・解析・
    比較のいずれかで失敗した場合は例外を送出するので、呼び出し側（UI）は
    `on_failed` 等で穏当に通知すること。
    """
    payload = fetch(PYPI_URL)
    latest = parse_latest_version(payload)
    status = compare_versions(current, latest)
    return UpdateCheckResult(current=current, latest=latest, status=status)
