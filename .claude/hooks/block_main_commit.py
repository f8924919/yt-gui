#!/usr/bin/env python3
"""Claude Code PreToolUse hook: main ブランチ上の git commit / git push をブロックする。

「main で直接コミットしない」（docs/git-workflow.md §1）のクライアント側強制（#232）。
サーバー側の最後の砦は branch protection の enforce_admins が担うため、本 hook は
早期警告に徹し、判定に迷うケースはすべてフェイルオープン（通す）に倒す:

- stdin の JSON パース失敗・git コマンド失敗（リポジトリ外・detached HEAD 等）→ 通す
- 検出は「`&&` / `;` / `|` / 改行で分割した各セグメントのサブコマンド位置」での
  git commit / git push 一致のみ。`git -c k=v commit` のようなオプション挟み込みや
  文字列内の擦り抜けは追わない（誤ブロック回避を優先。docs/git-workflow.md §1）。

ブロック時は permissionDecision: deny と理由を JSON で stdout に返す。
標準ライブラリのみに依存し、Windows / macOS / Linux で動作する。
"""

import json
import re
import subprocess
import sys

BLOCKED_SUBCOMMANDS = {"commit", "push"}
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def _current_branch(cwd: str | None) -> str | None:
    """カレントブランチ名を返す。解決できない場合は None（フェイルオープン）。"""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd or None,
            timeout=10,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _blocked_subcommand(command: str) -> str | None:
    """コマンド文字列に main 上で禁止する git サブコマンドがあれば返す。"""
    for segment in SEGMENT_SPLIT.split(command):
        tokens = segment.strip().split()
        if not tokens or tokens[0] != "git":
            continue
        # git 直後のオプション（引数を取らない形式のみ）を読み飛ばし、
        # サブコマンド位置のトークンを判定する
        for token in tokens[1:]:
            if token.startswith("-"):
                continue
            if token in BLOCKED_SUBCOMMANDS:
                return token
            break
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError, ValueError:
        return

    command = hook_input.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not command:
        return

    subcommand = _blocked_subcommand(command)
    if subcommand is None:
        return

    branch = _current_branch(hook_input.get("cwd"))
    if branch != "main":
        return

    reason = (
        f"main ブランチ上での `git {subcommand}` はブロックされました"
        "（docs/git-workflow.md §1: main で直接コミットしない）。"
        "feature/bugfix 等のブランチを main から切って作業してください。"
    )
    # Windows のコンソールエンコーディング（cp932 等）で化けないよう
    # ensure_ascii（既定）で ASCII セーフに出力する
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
