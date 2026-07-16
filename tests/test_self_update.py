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
import shutil
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
    build_replace_script,
    can_self_update,
    cleanup_leftovers,
    download_and_verify_update,
    get_install_dir,
    is_parent_writable,
    launch_replace_script,
    looks_like_app_dir,
    resolve_backup_dir,
    resolve_staging_dir,
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


# ═══════════════════════════════════════════════════════════════════════════
# Phase B-2: プリフライト・差し替えスクリプト・残骸掃除（#253）
# ═══════════════════════════════════════════════════════════════════════════

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="PowerShell 実行テストは Windows 限定"
)


# --- インストール先の特定（frozen 判定） ---


def test_get_install_dir_returns_none_when_not_frozen(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert get_install_dir() is None


def test_get_install_dir_returns_exe_parent_when_frozen(
    monkeypatch, tmp_path: Path
) -> None:
    exe = tmp_path / "apps" / "yt-gui" / "yt-gui.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert get_install_dir() == exe.parent


# --- プリフライト（親ディレクトリの書き込み可否） ---


def test_is_parent_writable_true_for_writable_parent(tmp_path: Path) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    assert is_parent_writable(install) is True


def test_is_parent_writable_false_when_parent_missing(tmp_path: Path) -> None:
    install = tmp_path / "missing" / "yt-gui"
    assert is_parent_writable(install) is False


def test_can_self_update_true_when_all_conditions_met(tmp_path: Path) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    assert can_self_update(platform="win32", current="0.5.0", install_dir=install)


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_can_self_update_false_on_non_windows(tmp_path: Path, platform: str) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    assert not can_self_update(platform=platform, current="0.5.0", install_dir=install)


def test_can_self_update_false_when_version_unknown(tmp_path: Path) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    assert not can_self_update(platform="win32", current="unknown", install_dir=install)


def test_can_self_update_false_when_not_frozen() -> None:
    # 開発環境（バンドル外）では get_install_dir() が None を返す。
    assert not can_self_update(platform="win32", current="0.5.0", install_dir=None)


def test_can_self_update_false_when_parent_not_writable(tmp_path: Path) -> None:
    install = tmp_path / "missing" / "yt-gui"
    assert not can_self_update(platform="win32", current="0.5.0", install_dir=install)


# --- 兄弟ディレクトリの導出（フォルダ名を尊重する不変条件） ---


def test_resolve_staging_and_backup_derive_from_install_name(tmp_path: Path) -> None:
    # ユーザーがインストールフォルダをリネームしていても name 基準で導出する。
    install = tmp_path / "my-renamed-app"
    assert resolve_staging_dir(install) == tmp_path / "my-renamed-app.update-staging"
    assert resolve_backup_dir(install) == tmp_path / "my-renamed-app.bak"


def test_looks_like_app_dir(tmp_path: Path) -> None:
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    assert looks_like_app_dir(new_dir, "yt-gui.exe") is False
    (new_dir / "yt-gui.exe").write_bytes(b"")
    assert looks_like_app_dir(new_dir, "yt-gui.exe") is True
    assert looks_like_app_dir(tmp_path / "absent", "yt-gui.exe") is False


# --- 残骸掃除（.bak / .update-staging） ---


def test_cleanup_leftovers_removes_bak_and_staging(tmp_path: Path) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    bak = tmp_path / "yt-gui.bak"
    staging = tmp_path / "yt-gui.update-staging"
    for d in (bak, staging):
        d.mkdir()
        (d / "f.txt").write_bytes(b"x")
    cleanup_leftovers(install)
    assert not bak.exists()
    assert not staging.exists()
    assert install.exists()  # インストール本体は触らない


def test_cleanup_leftovers_is_silent_when_absent(tmp_path: Path) -> None:
    install = tmp_path / "yt-gui"
    install.mkdir()
    cleanup_leftovers(install)  # 例外を出さない


def test_cleanup_leftovers_is_silent_on_removal_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """削除失敗（ロック・権限等）は例外を漏らさずサイレントに持ち越す。"""
    install = tmp_path / "yt-gui"
    install.mkdir()
    (install / "app.txt").write_bytes(b"x")
    bak = tmp_path / "yt-gui.bak"
    bak.mkdir()

    def _locked(*args, **kwargs):
        raise OSError("locked by another process")

    monkeypatch.setattr(shutil, "rmtree", _locked)
    cleanup_leftovers(install)  # 例外を出さない（起動を妨げない）
    # 削除は次回へ持ち越し、インストール本体には触れない。
    assert bak.exists()
    assert (install / "app.txt").exists()


# --- 差し替えスクリプトの生成（純関数・全 OS で検証） ---


def _build_script(tmp_path: Path, **kwargs) -> str:
    install = kwargs.pop("install_dir", tmp_path / "yt-gui")
    new_dir = kwargs.pop("new_dir", tmp_path / "yt-gui.update-staging" / "new")
    return build_replace_script(
        install_dir=install,
        new_dir=new_dir,
        pid=kwargs.pop("pid", 4242),
        exe_relpath=kwargs.pop("exe_relpath", "yt-gui.exe"),
        **kwargs,
    )


def test_build_replace_script_embeds_parameters(tmp_path: Path) -> None:
    script = _build_script(
        tmp_path, wait_timeout_sec=33, retry_count=5, retry_initial_ms=123
    )
    assert str(tmp_path / "yt-gui") in script
    assert str(tmp_path / "yt-gui.update-staging" / "new") in script
    assert str(tmp_path / "yt-gui.bak") in script  # install 名から導出した .bak
    assert "4242" in script
    assert "yt-gui.exe" in script
    assert "33" in script
    assert "123" in script


def test_build_replace_script_escapes_single_quotes(tmp_path: Path) -> None:
    # ユーザー名等にシングルクォートが含まれても構文が壊れないこと。
    install = tmp_path / "O'Brien" / "yt-gui"
    script = _build_script(tmp_path, install_dir=install)
    assert "O''Brien" in script
    # エスケープされていない生の O'Brien が残っていないこと。
    assert "O'Brien" not in script.replace("O''Brien", "")


def test_build_replace_script_checks_process_name(tmp_path: Path) -> None:
    # PID 再利用の誤検知対策としてプロセス名も照合する。
    script = _build_script(tmp_path, exe_relpath="yt-gui.exe")
    assert "ProcessName" in script
    assert "'yt-gui'" in script


def test_build_replace_script_self_deletes(tmp_path: Path) -> None:
    script = _build_script(tmp_path)
    assert "MyInvocation" in script


def test_build_replace_script_dialog_flag(tmp_path: Path) -> None:
    # 二重失敗時の案内は MessageBox。テストでは無効化できる（ブロック防止）。
    with_dialog = _build_script(tmp_path, show_dialog_on_failure=True)
    without_dialog = _build_script(tmp_path, show_dialog_on_failure=False)
    assert "MessageBox" in with_dialog
    assert ".bak" in with_dialog  # 案内文言に手動復旧先（.bak）を含める
    assert "MessageBox" not in without_dialog


# --- スクリプトの書き出しと起動 ---


def test_launch_replace_script_writes_ps1_and_spawns(tmp_path: Path) -> None:
    spawned: list[list[str]] = []
    ok = launch_replace_script(
        "Write-Output 'hi'", script_dir=tmp_path, spawn=spawned.append
    )
    assert ok is True
    assert len(spawned) == 1
    argv = spawned[0]
    assert argv[0] == "powershell.exe"
    assert "-NoProfile" in argv
    assert "-ExecutionPolicy" in argv
    assert "Bypass" in argv
    script_path = Path(argv[-1])
    assert script_path.suffix == ".ps1"
    # PowerShell 5.1 が非 ASCII パスを正しく読めるよう BOM 付き UTF-8 で書く。
    raw = script_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "Write-Output 'hi'" in raw.decode("utf-8-sig")


@windows_only
def test_launch_replace_script_default_spawn_executes_powershell(
    tmp_path: Path,
) -> None:
    """既定の spawn が実際に PowerShell を実行できること（フラグ検証）。

    DETACHED_PROCESS と CREATE_NO_WINDOW は排他で、併用すると PowerShell が
    起動直後に死ぬ（#253 E2E で検出）。マーカーファイルの出現で実行を確認する。
    """
    import time

    marker = tmp_path / "marker.txt"
    script = f"Set-Content -LiteralPath '{marker}' -Value 'ok'"
    assert launch_replace_script(script, script_dir=tmp_path) is True
    deadline = time.time() + 30
    while time.time() < deadline and not marker.exists():
        time.sleep(0.2)
    assert marker.exists(), "既定 spawn で PowerShell が実行されていない"


def test_launch_replace_script_returns_false_on_spawn_failure(tmp_path: Path) -> None:
    def _boom(argv: list[str]) -> None:
        raise OSError("blocked")

    # 例外を漏らさず False を返す（呼び出し側はアプリを終了しない）。
    assert launch_replace_script("x", script_dir=tmp_path, spawn=_boom) is False


# --- 差し替えスクリプトの実行（Windows 限定・実 PowerShell） ---


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


def _make_layout(tmp_path: Path) -> dict[str, Path]:
    """ダミーのインストール構成（旧版・ステージング済み新版）を作る。"""
    install = tmp_path / "yt-gui"
    install.mkdir()
    (install / "old.txt").write_bytes(b"old")
    (install / "yt-gui.exe").write_bytes(b"not a real exe")
    staging = tmp_path / "yt-gui.update-staging"
    new_dir = staging / "yt-gui-9.9.9-new"
    new_dir.mkdir(parents=True)
    (new_dir / "new.txt").write_bytes(b"new")
    (new_dir / "yt-gui.exe").write_bytes(b"not a real exe")
    return {"install": install, "staging": staging, "new_dir": new_dir}


def _run_script(tmp_path: Path, script: str) -> subprocess.CompletedProcess:
    script_path = tmp_path / "replace.ps1"
    script_path.write_text(script, encoding="utf-8-sig")
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


_FAST = {"wait_timeout_sec": 10, "retry_count": 2, "retry_initial_ms": 10}


@windows_only
def test_replace_script_swaps_install_and_cleans_up(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    script = build_replace_script(
        install_dir=layout["install"],
        new_dir=layout["new_dir"],
        pid=_dead_pid(),
        exe_relpath="yt-gui.exe",
        show_dialog_on_failure=False,
        **_FAST,
    )
    result = _run_script(tmp_path, script)
    assert result.returncode == 0, result.stderr
    # 新版が配置され、旧版は .bak に退避、ステージングは掃除済み。
    assert (layout["install"] / "new.txt").exists()
    assert not (layout["install"] / "old.txt").exists()
    assert (tmp_path / "yt-gui.bak" / "old.txt").exists()
    assert not layout["staging"].exists()
    # スクリプトは自己削除する。
    assert not (tmp_path / "replace.ps1").exists()


@windows_only
def test_replace_script_replaces_stale_backup(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    stale = tmp_path / "yt-gui.bak"
    stale.mkdir()
    (stale / "stale.txt").write_bytes(b"stale")
    script = build_replace_script(
        install_dir=layout["install"],
        new_dir=layout["new_dir"],
        pid=_dead_pid(),
        exe_relpath="yt-gui.exe",
        show_dialog_on_failure=False,
        **_FAST,
    )
    result = _run_script(tmp_path, script)
    assert result.returncode == 0, result.stderr
    # .bak は 1 世代のみ: 古い残骸は消え、今回の旧版に置き換わる。
    assert (tmp_path / "yt-gui.bak" / "old.txt").exists()
    assert not (tmp_path / "yt-gui.bak" / "stale.txt").exists()


@windows_only
def test_replace_script_rolls_back_when_new_dir_missing(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    shutil.rmtree(layout["new_dir"])  # 新→旧パス rename を失敗させる
    script = build_replace_script(
        install_dir=layout["install"],
        new_dir=layout["new_dir"],
        pid=_dead_pid(),
        exe_relpath="yt-gui.exe",
        show_dialog_on_failure=False,
        **_FAST,
    )
    result = _run_script(tmp_path, script)
    assert result.returncode == 2, result.stderr
    # ロールバック: 旧版がインストールパスへ復旧し、.bak は残らない。
    assert (layout["install"] / "old.txt").exists()
    assert not (tmp_path / "yt-gui.bak").exists()
    assert not (tmp_path / "replace.ps1").exists()


@windows_only
def test_replace_script_times_out_without_touching_install(tmp_path: Path) -> None:
    layout = _make_layout(tmp_path)
    # PID 待機を確実に発火させるため、プロセス名が一致する生存プロセスを使う。
    alive = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
    )
    try:
        exe_name = Path(sys.executable).name  # プロセス名を一致させる（python.exe）
        script = build_replace_script(
            install_dir=layout["install"],
            new_dir=layout["new_dir"],
            pid=alive.pid,
            exe_relpath=exe_name,
            wait_timeout_sec=1,
            retry_count=2,
            retry_initial_ms=10,
            show_dialog_on_failure=False,
        )
        result = _run_script(tmp_path, script)
    finally:
        alive.kill()
        alive.wait()
    assert result.returncode == 1, result.stderr
    # タイムアウト時はインストール先・ステージングに一切触れない。
    assert (layout["install"] / "old.txt").exists()
    assert not (tmp_path / "yt-gui.bak").exists()
    assert layout["new_dir"].exists()
