"""アプリ本体（yt-gui）の実体更新コア（Phase B-1）。

UI 非依存の関数群として、更新アーカイブのダウンロード（進捗・キャンセル
対応）・Sigstore attestation の検証・安全な展開を提供する。差し替え
（rename・ロールバック）と UI 接続は Phase B-2（#253）で扱う。

fail-closed を原則とし、あらゆる失敗は例外ではなく正規化された
`SelfUpdateResult` で呼び出し元へ返す。HTTP は `fetch` / `open_stream`、
sigstore 検証は `verify_bundle` の各引数で差し替え可能にしてオフラインで
単体テストできる形にしている。sigstore の import は関数内に遅延させ、
Phase A（更新チェック）経路・起動速度へ波及させない。

設計の意図・検証モデルは [docs/arch/self_update.md](../../docs/arch/self_update.md)
を参照。実装 Issue は #252。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .app_update import GITHUB_LATEST_RELEASE_URL, parse_latest_version
from .yt_dlp_update import UpdateStatus, compare_versions

# attestation バンドルの照会先（GitHub attestations API。public repo は無認証可）。
ATTESTATIONS_URL_TEMPLATE = (
    "https://api.github.com/repos/f8924919/yt-gui/attestations/sha256:{digest}"
)
# GitHub Actions の OIDC issuer（attestation 証明書の発行元として固定）。
GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
# 証明書 SAN の identity。ref はダウンロード対象バージョンのタグに完全一致で
# ピンする（緩いピンは同一 repo の別 workflow / 別 ref による署名を許すため）。
_IDENTITY_TEMPLATE = (
    "https://github.com/f8924919/yt-gui/.github/workflows/release.yml"
    "@refs/tags/v{version}"
)
# Windows 用配布アセット名（release.yml の成果物命名に一致させる）。
_WINDOWS_ASSET_TEMPLATE = "yt-gui-{version}-windows-x64.zip"

_DOWNLOAD_CHUNK_SIZE = 256 * 1024


class SelfUpdateStatus(Enum):
    """実体更新（ダウンロード〜展開）の結果種別。"""

    SUCCESS = "success"
    NOT_NEWER = "not_newer"
    ASSET_NOT_FOUND = "asset_not_found"
    NETWORK_ERROR = "network_error"
    CANCELLED = "cancelled"
    NO_ATTESTATION = "no_attestation"
    VERIFICATION_FAILED = "verification_failed"
    INVALID_ARCHIVE = "invalid_archive"


@dataclass(frozen=True)
class SelfUpdateResult:
    """実体更新の正規化された結果（失敗種別を UI が出し分けられる形）。"""

    status: SelfUpdateStatus
    version: str | None = None
    extracted_dir: Path | None = None


class _Cancelled(Exception):
    """ダウンロードのキャンセル要求（内部制御用。外へは漏らさない）。"""


def build_expected_identity(version: str) -> str:
    """attestation 証明書に要求する identity（SAN）を組み立てる純関数。"""
    return _IDENTITY_TEMPLATE.format(version=version)


def resolve_windows_asset(
    release: dict[str, Any], version: str
) -> tuple[str, str] | None:
    """リリース JSON の `assets[]` から Windows 用 zip を解決する純関数。

    `(アセット名, ダウンロード URL)` を返す。見つからなければ `None`。
    """
    expected = _WINDOWS_ASSET_TEMPLATE.format(version=version)
    for asset in release.get("assets", []):
        if asset.get("name") == expected and asset.get("browser_download_url"):
            return expected, str(asset["browser_download_url"])
    return None


def _is_unsafe_entry(name: str) -> bool:
    """zip エントリ名が展開先の外を指しうるか（zip slip / 絶対パス）を判定する。"""
    if PureWindowsPath(name).is_absolute() or PurePosixPath(name).is_absolute():
        return True
    if PureWindowsPath(name).drive:
        return True
    parts = PurePosixPath(name.replace("\\", "/")).parts
    return ".." in parts


def safe_extract(zip_path: Path, dest_dir: Path) -> None:
    """zip を検査してから `dest_dir` 配下へ展開する。

    zip slip（`..`）・絶対パス・ドライブ付きエントリを含む場合は 1 ファイルも
    展開せず `ValueError` を送出する。zip として不正な場合は
    `zipfile.BadZipFile` が送出される。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if _is_unsafe_entry(name):
                raise ValueError(f"zip エントリが展開先の外を指しています: {name}")
            # 念のため実パスでも封じ込めを確認する（判定漏れへの多重防御）。
            target = (dest_dir / name).resolve()
            if not target.is_relative_to(dest_resolved):
                raise ValueError(f"zip エントリが展開先の外を指しています: {name}")
        zf.extractall(dest_dir)


def _default_fetch(url: str) -> bytes:
    """stdlib `urllib` で URL を GET して本文を返す（既定の HTTP 実装）。

    GitHub API は User-Agent ヘッダー必須。
    """
    req = urllib.request.Request(url, headers={"User-Agent": "yt-gui"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return bytes(resp.read())


def _default_open_stream(url: str) -> tuple[int | None, Iterator[bytes]]:
    """URL をチャンク受信のイテレータとして開く（既定の DL 実装）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "yt-gui"})
    resp = urllib.request.urlopen(req, timeout=30)
    length = resp.headers.get("Content-Length")
    total = int(length) if length else None

    def chunks() -> Iterator[bytes]:
        with resp:
            while True:
                chunk = resp.read(_DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    return
                yield bytes(chunk)

    return total, chunks()


def _default_verify_bundle(
    bundle: dict[str, Any], identity: str, issuer: str
) -> dict[str, Any]:
    """sigstore-python で attestation バンドルを検証し in-toto Statement を返す。

    attest-build-provenance は DSSE / in-toto 形式のため `verify_dsse` を使う
    （`verify_artifact` は hashedrekord 用）。`verify_dsse` は subject digest と
    アセットの照合を行わないため、照合は呼び出し側で必ず行うこと。
    検証失敗時は sigstore の例外をそのまま送出する（呼び出し側で正規化）。
    """
    # 遅延 import: Phase A（更新チェック）経路・起動速度へ波及させない。
    from sigstore.models import Bundle
    from sigstore.verify import Verifier, policy

    parsed = Bundle.from_json(json.dumps(bundle))
    verifier = Verifier.production()
    pol = policy.Identity(identity=identity, issuer=issuer)
    _payload_type, payload = verifier.verify_dsse(parsed, pol)
    statement: dict[str, Any] = json.loads(payload)
    return statement


def _statement_matches_digest(statement: dict[str, Any], digest: str) -> bool:
    """in-toto Statement の subject digest が DL 実バイトの digest と一致するか。"""
    try:
        subjects = statement["subject"]
        return any(s.get("digest", {}).get("sha256") == digest for s in subjects)
    except KeyError, TypeError, AttributeError:
        return False


def _download(
    url: str,
    dest: Path,
    open_stream: Callable[[str], tuple[int | None, Iterator[bytes]]],
    progress: Callable[[int, int | None], None] | None,
    cancel: threading.Event | None,
) -> None:
    """`url` を `dest` へチャンク書き込みする（進捗通知・キャンセル対応）。"""
    total, chunks = open_stream(url)
    received = 0
    with dest.open("wb") as f:
        for chunk in chunks:
            if cancel is not None and cancel.is_set():
                raise _Cancelled
            f.write(chunk)
            received += len(chunk)
            if progress is not None:
                progress(received, total)
    if cancel is not None and cancel.is_set():
        raise _Cancelled


def _remove_quietly(path: Path) -> None:
    """中間生成物を残さないための後始末（失敗しても本処理の結果を変えない）。"""
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    except OSError:
        pass


def download_and_verify_update(
    current: str,
    work_dir: Path,
    *,
    fetch: Callable[[str], bytes] = _default_fetch,
    open_stream: Callable[
        [str], tuple[int | None, Iterator[bytes]]
    ] = _default_open_stream,
    verify_bundle: Callable[
        [dict[str, Any], str, str], dict[str, Any]
    ] = _default_verify_bundle,
    progress: Callable[[int, int | None], None] | None = None,
    cancel: threading.Event | None = None,
) -> SelfUpdateResult:
    """最新リリースをダウンロード・検証し `work_dir` 配下へ展開する。

    fail-closed: 検証が通るまで展開せず、あらゆる失敗は正規化された
    `SelfUpdateResult` で返す（例外を漏らさない）。成功時は展開済み
    ディレクトリのみを残し、中間生成物（zip・失敗時の部分ファイル）は
    すべて削除する。
    """
    # 1. 最新リリースの照会と単調性チェック（現行より新しい版のみ許容）。
    try:
        payload = fetch(GITHUB_LATEST_RELEASE_URL)
        release: dict[str, Any] = json.loads(payload)
        latest = parse_latest_version(payload)
        is_newer = compare_versions(current, latest) is UpdateStatus.UPDATE_AVAILABLE
    except Exception:
        return SelfUpdateResult(SelfUpdateStatus.NETWORK_ERROR)
    if not is_newer:
        return SelfUpdateResult(SelfUpdateStatus.NOT_NEWER, version=latest)

    resolved = resolve_windows_asset(release, latest)
    if resolved is None:
        return SelfUpdateResult(SelfUpdateStatus.ASSET_NOT_FOUND, version=latest)
    asset_name, asset_url = resolved

    # 2. ダウンロード（進捗・キャンセル対応。失敗時は部分ファイルを残さない）。
    work_dir.mkdir(parents=True, exist_ok=True)
    zip_path = work_dir / asset_name
    try:
        _download(asset_url, zip_path, open_stream, progress, cancel)
    except _Cancelled:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.CANCELLED, version=latest)
    except Exception:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.NETWORK_ERROR, version=latest)

    # 3. DL 実バイトの digest で attestation バンドルを取得する。
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    try:
        att_payload = fetch(ATTESTATIONS_URL_TEMPLATE.format(digest=digest))
        bundles = [att["bundle"] for att in json.loads(att_payload)["attestations"]]
    except urllib.error.HTTPError as exc:
        _remove_quietly(zip_path)
        status = (
            SelfUpdateStatus.NO_ATTESTATION
            if exc.code == 404
            else SelfUpdateStatus.NETWORK_ERROR
        )
        return SelfUpdateResult(status, version=latest)
    except Exception:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.NETWORK_ERROR, version=latest)
    if not bundles:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.NO_ATTESTATION, version=latest)

    # 4. 検証: ポリシー通過＋subject digest 一致の attestation が 1 件あれば成功。
    identity = build_expected_identity(latest)
    verified = False
    for bundle in bundles:
        try:
            statement = verify_bundle(bundle, identity, GITHUB_OIDC_ISSUER)
        except Exception:
            continue
        if _statement_matches_digest(statement, digest):
            verified = True
            break
    if not verified:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.VERIFICATION_FAILED, version=latest)

    # 5. 検証済み zip を安全に展開する（差し替えは Phase B-2 のスクリプト）。
    extract_dir = work_dir / f"yt-gui-{latest}-new"
    try:
        safe_extract(zip_path, extract_dir)
    except Exception:
        _remove_quietly(extract_dir)
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.INVALID_ARCHIVE, version=latest)
    _remove_quietly(zip_path)
    return SelfUpdateResult(
        SelfUpdateStatus.SUCCESS, version=latest, extracted_dir=extract_dir
    )
