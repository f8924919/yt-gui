#!/usr/bin/env python3
"""Claude Code SessionStart hook: 未完了タスクをセッション冒頭に注入する。

CLAUDE.md の「セッション開始時に docs/task/index.md を確認する」運用の機構化（#285）。
プロンプトの指示だけだと (1) 確認自体が飛ばされうる (2) 毎回ファイル全体を読む
コストがかかる、の 2 点が問題だったため、**必要な表だけ**を additionalContext
として注入する（docs/docs-guide.md §3.2 の運用注記も参照）。

抽出するのは docs/task/index.md の 2 つの表:

- `## タスク` — タスクメモ (`docs/task/{slug}.md`) を持つ進行中・未着手のタスク
- `## 起票済み・未着手の Issue` — メモをまだ作っていない未着手の Issue

判定に迷うケース（ファイル欠落・パース失敗）は**何も注入せず通す**
（フェイルオープン）。注入が無くても CLAUDE.md の指示で従来どおり index.md を
読めばよく、hook の不調でセッションを止めない。**ただし見出しが 1 つも見つからない
ときは、その旨だけを 1 行注入する**。黙って諦めると、見出しの改名で自動注入が
静かに止まり、「注入が無い = hook が動いていない」という CLAUDE.md の判断を誤らせる。
**片方の見出しだけが見つからないときは、見つかった表を注入したうえで、見つからなかった
見出しと実際の H2 見出しを 1 行で知らせる**。注入自体は出ているので、欠けた表は
黙っていると気づけない（#326。docs/git-workflow.md §5.6 の共通方針）。

標準ライブラリのみに依存し、Windows / macOS / Linux で動作する。
"""

import contextlib
import json
import sys
from pathlib import Path

# .claude/hooks/<this>.py → リポジトリルート
REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_INDEX = REPO_ROOT / "docs" / "task" / "index.md"

SECTIONS = {
    "## タスク": "タスクメモを持つタスク",
    "## 起票済み・未着手の Issue": "起票済み・未着手の Issue",
}
EMPTY_MARKER = "ありません"
HEADER = "## 未完了タスク（docs/task/index.md からの自動注入）"


def _table_rows(lines: list[str]) -> list[list[str]]:
    """表の本文行（見出し行・区切り行を除く）をセルのリストとして返す。"""
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue  # 区切り行
        rows.append(cells)
    return rows[1:] if rows else []  # 先頭は見出し行


def _sections(text: str) -> dict[str, list[str]]:
    """H2 見出しごとに行を束ねる。HTML コメント（記入例）内は無視する。"""
    grouped: dict[str, list[str]] = {}
    current: str | None = None
    in_comment = False
    for line in text.splitlines():
        if in_comment:
            in_comment = "-->" not in line
            continue
        if line.lstrip().startswith("<!--"):
            in_comment = "-->" not in line
            continue
        if line.startswith("## "):
            current = line.strip()
            grouped[current] = []
        elif current is not None:
            grouped[current].append(line)
    return grouped


def _format(rows: list[list[str]]) -> list[str]:
    """表の行を箇条書きにする。空表のプレースホルダ行は「なし」に畳む。"""
    if not rows:
        return ["- （表が空）"]
    if len(rows) == 1 and EMPTY_MARKER in rows[0][0]:
        return ["- なし"]
    return [
        "- " + " / ".join(cell for cell in row[:3] if cell and cell != "—")
        for row in rows
    ]


def build_context(index_text: str) -> str:
    """index.md の本文から注入文を組み立てる（テストが直接呼ぶ入口）。"""
    grouped = _sections(index_text)
    found = [h for h in grouped if h.startswith("## ")]

    blocks: list[str] = []
    for heading, label in SECTIONS.items():
        if heading not in grouped:
            continue
        blocks.append(f"**{label}**")
        blocks.extend(_format(_table_rows(grouped[heading])))
        blocks.append("")

    if not blocks:
        # 見出しが 1 つも一致しない（改名された等）。黙って諦めず、その旨を注入する。
        return "\n".join(
            [
                HEADER,
                "",
                "**期待する見出しが見つからないため表を注入できなかった。**"
                f" 期待: {' / '.join(SECTIONS)}。"
                f"実際: {' / '.join(found) or '（H2 見出しなし）'}。"
                " docs/task/index.md を直接読み、見出しを直すか"
                " .claude/hooks/session_task_status.py の SECTIONS を合わせること。",
            ]
        )

    missing = [h for h in SECTIONS if h not in grouped]
    if missing:
        # 片方だけ改名された等。残った表は出しつつ、欠けた表が黙って
        # 消えないようにする（注入自体は出ているので、「注入が無い
        # = hook が動いていない」の判断が働かない）。
        blocks.append(
            f"**見つからなかった見出し**: {' / '.join(missing)}"
            f"（実際: {' / '.join(found)}）。"
            " この表は注入できていないので docs/task/index.md を直接読むこと。"
        )
        blocks.append("")

    return "\n".join(
        [
            HEADER,
            "",
            *blocks,
            "CLAUDE.md のタスク管理ルールに従い、未着手 / 進行中のものがあれば"
            "**対応するかをユーザーに尋ねること**。詳細・着手時の申し送りは "
            "docs/task/index.md と docs/task/archive/index.md を参照。",
        ]
    )


def main() -> None:
    # 入力は使わないが、読み切ってから処理する
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        json.load(sys.stdin)

    try:
        index_text = TASK_INDEX.read_text(encoding="utf-8")
    except OSError:
        return  # index.md が無い → 何も注入しない

    context = build_context(index_text)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
