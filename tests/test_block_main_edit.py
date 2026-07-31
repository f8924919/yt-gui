"""Claude Code PreToolUse hook（.claude/hooks/block_main_edit.py）のテスト。

hook は stdin の JSON（`tool_input.file_path`）を受け取り、リポジトリのカレント
ブランチが main のときのリポジトリ内ファイル編集を permissionDecision: deny で
返す。それ以外（main 以外・リポジトリ外・不正入力）はフェイルオープンで何も
出力せず exit 0 する（#285）。

ブランチ判定・所属判定の対象はリポジトリルート（hook ファイルからの相対）で
固定のため、判定ロジックは `repo_root` を引数に取るヘルパを直接呼んで検証し、
`main()` 全体は `REPO_ROOT` を差し替えて確認する。フェイルオープン系は
ブランチに依存しないため subprocess 実行で確認する。
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / ".claude" / "hooks" / "block_main_edit.py"

_spec = importlib.util.spec_from_file_location("block_main_edit", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
block_main_edit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(block_main_edit)


def _git(repo: Path, *args: str) -> None:
    import os

    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        # 実行者のグローバル/システム設定（init.defaultBranch 等）を混入させない
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": str(repo / ".no-global-config"),
            "GIT_CONFIG_SYSTEM": str(repo / ".no-system-config"),
        },
    )


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    return repo


@pytest.fixture
def feature_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "feature_repo"
    repo.mkdir()
    _git(repo, "init", "-b", "feature/1-test")
    return repo


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    repo_root: Path,
    payload: object,
) -> bool:
    """`REPO_ROOT` を差し替えて main() を実行し、deny されたかを返す。"""
    monkeypatch.setattr(block_main_edit, "REPO_ROOT", repo_root)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    block_main_edit.main()
    out = capsys.readouterr().out
    if not out.strip():
        return False
    decision = json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision")
    return bool(decision == "deny")


def _edit_payload(file_path: Path) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(file_path)},
    }


# ── ブランチ判定 ─────────────────────────────────────────────────────────────


def test_on_main_detects_main(main_repo):
    assert block_main_edit._on_main(main_repo) is True


def test_on_main_detects_feature_branch(feature_repo):
    assert block_main_edit._on_main(feature_repo) is False


def test_on_main_fails_open_outside_git_repo(tmp_path):
    assert block_main_edit._on_main(tmp_path) is False


# ── リポジトリ所属判定 ───────────────────────────────────────────────────────


def test_inside_repo_accepts_nested_path(main_repo):
    assert (
        block_main_edit._inside_repo(str(main_repo / "a" / "b.py"), main_repo) is True
    )


def test_inside_repo_rejects_outside_path(main_repo, tmp_path):
    outside = tmp_path / "elsewhere" / "memory.md"
    assert block_main_edit._inside_repo(str(outside), main_repo) is False


# ── main()（ブロック / 通過） ────────────────────────────────────────────────


def test_denies_edit_on_main(monkeypatch, capsys, main_repo):
    assert _run_main(monkeypatch, capsys, main_repo, _edit_payload(main_repo / "a.py"))


def test_deny_reason_mentions_main(monkeypatch, capsys, main_repo):
    monkeypatch.setattr(block_main_edit, "REPO_ROOT", main_repo)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps(_edit_payload(main_repo / "a.py")))
    )
    block_main_edit.main()
    output = json.loads(capsys.readouterr().out)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "main" in reason


def test_denies_notebook_edit_on_main(monkeypatch, capsys, main_repo):
    """NotebookEdit の入力キーは `notebook_path`（`file_path` ではない）。"""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(main_repo / "a.ipynb")},
    }
    assert _run_main(monkeypatch, capsys, main_repo, payload)


def test_allows_notebook_edit_on_feature_branch(monkeypatch, capsys, feature_repo):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(feature_repo / "a.ipynb")},
    }
    assert not _run_main(monkeypatch, capsys, feature_repo, payload)


def test_allows_edit_on_feature_branch(monkeypatch, capsys, feature_repo):
    payload = _edit_payload(feature_repo / "a.py")
    assert not _run_main(monkeypatch, capsys, feature_repo, payload)


def test_allows_edit_outside_repo_even_on_main(
    monkeypatch, capsys, main_repo, tmp_path
):
    """リポジトリ外（Claude Code のメモリ等）への書き込みは巻き込まない。"""
    payload = _edit_payload(tmp_path / "outside" / "memory.md")
    assert not _run_main(monkeypatch, capsys, main_repo, payload)


# ── フェイルオープン ─────────────────────────────────────────────────────────


def test_fails_open_on_missing_file_path(monkeypatch, capsys, main_repo):
    payload = {"hook_event_name": "PreToolUse", "tool_input": {}}
    assert not _run_main(monkeypatch, capsys, main_repo, payload)


def test_fails_open_on_non_string_file_path(monkeypatch, capsys, main_repo):
    payload = {"hook_event_name": "PreToolUse", "tool_input": {"file_path": 42}}
    assert not _run_main(monkeypatch, capsys, main_repo, payload)


def test_fails_open_on_invalid_stdin(monkeypatch, capsys, main_repo):
    assert not _run_main(monkeypatch, capsys, main_repo, "this is not json")


def test_fails_open_on_non_object_json(monkeypatch, capsys, main_repo):
    """dict 以外の JSON（配列・文字列）でも例外を出さず通す。"""
    for payload in ([1, 2], 42, json.dumps("just a string")):
        assert not _run_main(monkeypatch, capsys, main_repo, payload)


def test_fails_open_on_non_object_tool_input(monkeypatch, capsys, main_repo):
    payload = {"hook_event_name": "PreToolUse", "tool_input": "oops"}
    assert not _run_main(monkeypatch, capsys, main_repo, payload)


def _run_hook_subprocess(stdin_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_script_fails_open_on_empty_stdin():
    """スクリプトとして起動しても不正入力で落ちない（exit 0・無出力）。"""
    result = _run_hook_subprocess("")
    assert result.returncode == 0
    assert not result.stdout.strip()


def test_script_fails_open_on_path_outside_repo(tmp_path):
    payload = _edit_payload(tmp_path / "outside.md")
    result = _run_hook_subprocess(json.dumps(payload))
    assert result.returncode == 0
    assert not result.stdout.strip()
