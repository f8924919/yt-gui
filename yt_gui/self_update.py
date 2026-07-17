"""アプリ本体（yt-gui）の実体更新（Phase B）。

UI 非依存の関数群として、更新アーカイブのダウンロード（進捗・キャンセル
対応）・Sigstore attestation の検証・安全な展開（B-1 = #252）と、Windows
での適用（プリフライト・差し替え PowerShell スクリプトの生成/起動・残骸
掃除。B-2 = #253）を提供する。UI 接続は `app.py` 側が担う。

fail-closed を原則とし、あらゆる失敗は例外ではなく正規化された
`SelfUpdateResult` で呼び出し元へ返す。HTTP は `fetch` / `open_stream`、
sigstore 検証は `verify_bundle` の各引数で差し替え可能にしてオフラインで
単体テストできる形にしている。sigstore の import は関数内に遅延させ、
Phase A（更新チェック）経路・起動速度へ波及させない。

設計の意図・検証モデルは [docs/arch/self_update.md](../../docs/arch/self_update.md)
を参照。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
# 証明書 SAN の identity（完全一致でピン）。release.yml は main への push で
# 起動しタグを同一実行内で作成するため、SAN の ref は refs/heads/main になる
# （タグ ref ではない。実 attestation で確認済み・#252）。バージョンとの
# 紐付けは subject digest 照合と単調性チェックが担う。
EXPECTED_IDENTITY = (
    "https://github.com/f8924919/yt-gui/.github/workflows/release.yml@refs/heads/main"
)
# Windows 用配布アセット名（release.yml の成果物命名に一致させる）。
_WINDOWS_ASSET_TEMPLATE = "yt-gui-{version}-windows-x64.zip"

_DOWNLOAD_CHUNK_SIZE = 256 * 1024

# bundle_url 応答（snappy 圧縮バンドル）の非圧縮長上限。実測 約 11 KB のため
# 十分な余裕を持たせつつ、展開爆弾を封じる（#262）。
_MAX_BUNDLE_SIZE = 10 * 1024 * 1024


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


def _decode_raw_snappy(data: bytes, max_size: int = _MAX_BUNDLE_SIZE) -> bytes:
    """raw snappy block format（framing なし）を展開する。

    attestations API の bundle_url 応答（`Content-Type: application/x-snappy`）
    の展開に必要な最小の純 Python 実装（展開のみ・依存追加なし。#262）。
    外部から届くデータを扱うため fail-closed: 不正 varint・copy オフセット
    範囲外・宣言長との不一致・`max_size` 超過はすべて `ValueError`。
    """
    # 非圧縮長ヘッダー（little-endian の 7 bit varint）。
    pos = 0
    length = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ValueError("snappy: 長さヘッダーが途中で終わっています")
        byte = data[pos]
        pos += 1
        length |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
        if shift >= 35:
            raise ValueError("snappy: 長さヘッダーが長すぎます")
    if length > max_size:
        raise ValueError(f"snappy: 非圧縮長 {length} が上限 {max_size} を超えています")

    out = bytearray()
    while pos < len(data):
        tag = data[pos]
        pos += 1
        kind = tag & 0x03
        if kind == 0:  # literal
            size = (tag >> 2) + 1
            if size > 60:  # 長さは追加バイト（1〜4）で表される
                extra = size - 60
                if pos + extra > len(data):
                    raise ValueError("snappy: literal 長のバイトが不足しています")
                size = int.from_bytes(data[pos : pos + extra], "little") + 1
                pos += extra
            if pos + size > len(data):
                raise ValueError("snappy: literal 本体が不足しています")
            out += data[pos : pos + size]
            pos += size
        else:  # copy（既出力からの後方参照。offset < size の重なり複製あり）
            if kind == 1:
                size = ((tag >> 2) & 0x07) + 4
                if pos >= len(data):
                    raise ValueError("snappy: copy オフセットが不足しています")
                offset = ((tag & 0xE0) << 3) | data[pos]
                pos += 1
            else:
                width = 2 if kind == 2 else 4
                size = (tag >> 2) + 1
                if pos + width > len(data):
                    raise ValueError("snappy: copy オフセットが不足しています")
                offset = int.from_bytes(data[pos : pos + width], "little")
                pos += width
            if offset == 0 or offset > len(out):
                raise ValueError("snappy: copy オフセットが出力範囲外です")
            for _ in range(size):
                out.append(out[-offset])
        if len(out) > length:
            raise ValueError("snappy: 出力が宣言された非圧縮長を超えています")
    if len(out) != length:
        raise ValueError("snappy: 出力長が宣言された非圧縮長と一致しません")
    return bytes(out)


def _parse_bundle_bytes(raw: bytes) -> dict[str, Any]:
    """bundle_url 応答をバンドル dict へ変換する（#262）。

    現行の snappy 圧縮（raw block format）と、素の JSON（将来の仕様変更への
    耐性）の両方を受け付ける。判別は先頭バイト: JSON オブジェクトは必ず
    `{` で始まり、実バンドルの snappy は多バイト varint（先頭バイトの
    継続ビットが立つ）で始まるため衝突しない。
    """
    text = raw if raw.lstrip()[:1] == b"{" else _decode_raw_snappy(raw)
    bundle = json.loads(text)
    if not isinstance(bundle, dict):
        raise ValueError("bundle が JSON オブジェクトではありません")
    return bundle


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

    # 3. DL 実バイトの digest で attestation の一覧を取得する。
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    try:
        att_payload = fetch(ATTESTATIONS_URL_TEMPLATE.format(digest=digest))
        attestations = json.loads(att_payload)["attestations"]
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
    if not attestations:
        _remove_quietly(zip_path)
        return SelfUpdateResult(SelfUpdateStatus.NO_ATTESTATION, version=latest)

    # 3.5. バンドル解決（#262）: API version 2026-03-10 で `bundle` 埋め込みが
    # 廃止され `bundle_url` 参照になったため、attestation 1 件ごとに
    # 埋め込み → bundle_url の順で解決する。解決できないものはスキップし、
    # bundle_url の取得失敗だけはネットワーク起因として全滅時に区別する。
    bundles: list[dict[str, Any]] = []
    network_skip = False
    for att in attestations:
        if not isinstance(att, dict):
            continue
        bundle = att.get("bundle")
        if isinstance(bundle, dict):
            bundles.append(bundle)
            continue
        bundle_url = att.get("bundle_url")
        if not bundle_url:
            continue
        try:
            raw = fetch(bundle_url)
        except Exception:
            network_skip = True
            continue
        try:
            bundles.append(_parse_bundle_bytes(raw))
        except Exception:
            continue

    # 4. 検証: ポリシー通過＋subject digest 一致の attestation が 1 件あれば成功。
    verified = False
    for bundle in bundles:
        try:
            statement = verify_bundle(bundle, EXPECTED_IDENTITY, GITHUB_OIDC_ISSUER)
        except Exception:
            continue
        if _statement_matches_digest(statement, digest):
            verified = True
            break
    if not verified:
        _remove_quietly(zip_path)
        status = (
            SelfUpdateStatus.NETWORK_ERROR
            if network_skip
            else SelfUpdateStatus.VERIFICATION_FAILED
        )
        return SelfUpdateResult(status, version=latest)

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


# ═══════════════════════════════════════════════════════════════════════════
# Phase B-2: 適用（プリフライト・差し替えスクリプト・残骸掃除。#253）
# ═══════════════════════════════════════════════════════════════════════════

# インストール先の兄弟に作る退避 / ステージングの接尾辞。フォルダ名基準で
# 導出するため、ユーザーがインストールフォルダをリネームしていても追従する。
_BACKUP_SUFFIX = ".bak"
_STAGING_SUFFIX = ".update-staging"


def get_install_dir() -> Path | None:
    """PyInstaller バンドル実行時のインストール先（exe のあるフォルダ）を返す。

    非 frozen（開発環境）では `None`。実体更新の無効化を兼ねる。
    """
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).parent


def is_parent_writable(install_dir: Path) -> bool:
    """インストール先の**親ディレクトリ**へ書き込めるかを一時ファイルで判定する。

    差し替えは親ディレクトリでのフォルダ rename（＋ステージング作成）で行う
    ため、判定対象はインストール先自身ではなく親（UAC 昇格は持ち込まない）。
    """
    try:
        with tempfile.NamedTemporaryFile(
            dir=install_dir.parent, prefix=".yt-gui-write-check-"
        ):
            pass
    except OSError:
        return False
    return True


def can_self_update(*, platform: str, current: str, install_dir: Path | None) -> bool:
    """「更新して再起動」を提示できるか（プリフライトの集約判定）。

    Windows・バンドル実行・バージョン解決済み・親ディレクトリ書き込み可を
    すべて満たすときのみ真。判定材料は引数注入（テスト可能性のため）。
    """
    if platform != "win32" or current == "unknown" or install_dir is None:
        return False
    return is_parent_writable(install_dir)


def resolve_staging_dir(install_dir: Path) -> Path:
    """ステージング先（インストール先と同じ親 = 同一ボリューム rename 保証）。"""
    return install_dir.parent / (install_dir.name + _STAGING_SUFFIX)


def resolve_backup_dir(install_dir: Path) -> Path:
    """旧版の退避先（`.bak`・1 世代のみ）。"""
    return install_dir.parent / (install_dir.name + _BACKUP_SUFFIX)


def looks_like_app_dir(new_dir: Path, exe_name: str) -> bool:
    """展開結果のルート直下に実行ファイルがあるか（差し替え前の健全性確認）。

    release.yml の zip はルートプレフィックスなし（`dist/yt-gui/*` を直下に
    固める）ため、展開ディレクトリ直下に exe が来るのが正常。
    """
    try:
        return (new_dir / exe_name).is_file()
    except OSError:
        return False


def cleanup_leftovers(install_dir: Path) -> None:
    """前回更新の残骸（`.bak`・ステージング）を削除する。

    次回起動のメインウィンドウ表示後（簡易ヘルスチェック通過後）と、更新
    開始時に呼ぶ。失敗はサイレントに次回へ持ち越す（起動を妨げない）。
    """
    _remove_quietly(resolve_backup_dir(install_dir))
    _remove_quietly(resolve_staging_dir(install_dir))


def _ps_quote(value: object) -> str:
    """PowerShell のシングルクォートリテラルとして安全に埋め込む。

    パスはユーザー環境由来で `'`・`$`・バッククォートを含みうる。シングル
    クォートリテラルは `$`・バッククォートを展開しないため、`'` の二重化
    のみで安全になる。
    """
    return "'" + str(value).replace("'", "''") + "'"


# 差し替えスクリプトの本体。プレースホルダ（@@...@@）を `build_replace_script`
# が埋める（PowerShell は `{}` と `$` を多用するため f-string / Template は
# 使わない）。exit code: 0=成功 / 1=PID 待機タイムアウト / 2=失敗（インストール
# は無傷または復旧済み） / 3=二重失敗（ロールバックも失敗）。
_REPLACE_SCRIPT_TEMPLATE = r"""# yt-gui self-update replace script (auto-generated)
$ErrorActionPreference = 'Stop'
$installDir = @@INSTALL@@
$newDir = @@NEW@@
$backupDir = @@BACKUP@@
$stagingDir = @@STAGING@@
$exeRelPath = @@EXE@@
$procName = @@PROC_NAME@@
$targetPid = @@TARGET_PID@@
$exePath = Join-Path $installDir $exeRelPath
$scriptPath = $MyInvocation.MyCommand.Path

function Invoke-WithRetry([scriptblock] $Action) {
    # AV / OneDrive の一時ロックを想定した指数バックオフ。
    $delay = @@RETRY_INITIAL_MS@@
    for ($i = 0; $i -lt @@RETRY_COUNT@@; $i++) {
        try {
            & $Action
            return $true
        } catch {
            Start-Sleep -Milliseconds $delay
            $delay = [Math]::Min($delay * 2, 8000)
        }
    }
    return $false
}

function Remove-Self {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
}

function Start-App {
    # 起動失敗は差し替え結果に影響させない（配置済み・手動起動可能）。
    try { Start-Process -FilePath $exePath -WorkingDirectory $installDir } catch { }
}

# 1. 旧プロセスの終了を待つ。PID 再利用の誤検知を避けるためプロセス名も照合。
$deadline = (Get-Date).AddSeconds(@@WAIT_TIMEOUT_SEC@@)
while ($true) {
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($null -eq $proc -or $proc.ProcessName -ne $procName) { break }
    if ((Get-Date) -gt $deadline) {
        # タイムアウト: インストール先へ一切触れず中断する。
        Remove-Self
        exit 1
    }
    Start-Sleep -Milliseconds 200
}

# 2. 既存 .bak の削除（1 世代のみ）→ 旧 → .bak 退避 → 新 → 旧パス配置。
$renamedOld = $false
$ok = $true
if (Test-Path -LiteralPath $backupDir) {
    $ok = Invoke-WithRetry { Remove-Item -LiteralPath $backupDir -Recurse -Force }
}
if ($ok) {
    $ok = Invoke-WithRetry {
        Move-Item -LiteralPath $installDir -Destination $backupDir
    }
    if ($ok) { $renamedOld = $true }
}
if ($ok) {
    $ok = Invoke-WithRetry { Move-Item -LiteralPath $newDir -Destination $installDir }
}
if ($ok) {
    # 成功: 新 exe を起動し、ステージング残骸を掃除して自己削除する。
    Start-App
    if (Test-Path -LiteralPath $stagingDir) {
        $null = Invoke-WithRetry {
            Remove-Item -LiteralPath $stagingDir -Recurse -Force
        }
    }
    Remove-Self
    exit 0
}
if ($renamedOld) {
    # 失敗: .bak を書き戻すロールバック。成功すれば旧版を起動し直す
    # （バージョン不変が実質的な失敗通知になる）。
    $restored = Invoke-WithRetry {
        Move-Item -LiteralPath $backupDir -Destination $installDir
    }
    if ($restored) {
        Start-App
        Remove-Self
        exit 2
    }
    # 二重失敗: .bak・ステージングを残し、手動復旧を案内する。
@@FAILURE_DIALOG@@
    Remove-Self
    exit 3
}
# 何も変更していない失敗（.bak 掃除不能・退避 rename 失敗）: 旧版を起動し直す。
Start-App
Remove-Self
exit 2
"""

_FAILURE_DIALOG_SNIPPET = r"""    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    [System.Windows.Forms.MessageBox]::Show(
        "yt-gui update failed and automatic recovery also failed.`n" +
        "Your previous version is preserved at:`n$backupDir`n" +
        "Rename it back to restore the app.",
        'yt-gui'
    ) | Out-Null"""


def build_replace_script(
    *,
    install_dir: Path,
    new_dir: Path,
    pid: int,
    exe_relpath: str,
    wait_timeout_sec: int = 60,
    retry_count: int = 8,
    retry_initial_ms: int = 250,
    show_dialog_on_failure: bool = True,
) -> str:
    """差し替え PowerShell スクリプトのソースを組み立てる純関数。

    待機・リトライ値はテストが短い値を注入して実スクリプトを高速実行する
    ための引数。`show_dialog_on_failure=False` は二重失敗テストで
    MessageBox がブロックしないための注入点（本番は既定 True）。
    """
    dialog = _FAILURE_DIALOG_SNIPPET if show_dialog_on_failure else ""
    replacements = {
        "@@INSTALL@@": _ps_quote(install_dir),
        "@@NEW@@": _ps_quote(new_dir),
        "@@BACKUP@@": _ps_quote(resolve_backup_dir(install_dir)),
        "@@STAGING@@": _ps_quote(resolve_staging_dir(install_dir)),
        "@@EXE@@": _ps_quote(exe_relpath),
        "@@PROC_NAME@@": _ps_quote(Path(exe_relpath).stem),
        "@@TARGET_PID@@": str(int(pid)),
        "@@WAIT_TIMEOUT_SEC@@": str(int(wait_timeout_sec)),
        "@@RETRY_COUNT@@": str(int(retry_count)),
        "@@RETRY_INITIAL_MS@@": str(int(retry_initial_ms)),
        "@@FAILURE_DIALOG@@": dialog,
    }
    script = _REPLACE_SCRIPT_TEMPLATE
    for token, value in replacements.items():
        script = script.replace(token, value)
    return script


def _default_spawn(argv: list[str]) -> None:
    """スクリプトをアプリから切り離したプロセスとして起動する（Windows 前提）。

    CREATE_NO_WINDOW（隠しコンソール）を使う。DETACHED_PROCESS はコンソール
    自体を与えず PowerShell が起動直後に死ぬため併用しない（両者は排他。
    #253 の E2E で検出）。Windows の子プロセスは親終了後も生存するため、
    これでアプリ終了後の差し替えが成立する。
    """
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    subprocess.Popen(argv, creationflags=creationflags, close_fds=True)


def launch_replace_script(
    script_text: str,
    *,
    script_dir: Path | None = None,
    spawn: Callable[[list[str]], None] = _default_spawn,
) -> bool:
    """スクリプトを対象ツリー外（%TEMP%）へ書き出して起動する。

    書き出し・起動の失敗は例外を漏らさず `False` で返す（呼び出し側は
    アプリを終了せず「更新失敗」通知へ戻る）。GPO で ExecutionPolicy を
    強制する環境では Bypass が効かない（spec の既知の制限）。
    """
    script_path: Path | None = None
    try:
        base = script_dir if script_dir is not None else Path(tempfile.gettempdir())
        fd, raw_path = tempfile.mkstemp(
            prefix="yt-gui-replace-", suffix=".ps1", dir=base
        )
        os.close(fd)
        script_path = Path(raw_path)
        # PowerShell 5.1 が非 ASCII パスを正しく読めるよう BOM 付き UTF-8。
        script_path.write_text(script_text, encoding="utf-8-sig")
        spawn(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ]
        )
    except Exception:
        if script_path is not None:
            _remove_quietly(script_path)
        return False
    return True
