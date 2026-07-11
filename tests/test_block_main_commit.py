"""Claude Code PreToolUse hook（.claude/hooks/block_main_commit.py）のテスト。

hook は stdin の JSON（tool_input.command / cwd）を受け取り、カレントブランチが
main のときの git commit / git push を permissionDecision: deny で返す。
それ以外（安全なコマンド・main 以外・リポジトリ外・不正入力）はフェイルオープンで
何も出力せず exit 0 する（#232）。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / ".claude" / "hooks" / "block_main_commit.py"


def _run_hook(
    stdin_text: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _hook_decision(command: str, cwd: Path) -> tuple[int, str]:
    """hook を実行し (returncode, stdout) を返す。"""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }
    result = _run_hook(json.dumps(payload))
    return result.returncode, result.stdout


def _is_denied(stdout: str) -> bool:
    if not stdout.strip():
        return False
    output = json.loads(stdout)
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    return bool(decision == "deny")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        # 実行者のグローバル/システム設定（init.defaultBranch 等）を混入させない
        env={
            **__import__("os").environ,
            "GIT_CONFIG_GLOBAL": str(repo / ".no-global-config"),
            "GIT_CONFIG_SYSTEM": str(repo / ".no-system-config"),
        },
    )


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    """main ブランチ上にいる一時 git リポジトリ（コミット 1 つあり）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "a.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "init")
    return repo


@pytest.fixture
def feature_repo(main_repo: Path) -> Path:
    """feature ブランチ上にいる一時 git リポジトリ。"""
    _git(main_repo, "checkout", "-b", "feature/1-test")
    return main_repo


def test_denies_commit_on_main(main_repo):
    code, out = _hook_decision("git commit -m test", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_denies_push_on_main(main_repo):
    code, out = _hook_decision("git push origin main", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_denies_compound_command_on_main(main_repo):
    code, out = _hook_decision("uv run pytest && git push", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_denies_semicolon_compound_on_main(main_repo):
    code, out = _hook_decision("git add -A; git commit -m x", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_deny_reason_is_returned(main_repo):
    _code, out = _hook_decision("git commit -m test", main_repo)
    output = json.loads(out)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "main" in reason


def test_allows_safe_git_commands_on_main(main_repo):
    safe = ("git status", "git log --oneline", "git pull --ff-only origin main")
    for command in safe:
        code, out = _hook_decision(command, main_repo)
        assert code == 0
        assert not _is_denied(out), command


def test_allows_grep_mentioning_commit_on_main(main_repo):
    # サブコマンド位置一致のため、引数中の "commit" は誤検知しない
    code, out = _hook_decision('git log --grep="commit"', main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_allows_commit_on_feature_branch(feature_repo):
    code, out = _hook_decision("git commit -m test", feature_repo)
    assert code == 0
    assert not _is_denied(out)


def test_allows_push_on_feature_branch(feature_repo):
    code, out = _hook_decision("git push -u origin feature/1-test", feature_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_outside_git_repo(tmp_path):
    code, out = _hook_decision("git commit -m test", tmp_path)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_on_invalid_stdin():
    result = _run_hook("this is not json")
    assert result.returncode == 0
    assert not _is_denied(result.stdout)


def test_fails_open_on_empty_stdin():
    result = _run_hook("")
    assert result.returncode == 0
    assert not _is_denied(result.stdout)


def test_denies_commit_on_unborn_main(tmp_path):
    # git init -b main 直後（コミットなし）でも symbolic-ref で解決して deny する
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    code, out = _hook_decision("git commit -m init", repo)
    assert code == 0
    assert _is_denied(out)
