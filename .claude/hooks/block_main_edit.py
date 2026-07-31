#!/usr/bin/env python3
"""Claude Code PreToolUse hook: main 上のリポジトリ内ファイル編集をブロックする。

「main で直接作業しない」（docs/git-workflow.md §1）を**編集の時点**で効かせる（#285）。
block_main_commit.py は commit / push を止めるが、そこに至るまでの編集は素通りする
ため、ブランチを切り忘れたことに気付くのが commit 直前になり巻き戻しが要る。

判定に迷うケースはすべてフェイルオープン（通す）に倒す:

- stdin の JSON パース失敗・`file_path` 欠落 / 非文字列・パス解決失敗 → 通す
- git コマンド失敗（リポジトリ外・detached HEAD 等）→ 通す
- **リポジトリ外のファイルは対象外**（Claude Code のメモリなど、リポジトリと
  無関係の書き込みを巻き込まないため）

ブロック時は permissionDecision: deny と理由を JSON で stdout に返す。
標準ライブラリのみに依存し、Windows / macOS / Linux で動作する。
"""

import json
import subprocess
import sys
from pathlib import Path

# .claude/hooks/<this>.py → リポジトリルート
REPO_ROOT = Path(__file__).resolve().parents[2]


def _on_main(repo_root: Path) -> bool:
    """リポジトリのカレントブランチが main かを返す。解決不能なら False（通す）。"""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=10,
        )
    except OSError, subprocess.SubprocessError:
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "main"


def _inside_repo(raw_path: str, repo_root: Path) -> bool:
    """対象ファイルがリポジトリ内かを返す。解決できなければ False（通す）。"""
    try:
        Path(raw_path).resolve().relative_to(repo_root.resolve())
    except OSError, ValueError:
        return False
    return True


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError, ValueError:
        return

    raw_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return

    if not _inside_repo(raw_path, REPO_ROOT) or not _on_main(REPO_ROOT):
        return

    reason = (
        "main ブランチ上でのリポジトリ内ファイルの編集はブロックされました"
        "（docs/git-workflow.md §1: main で直接作業しない）。"
        "先に main から作業ブランチ（feature/ bugfix/ hotfix/ refactor/ docs/ chore/）"
        "を切ってから編集してください。"
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
