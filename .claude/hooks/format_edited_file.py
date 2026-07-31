#!/usr/bin/env python3
"""Claude Code PostToolUse hook: 編集したソースファイルをその場で整形する。

verify ゲート（docs/git-workflow.md §5 step 7）の `ruff format` で最後にまとめて
整形すると、整形だけの差分が実装コミットに混ざり、検証の手戻りも増える。編集直後に
同じ整形を掛けておけばその往復が消える（#285）。

対象は `yt_gui/` `tests/` 配下の `.py` に限定する。リポジトリ全体を対象にすると
`scripts/` の一時生成物や `docs/` 配下のコード片まで巻き込むため、ruff の設定
（pyproject.toml）に従う主要ソースだけを扱い、残りは verify ゲートに委ねる。

ruff・対象ファイルのいずれかが見つからない場合や整形が失敗した場合も**黙って通す**
（フェイルオープン）。整形は verify ゲートでも走るため、ここでの失敗は「早めに
整形できなかった」以上の意味を持たない。

標準ライブラリのみに依存し、Windows / macOS / Linux で動作する。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

# .claude/hooks/<this>.py → リポジトリルート
REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_DIRS = ("yt_gui", "tests")
TARGET_SUFFIXES = {".py"}
# 起動子は他の hook と同じく uv に揃える（docs/git-workflow.md §1・§5.6）
FORMAT_CMD = ["uv", "run", "--no-sync", "--project", str(REPO_ROOT), "ruff", "format"]


def _target(raw_path: str, repo_root: Path) -> Path | None:
    """整形対象なら絶対パスを返す。対象外・解決不能なら None。"""
    try:
        path = Path(raw_path).resolve()
    except OSError, ValueError:
        return None
    if path.suffix not in TARGET_SUFFIXES or not path.is_file():
        return None
    for name in TARGET_DIRS:
        try:
            path.relative_to(repo_root.resolve() / name)
        except ValueError:
            continue
        return path
    return None  # 対象ディレクトリの外は触らない


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError, ValueError:
        return
    if not isinstance(hook_input, dict):
        return

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return
    raw_path = tool_input.get("file_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return

    path = _target(raw_path, REPO_ROOT)
    if path is None:
        return

    executable = shutil.which(FORMAT_CMD[0])
    if executable is None:
        return

    try:
        subprocess.run(
            [executable, *FORMAT_CMD[1:], str(path)],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=60,
        )
    except OSError, subprocess.SubprocessError:
        return  # 整形できなくても通す（verify ゲートで拾う）


if __name__ == "__main__":
    main()
