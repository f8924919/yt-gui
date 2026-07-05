"""アプリ本体（yt-gui）のバージョン照会・更新チェック。

UI 非依存の純関数として、最新版の照会・解析・比較を提供する。最新版は
GitHub Releases API（`releases/latest` の `tag_name`）を stdlib `urllib` で
取得し、比較は `yt_dlp_update.compare_versions` を再利用する。HTTP 部分は
`fetch` 引数で差し替え可能にしてオフラインで単体テストできる形にしている。

設計の意図・接続点は [docs/arch/app_update.md](../../docs/arch/app_update.md)
を参照。実体の自動更新（Phase B）は docs/research/app-update.md で検討中。
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable

from .yt_dlp_update import UpdateCheckResult, UpdateStatus, compare_versions

# 最新版の照会先（GitHub Releases API）。draft / prerelease は返らない。
GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/f8924919/yt-gui/releases/latest"
)
# 新版があるときに案内するリリースページ。
RELEASES_URL = "https://github.com/f8924919/yt-gui/releases"


def parse_latest_version(payload: str | bytes) -> str:
    """GitHub Releases API レスポンスから `tag_name` のバージョンを取り出す純関数。

    タグは `v{version}` 形式（例 `v0.4.0`）を前提とし、`v` prefix を除去して
    返す。JSON でない、`tag_name` が無い、`v` prefix が無い等の不正な入力では
    `ValueError` / `KeyError` を送出する（呼び出し側で「照会失敗」として扱う）。
    """
    data = json.loads(payload)
    tag_name = data["tag_name"]
    if not isinstance(tag_name, str) or not tag_name.startswith("v") or tag_name == "v":
        raise ValueError("GitHub レスポンスの tag_name が不正です。")
    return tag_name[1:]


def _default_fetch(url: str) -> bytes:
    """stdlib `urllib` で URL を GET して本文を返す（既定の HTTP 実装）。

    GitHub API は User-Agent ヘッダー必須。
    """
    req = urllib.request.Request(url, headers={"User-Agent": "yt-gui"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return bytes(resp.read())


def check_for_update(
    current: str,
    *,
    fetch: Callable[[str], bytes] = _default_fetch,
) -> UpdateCheckResult:
    """最新版を照会し現バージョン `current` と比較する。

    HTTP は `fetch` 引数で差し替え可能（オフライン単体テスト用）。照会・解析・
    比較のいずれかで失敗した場合は例外を送出するので、呼び出し側（UI）は
    `on_failed` 等で穏当に扱うこと（起動時はサイレント、手動時は警告表示）。
    """
    payload = fetch(GITHUB_LATEST_RELEASE_URL)
    latest = parse_latest_version(payload)
    status = compare_versions(current, latest)
    return UpdateCheckResult(current=current, latest=latest, status=status)


def should_check_on_startup(*, enabled: bool, current: str) -> bool:
    """起動時自動チェックを行うかを判定する純関数。

    オプトアウト設定が有効、またはパッケージメタデータ未解決
    （`current == "unknown"`、開発環境等）のときはチェックしない。
    """
    return enabled and current != "unknown"


def should_notify(result: UpdateCheckResult) -> bool:
    """起動時チェック結果を通知すべきかを判定する純関数（新版検出時のみ）。"""
    return result.status is UpdateStatus.UPDATE_AVAILABLE
