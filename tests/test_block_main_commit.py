"""Claude Code PreToolUse hook（.claude/hooks/block_main_commit.py）のテスト。

hook は stdin の JSON（tool_input.command / cwd）を受け取り、カレントブランチが
main のときの git commit / git push を permissionDecision: deny で返す。
それ以外（安全なコマンド・main 以外・リポジトリ外・不正入力）はフェイルオープンで
何も出力せず exit 0 する（#232）。

ブランチ判定は cwd を起点にした実効ディレクトリに対して行う（#240）:
複合コマンド内の `cd <path>` を追跡し、git のグローバルオプション `-C <path>`
（複数指定の累積を含む）も解決する。パス解決に失敗するケース・`--git-dir` /
`--work-tree`・クォート付きパスは一律フェイルオープン。
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


# ── クロスリポジトリ（cd 追跡・-C 解決。#240） ───────────────────────────────


def _hook_decision_no_cwd(command: str) -> tuple[int, str]:
    """cwd を含まない hook 入力で実行し (returncode, stdout) を返す。"""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    result = _run_hook(json.dumps(payload))
    return result.returncode, result.stdout


@pytest.fixture
def other_main_repo(tmp_path: Path) -> Path:
    """main ブランチ上の別リポジトリ（unborn で可）。"""
    repo = tmp_path / "other_main"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    return repo


@pytest.fixture
def other_feature_repo(tmp_path: Path) -> Path:
    """feature ブランチ上の別リポジトリ（unborn で可）。"""
    repo = tmp_path / "other_feature"
    repo.mkdir()
    _git(repo, "init", "-b", "feature/2-other")
    return repo


def test_allows_cd_to_feature_repo_then_commit(main_repo, other_feature_repo):
    """実際に誤ブロックされた形（cd <別リポジトリ>; git commit; git push）の回帰。"""
    command = (
        f"cd {other_feature_repo}; git commit -m x; git push -u origin feature/2-other"
    )
    code, out = _hook_decision(command, main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_denies_cd_to_main_repo_then_commit(feature_repo, other_main_repo):
    """クロスリポジトリでも移動先が main なら保護は機能する。"""
    command = f"cd {other_main_repo}; git commit -m x"
    code, out = _hook_decision(command, feature_repo)
    assert code == 0
    assert _is_denied(out)


def test_cd_relative_path_is_resolved(tmp_path, other_main_repo, other_feature_repo):
    """cd の相対パスは実効ディレクトリ起点で解決される。"""
    code, out = _hook_decision(
        f"cd {other_feature_repo.name}; git commit -m x", tmp_path
    )
    assert code == 0
    assert not _is_denied(out)
    code, out = _hook_decision(f"cd {other_main_repo.name}; git commit -m x", tmp_path)
    assert code == 0
    assert _is_denied(out)


def test_cd_only_applies_to_later_segments(main_repo, other_feature_repo):
    """cd より前のセグメントは元の cwd で判定される。"""
    command = f"git commit -m x; cd {other_feature_repo}"
    code, out = _hook_decision(command, main_repo)
    assert code == 0
    assert _is_denied(out)


def test_allows_dash_c_to_feature_repo(main_repo, other_feature_repo):
    code, out = _hook_decision(f"git -C {other_feature_repo} commit -m x", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_denies_dash_c_to_main_repo(feature_repo, other_main_repo):
    code, out = _hook_decision(f"git -C {other_main_repo} push", feature_repo)
    assert code == 0
    assert _is_denied(out)


def test_dash_c_accumulates(tmp_path, main_repo):
    """`git -C a -C b` は a/b を指す（git 仕様の累積解決）。"""
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    _git(inner, "init", "-b", "feature/3-nested")
    code, out = _hook_decision(f"git -C {outer} -C inner commit -m x", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_cd_and_dash_c_combination(tmp_path, feature_repo, other_main_repo):
    """cd で移った実効ディレクトリを起点に -C の相対パスを解決する。"""
    command = f"cd {tmp_path}; git -C {other_main_repo.name} commit -m x"
    code, out = _hook_decision(command, feature_repo)
    assert code == 0
    assert _is_denied(out)


def test_denies_dash_c_after_subcommand(main_repo):
    """`git commit -C HEAD~1` の -C はサブコマンド後置（メッセージ再利用）であり
    グローバルオプションではない。cwd（main）で判定され deny される。"""
    code, out = _hook_decision("git commit -C HEAD~1", main_repo)
    assert code == 0
    assert _is_denied(out)


# ── クロスリポジトリのフェイルオープン ───────────────────────────────────────


def test_fails_open_dash_c_without_argument(main_repo):
    code, out = _hook_decision("git -C", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_dash_c_nonexistent_path(main_repo, tmp_path):
    command = f"git -C {tmp_path / 'no_such_dir'} commit -m x"
    code, out = _hook_decision(command, main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_dash_c_non_repo_path(main_repo, tmp_path):
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    code, out = _hook_decision(f"git -C {plain_dir} commit -m x", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_cd_with_quoted_spaced_path(main_repo, tmp_path):
    """クォート付き（スペース含む）パスの cd は追跡不能 → 以降の git は通す。"""
    spaced = tmp_path / "dir with space"
    code, out = _hook_decision(f'cd "{spaced}"; git commit -m x', main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_dash_c_with_quoted_spaced_path(main_repo, tmp_path):
    """クォート付き（スペース含む）パスの -C も追跡不能 → フェイルオープン。"""
    spaced = tmp_path / "dir with space"
    code, out = _hook_decision(f'git -C "{spaced}" commit -m x', main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_cd_without_argument(main_repo):
    """引数なし cd（ホーム移動）は移動先を解決しない → 以降はフェイルオープン。"""
    code, out = _hook_decision("cd; git commit -m x", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_fails_open_git_dir_option(main_repo):
    for command in (
        f"git --git-dir {main_repo / '.git'} commit -m x",
        f"git --git-dir={main_repo / '.git'} commit -m x",
        f"git --work-tree {main_repo} commit -m x",
        f"git --work-tree={main_repo} commit -m x",
    ):
        code, out = _hook_decision(command, main_repo)
        assert code == 0
        assert not _is_denied(out), command


def test_fails_open_missing_cwd_with_relative_cd():
    """hook 入力に cwd が無い場合、相対 cd は解決できない → フェイルオープン。"""
    code, out = _hook_decision_no_cwd("cd sub; git commit -m x")
    assert code == 0
    assert not _is_denied(out)


def test_denies_missing_cwd_with_absolute_cd(other_main_repo):
    """cwd 不明でも絶対パスの cd は解決できるため main 保護は機能する。"""
    code, out = _hook_decision_no_cwd(f"cd {other_main_repo}; git commit -m x")
    assert code == 0
    assert _is_denied(out)


# ── リモートブランチ削除の除外（#285） ───────────────────────────────────────
#
# マージ済みブランチの削除は main へ戻ってから行う正規の手順（git-workflow §5
# step 9・/finish-task）。main の履歴を変更しないため main 上でも通す。


def test_allows_branch_deletion_on_main(main_repo):
    code, out = _hook_decision("git push origin --delete feature/1-test", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_allows_short_branch_deletion_on_main(main_repo):
    code, out = _hook_decision("git push origin -d feature/1-test", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_allows_colon_refspec_deletion_on_main(main_repo):
    """`git push origin :branch` も削除 refspec として通す。"""
    code, out = _hook_decision("git push origin :feature/1-test", main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_allows_deletion_in_compound_command_on_main(main_repo):
    """/finish-task が出す形（local 削除 → remote 削除）を通す。"""
    command = "git branch -d feature/1-test && git push origin --delete feature/1-test"
    code, out = _hook_decision(command, main_repo)
    assert code == 0
    assert not _is_denied(out)


def test_still_denies_normal_push_on_main(main_repo):
    """削除除外を入れても通常の push は従来どおりブロックする。"""
    for command in ("git push", "git push origin main", "git push -u origin main"):
        code, out = _hook_decision(command, main_repo)
        assert code == 0
        assert _is_denied(out), command


def test_still_denies_push_with_delete_like_message(main_repo):
    """引数に `-d` を含まない通常 push は削除と誤認しない。"""
    code, out = _hook_decision("git push origin main --force-with-lease", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_denies_mixed_refspec_push_on_main(main_repo):
    """削除 refspec と通常 push の混在は削除扱いにせずブロックする。"""
    code, out = _hook_decision("git push origin main :old", main_repo)
    assert code == 0
    assert _is_denied(out)


def test_fails_open_on_non_object_json(main_repo):
    """dict 以外の JSON でも例外を出さず通す（exit 0・無出力）。"""
    for payload in ("[1, 2]", "42", '"a string"'):
        result = _run_hook(payload)
        assert result.returncode == 0, payload
        assert not _is_denied(result.stdout), payload


def test_deletion_exemption_does_not_apply_to_commit(main_repo):
    """`--delete` は push 固有の判定で、commit には適用しない。"""
    code, out = _hook_decision("git commit -m x --delete", main_repo)
    assert code == 0
    assert _is_denied(out)
