"""yt_gui.self_update のテスト。

対応 spec: [アプリ本体の更新](../docs/spec/features/app-update.md)（Phase B）。
対応 arch: [self_update.md](../docs/arch/self_update.md)。

コアは UI 非依存の関数群なので Qt なしで検証する。HTTP は `fetch` /
`open_stream`、sigstore 検証は `verify_bundle` の差し替えでオフラインで
完結させる。失敗はすべて正規化された `SelfUpdateResult` で返り、例外を
漏らさないこと（fail-closed）を検証する。
"""

import email.message
import hashlib
import io
import json
import subprocess
import sys
import threading
import urllib.error
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from yt_gui.self_update import (
    ATTESTATIONS_URL_TEMPLATE,
    EXPECTED_IDENTITY,
    SelfUpdateResult,
    SelfUpdateStatus,
    download_and_verify_update,
    resolve_windows_asset,
    safe_extract,
)

ASSET_URL = "https://example.invalid/yt-gui-0.5.0-windows-x64.zip"


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _release_payload(tag: str, asset_names: list[str]) -> bytes:
    assets = [
        {"name": name, "browser_download_url": f"https://example.invalid/{name}"}
        for name in asset_names
    ]
    return json.dumps({"tag_name": tag, "assets": assets}).encode("utf-8")


def _attestations_payload(count: int = 1) -> bytes:
    return json.dumps(
        {"attestations": [{"bundle": {"idx": i}} for i in range(count)]}
    ).encode("utf-8")


def _statement_for(data: bytes) -> dict:
    return {"subject": [{"digest": {"sha256": hashlib.sha256(data).hexdigest()}}]}


def _make_fetch(
    release: bytes, attestations: bytes | Exception
) -> Callable[[str], bytes]:
    def fetch(url: str) -> bytes:
        if url.endswith("/releases/latest"):
            return release
        if isinstance(attestations, Exception):
            raise attestations
        return attestations

    return fetch


def _make_open_stream(
    data: bytes, chunk_size: int = 4
) -> Callable[[str], tuple[int | None, Iterator[bytes]]]:
    def open_stream(url: str) -> tuple[int | None, Iterator[bytes]]:
        chunks = (data[i : i + chunk_size] for i in range(0, len(data), chunk_size))
        return len(data), chunks

    return open_stream


def _accepting_verify(data: bytes) -> Callable[[dict, str, str], dict]:
    def verify_bundle(bundle: dict, identity: str, issuer: str) -> dict:
        return _statement_for(data)

    return verify_bundle


def _run_update(
    zip_data: bytes,
    work_dir: Path,
    *,
    current: str = "0.4.0",
    release: bytes | None = None,
    attestations: bytes | Exception | None = None,
    open_stream: Callable[[str], tuple[int | None, Iterator[bytes]]] | None = None,
    verify_bundle: Callable[[dict, str, str], dict] | None = None,
    progress: Callable[[int, int | None], None] | None = None,
    cancel: threading.Event | None = None,
) -> SelfUpdateResult:
    """既定は成功系で、引数で個別要素を失敗系に差し替えるテストドライバ。"""
    return download_and_verify_update(
        current,
        work_dir,
        fetch=_make_fetch(
            release
            if release is not None
            else _release_payload("v0.5.0", ["yt-gui-0.5.0-windows-x64.zip"]),
            attestations if attestations is not None else _attestations_payload(),
        ),
        open_stream=open_stream
        if open_stream is not None
        else _make_open_stream(zip_data),
        verify_bundle=verify_bundle
        if verify_bundle is not None
        else _accepting_verify(zip_data),
        progress=progress,
        cancel=cancel,
    )


# --- 純関数（アセット解決・identity 生成） ---


def test_resolve_windows_asset_matches_by_name() -> None:
    release = json.loads(
        _release_payload(
            "v0.5.0",
            ["yt-gui-0.5.0-macos-arm64.zip", "yt-gui-0.5.0-windows-x64.zip"],
        )
    )
    resolved = resolve_windows_asset(release, "0.5.0")
    assert resolved == (
        "yt-gui-0.5.0-windows-x64.zip",
        "https://example.invalid/yt-gui-0.5.0-windows-x64.zip",
    )


@pytest.mark.parametrize(
    "asset_names",
    [
        [],
        ["yt-gui-0.5.0-macos-arm64.zip"],
        ["yt-gui-0.4.0-windows-x64.zip"],
    ],
    ids=["no_assets", "other_os_only", "wrong_version"],
)
def test_resolve_windows_asset_returns_none_when_missing(
    asset_names: list[str],
) -> None:
    release = json.loads(_release_payload("v0.5.0", asset_names))
    assert resolve_windows_asset(release, "0.5.0") is None


def test_expected_identity_pins_release_workflow_on_main() -> None:
    # release.yml は main への push で起動するため SAN の ref は
    # refs/heads/main（タグ ref ではない。実 attestation で確認済み・#252）。
    assert EXPECTED_IDENTITY == (
        "https://github.com/f8924919/yt-gui/.github/workflows/release.yml"
        "@refs/heads/main"
    )


def test_attestations_url_template_uses_sha256_prefix() -> None:
    assert ATTESTATIONS_URL_TEMPLATE.format(digest="abc123") == (
        "https://api.github.com/repos/f8924919/yt-gui/attestations/sha256:abc123"
    )


# --- 成功系 ---


def test_download_and_verify_update_success(tmp_path: Path) -> None:
    zip_data = _make_zip({"yt-gui/yt-gui.exe": b"binary", "yt-gui/data.txt": b"x"})
    result = _run_update(zip_data, tmp_path)
    assert result.status is SelfUpdateStatus.SUCCESS
    assert result.version == "0.5.0"
    assert result.extracted_dir is not None
    assert (result.extracted_dir / "yt-gui" / "yt-gui.exe").read_bytes() == b"binary"
    # 成功時、展開済みディレクトリ以外の中間生成物（zip）は残さない。
    leftovers = [p for p in tmp_path.rglob("*.zip") if p.is_file()]
    assert leftovers == []


def test_download_and_verify_update_passes_pinned_identity_to_verifier(
    tmp_path: Path,
) -> None:
    zip_data = _make_zip({"a.txt": b"x"})
    seen: list[tuple[str, str]] = []

    def verify_bundle(bundle: dict, identity: str, issuer: str) -> dict:
        seen.append((identity, issuer))
        return _statement_for(zip_data)

    result = _run_update(zip_data, tmp_path, verify_bundle=verify_bundle)
    assert result.status is SelfUpdateStatus.SUCCESS
    assert seen == [(EXPECTED_IDENTITY, "https://token.actions.githubusercontent.com")]


def test_download_and_verify_update_accepts_second_attestation(
    tmp_path: Path,
) -> None:
    # 複数 attestation は 1 件ずつ検証し、1 件でも通過＋digest 一致なら成功。
    zip_data = _make_zip({"a.txt": b"x"})
    calls: list[int] = []

    def verify_bundle(bundle: dict, identity: str, issuer: str) -> dict:
        calls.append(bundle["idx"])
        if bundle["idx"] == 0:
            raise ValueError("signature mismatch")
        return _statement_for(zip_data)

    result = _run_update(
        zip_data,
        tmp_path,
        attestations=_attestations_payload(count=2),
        verify_bundle=verify_bundle,
    )
    assert result.status is SelfUpdateStatus.SUCCESS
    assert calls == [0, 1]


def test_progress_is_reported_monotonically(tmp_path: Path) -> None:
    zip_data = _make_zip({"a.txt": b"0123456789" * 10})
    seen: list[tuple[int, int | None]] = []
    result = _run_update(
        zip_data, tmp_path, progress=lambda done, total: seen.append((done, total))
    )
    assert result.status is SelfUpdateStatus.SUCCESS
    assert len(seen) > 1
    received = [done for done, _total in seen]
    assert received == sorted(received)
    assert received[-1] == len(zip_data)
    assert all(total == len(zip_data) for _done, total in seen)


# --- 失敗系（すべて正規化された結果型で返り、例外を漏らさない） ---


def test_not_newer_skips_download(tmp_path: Path) -> None:
    zip_data = _make_zip({"a.txt": b"x"})
    opened: list[str] = []

    def open_stream(url: str) -> tuple[int | None, Iterator[bytes]]:
        opened.append(url)
        return len(zip_data), iter([zip_data])

    result = _run_update(
        zip_data,
        tmp_path,
        current="0.5.0",
        release=_release_payload("v0.5.0", ["yt-gui-0.5.0-windows-x64.zip"]),
        open_stream=open_stream,
    )
    assert result.status is SelfUpdateStatus.NOT_NEWER
    assert opened == []


def test_asset_not_found(tmp_path: Path) -> None:
    result = _run_update(
        _make_zip({"a.txt": b"x"}),
        tmp_path,
        release=_release_payload("v0.5.0", ["yt-gui-0.5.0-macos-arm64.zip"]),
    )
    assert result.status is SelfUpdateStatus.ASSET_NOT_FOUND


def test_release_query_failure_is_normalized(tmp_path: Path) -> None:
    def failing_fetch(url: str) -> bytes:
        raise OSError("offline")

    result = download_and_verify_update(
        "0.4.0",
        tmp_path,
        fetch=failing_fetch,
        open_stream=_make_open_stream(b""),
        verify_bundle=_accepting_verify(b""),
    )
    assert result.status is SelfUpdateStatus.NETWORK_ERROR


def test_download_failure_cleans_partial_file(tmp_path: Path) -> None:
    def open_stream(url: str) -> tuple[int | None, Iterator[bytes]]:
        def chunks() -> Iterator[bytes]:
            yield b"part"
            raise TimeoutError("stalled")

        return 100, chunks()

    result = _run_update(_make_zip({"a.txt": b"x"}), tmp_path, open_stream=open_stream)
    assert result.status is SelfUpdateStatus.NETWORK_ERROR
    assert list(tmp_path.iterdir()) == []


def test_cancel_stops_download_and_cleans_up(tmp_path: Path) -> None:
    zip_data = _make_zip({"a.txt": b"0123456789" * 100})
    cancel = threading.Event()

    def progress(done: int, total: int | None) -> None:
        cancel.set()

    result = _run_update(
        zip_data,
        tmp_path,
        open_stream=_make_open_stream(zip_data, chunk_size=16),
        progress=progress,
        cancel=cancel,
    )
    assert result.status is SelfUpdateStatus.CANCELLED
    assert list(tmp_path.iterdir()) == []


def test_attestation_http_404_means_no_attestation(tmp_path: Path) -> None:
    err = urllib.error.HTTPError(
        "https://api.github.com/", 404, "Not Found", email.message.Message(), None
    )
    result = _run_update(_make_zip({"a.txt": b"x"}), tmp_path, attestations=err)
    assert result.status is SelfUpdateStatus.NO_ATTESTATION


def test_attestation_fetch_failure_is_network_error(tmp_path: Path) -> None:
    result = _run_update(
        _make_zip({"a.txt": b"x"}), tmp_path, attestations=OSError("offline")
    )
    assert result.status is SelfUpdateStatus.NETWORK_ERROR


def test_empty_attestations_means_no_attestation(tmp_path: Path) -> None:
    result = _run_update(
        _make_zip({"a.txt": b"x"}),
        tmp_path,
        attestations=json.dumps({"attestations": []}).encode("utf-8"),
    )
    assert result.status is SelfUpdateStatus.NO_ATTESTATION


def test_verifier_rejection_is_verification_failed(tmp_path: Path) -> None:
    # identity 不一致・署名不正などで sigstore 検証が例外を出すケース。
    def rejecting_verify(bundle: dict, identity: str, issuer: str) -> dict:
        raise ValueError("identity mismatch")

    result = _run_update(
        _make_zip({"a.txt": b"x"}), tmp_path, verify_bundle=rejecting_verify
    )
    assert result.status is SelfUpdateStatus.VERIFICATION_FAILED


def test_subject_digest_mismatch_is_verification_failed(tmp_path: Path) -> None:
    # 検証自体は通っても subject digest が DL 実バイトと一致しなければ失敗。
    def wrong_digest_verify(bundle: dict, identity: str, issuer: str) -> dict:
        return _statement_for(b"different bytes")

    result = _run_update(
        _make_zip({"a.txt": b"x"}), tmp_path, verify_bundle=wrong_digest_verify
    )
    assert result.status is SelfUpdateStatus.VERIFICATION_FAILED


def test_verification_failure_cleans_downloaded_zip(tmp_path: Path) -> None:
    def rejecting_verify(bundle: dict, identity: str, issuer: str) -> dict:
        raise ValueError("bad")

    _run_update(_make_zip({"a.txt": b"x"}), tmp_path, verify_bundle=rejecting_verify)
    assert list(tmp_path.iterdir()) == []


def test_invalid_zip_is_normalized(tmp_path: Path) -> None:
    result = _run_update(b"this is not a zip file", tmp_path)
    assert result.status is SelfUpdateStatus.INVALID_ARCHIVE


def test_unexpected_verifier_exception_does_not_leak(tmp_path: Path) -> None:
    def broken_verify(bundle: dict, identity: str, issuer: str) -> dict:
        raise RuntimeError("unexpected internal error")

    result = _run_update(
        _make_zip({"a.txt": b"x"}), tmp_path, verify_bundle=broken_verify
    )
    assert result.status is SelfUpdateStatus.VERIFICATION_FAILED


# --- 安全展開（zip slip / 絶対パス対策） ---


def test_safe_extract_extracts_normal_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "ok.zip"
    zip_path.write_bytes(_make_zip({"dir/file.txt": b"content"}))
    dest = tmp_path / "out"
    safe_extract(zip_path, dest)
    assert (dest / "dir" / "file.txt").read_bytes() == b"content"


@pytest.mark.parametrize(
    "entry_name",
    ["../evil.txt", "dir/../../evil.txt", "/abs.txt", "C:/evil.txt"],
    ids=["parent_traversal", "nested_traversal", "rooted", "drive_absolute"],
)
def test_safe_extract_rejects_unsafe_entries(tmp_path: Path, entry_name: str) -> None:
    zip_path = tmp_path / "evil.zip"
    zip_path.write_bytes(_make_zip({entry_name: b"pwned"}))
    dest = tmp_path / "out"
    with pytest.raises(ValueError):
        safe_extract(zip_path, dest)
    # 展開先の外にファイルを作っていないこと。
    assert not (tmp_path / "evil.txt").exists()


def test_zip_slip_via_orchestrator_is_invalid_archive(tmp_path: Path) -> None:
    result = _run_update(_make_zip({"../evil.txt": b"pwned"}), tmp_path)
    assert result.status is SelfUpdateStatus.INVALID_ARCHIVE
    assert not (tmp_path.parent / "evil.txt").exists()


# --- 遅延 import（Phase A 経路へ波及させない） ---


def test_sigstore_is_not_imported_at_module_import() -> None:
    # 別プロセスで検証する（本プロセスは他テストの import 状況に依存するため）。
    code = (
        "import sys; import yt_gui.self_update; import yt_gui.app_update; "
        "assert not any(m == 'sigstore' or m.startswith('sigstore.') "
        "for m in sys.modules), 'sigstore must be lazily imported'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
