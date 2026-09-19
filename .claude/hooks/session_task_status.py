#!/usr/bin/env python3
"""Claude Code SessionStart hook: 未完了タスクをセッション冒頭に注入する。

CLAUDE.md の「セッション開始時に docs/task/index.md を確認する」運用の機構化（#285）。
プロンプトの指示だけだと (1) 確認自体が飛ばされうる (2) 毎回ファイル全体を読む
コストがかかる、の 2 点が問題だったため、**必要な表だけ**を additionalContext
として注入する（docs/docs-guide.md §3.2 の運用注記も参照）。

抽出するのは docs/task/index.md の 2 つの表:

- `## タスク` — タスクメモ (`docs/task/{slug}.md`) を持つ進行中・未着手のタスク
- `## 起票済み・未着手の Issue` — メモをまだ作っていない未着手の Issue

加えて `## タスク` 表で **`進行中`** の行はタスクメモを開き（パスは「タスク」列の
リンク先を **index の親ディレクトリ基準**で解決する）、次の 3 つを注入する（#326）。
長いセッションは文脈が要約されて計画の精度が落ちるので、`/clear` した新セッションから
**メモを探さずに**再開できるようにするため（docs/git-workflow.md §5 の分割点 A / B）:

- 冒頭の引用ブロック（本文先頭から最初の `## ` までの連続する `>` 行。
  Issue・ブランチ・基点）
- 見出しに NEXT_KEYWORDS（「次にやること」「申し送り」）を**含む** H2 節の全文
  （文書順に全部）
- 見出しが PROGRESS_PREFIX（「進捗」）で**始まる** H2 節の未チェック項目
  （`- [ ]` / `* [ ]`。入れ子も）

見出しの語はここの定数が正本（docs/docs-guide.md §3.2 の見出し規約はここへリンクする）。
注入量には上限を置く（PER_MEMO_LIMIT / TOTAL_LIMIT。注入後の行数で数える）。index.md を
「短く保つ」のと同じ理由 — この注入はセッション開始時に毎回読み込まれ、そのまま文脈
コストになる。超えたら「…以下は <path> を読む」の 1 行で切る。

判定に迷うケース（ファイル欠落・パース失敗）は**何も注入せず通す**
（フェイルオープン）。注入が無くても CLAUDE.md の指示で従来どおり index.md を
読めばよく、hook の不調でセッションを止めない。**ただし見出しが 1 つも見つからない
ときは、その旨だけを 1 行注入する**。黙って諦めると、見出しの改名で自動注入が
静かに止まり、「注入が無い = hook が動いていない」という CLAUDE.md の判断を誤らせる。
**片方の見出しだけが見つからないときは、見つかった表を注入したうえで、見つからなかった
見出しと実際の H2 見出しを 1 行で知らせる**（`## タスク` が無いときは、進行中メモも
注入できていないことも同じ行に書く）。注入自体は出ているので、欠けた表は黙っていると
気づけない（#326。docs/git-workflow.md §5.6 の共通方針）。タスクメモ側も同じで、
**メモが読めない・節が無い・チェック項目が無い・未チェック 0 件はそれぞれ別の 1 行**を
出す（「無い」と「全部済んだ」を同じ文にしない）。`進行中` なのにメモへのリンクが
無い行も黙って落とさず 1 行出す（雛形には無い、yt-gui で足した分岐）。

組み立ては build_context(index_text, base_dir) に切り出してあり、テストはこれを直接呼ぶ
（tests/test_session_task_status.py）。

標準ライブラリのみに依存し、Windows / macOS / Linux で動作する。
"""

import contextlib
import json
import re
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

# --- 進行中メモの注入
TASK_HEADING = "## タスク"
IN_PROGRESS = "進行中"
NEXT_KEYWORDS = ("次にやること", "申し送り")
PROGRESS_PREFIX = "進捗"
UNCHECKED = ("- [ ]", "* [ ]")
CHECKBOX = ("[ ]", "[x]", "[X]")
PER_MEMO_LIMIT = 60
TOTAL_LIMIT = 200
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


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


def _quote_block(text: str) -> list[str]:
    """本文先頭から最初の `## ` までにある、`>` で始まる最初の連続行。"""
    quote: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith(">"):
            quote.append(line)
        elif quote:
            break  # 連続が切れたら終わり
    return quote


def _memo_lines(text: str) -> list[str]:
    """1 つのメモから注入する行（上限を掛ける前）。無い節はその旨を 1 行出す。"""
    out: list[str] = []
    quote = _quote_block(text)
    if quote:
        out.extend(quote)
    else:
        out.append("- 引用ブロックが無い")
    grouped = _sections(text)
    titles = {h: h[3:].strip() for h in grouped}

    next_found = False
    for heading, title in titles.items():
        if any(k in title for k in NEXT_KEYWORDS):
            next_found = True
            out.append(f"### {title}")
            out.extend(line for line in grouped[heading] if line.strip())
    missing: list[str] = []
    if not next_found:
        missing.append("「次にやること／申し送り」の節")

    progress = [h for h, t in titles.items() if t.startswith(PROGRESS_PREFIX)]
    if not progress:
        missing.append("「進捗」の節")
    else:
        unchecked: list[str] = []
        any_box = False
        for heading in progress:
            for line in grouped[heading]:
                if any(b in line for b in CHECKBOX):
                    any_box = True
                if line.lstrip().startswith(UNCHECKED):
                    unchecked.append(line)
        if unchecked:
            out.append(f"### {titles[progress[0]]}（未チェックのみ）")
            out.extend(unchecked)
        elif any_box:
            out.append("- 進捗: 未チェック項目なし")
        else:
            out.append("- 進捗: チェック項目が無い")
    out.extend(f"- {label}が無い" for label in missing)
    return out


def _memo_link(cell: str) -> tuple[str, str] | None:
    m = LINK_RE.search(cell)
    return (m.group(1), m.group(2)) if m else None


def _cut(lines: list[str], limit: int, path: str) -> list[str]:
    if len(lines) <= limit:
        return lines
    return [*lines[: max(limit - 1, 0)], f"…以下は {path} を読む"]


def _display_path(p: Path) -> str:
    """注入文に載せるパス。リポジトリ内ならルート相対、外（テストの一時ディレクトリ）なら絶対。"""
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except OSError, ValueError:
        return p.as_posix()


def _in_progress_blocks(rows: list[list[str]], base_dir: Path) -> list[str]:
    """`進行中` の行ごとにメモを開き、注入行を上限つきで組み立てる。"""
    out: list[str] = []
    skipped: list[str] = []
    for row in rows:
        status = row[1] if len(row) > 1 else ""
        if IN_PROGRESS not in status:
            continue
        link = _memo_link(row[0])
        if link is None:
            # 進行中なのにメモへのリンクが無い行は、黙って落とさずに知らせる
            out.append(f"- リンクの無い進行中の行: {row[0]}")
            continue
        label, href = link
        path = _display_path(base_dir / href)
        if len(out) >= TOTAL_LIMIT:
            # 合計上限に達した後の進行中メモは名前だけ挙げる（黙って落とさない）
            skipped.append(path)
            continue
        block = [f"**進行中タスクメモ: {label}**（{path}）"]
        try:
            text = (base_dir / href).read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            block.append(f"- メモが読めない: {path}")
            out.extend([*block, ""])
            continue
        block.extend(_memo_lines(text))
        block = _cut(block, PER_MEMO_LIMIT, path)
        if len(out) + len(block) > TOTAL_LIMIT:
            block = _cut(block, max(TOTAL_LIMIT - len(out), 1), path)
            out.extend(block)
            continue
        out.extend([*block, ""])
    if skipped:
        out.append("- 合計上限のため注入しなかった進行中メモ: " + " / ".join(skipped))
    return out


def build_context(index_text: str, base_dir: Path) -> str:
    """index.md の本文から注入文を組み立てる（テストが直接呼ぶ入口）。

    base_dir はタスクメモのリンクを解決する基準（index.md の親ディレクトリ）。
    """
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
        if TASK_HEADING in missing:
            blocks[-1] += f" {TASK_HEADING} が無いので、進行中メモも注入できていない。"
        blocks.append("")

    if TASK_HEADING in grouped:
        blocks.extend(_in_progress_blocks(_table_rows(grouped[TASK_HEADING]), base_dir))

    return "\n".join(
        [
            HEADER,
            "",
            *blocks,
            "CLAUDE.md のタスク管理ルールに従い、未着手 / 進行中のものがあれば"
            "**対応するかをユーザーに尋ねること**。進行中メモを続けると決まったら、"
            "注入された申し送りから再開する。詳細は "
            "docs/task/index.md と docs/task/archive/index.md を参照。",
        ]
    )


def main() -> None:
    # 入力は使わないが、読み切ってから処理する
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        json.load(sys.stdin)

    try:
        index_text = TASK_INDEX.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return  # index.md が無い・読めない → 何も注入しない

    context = build_context(index_text, TASK_INDEX.parent)

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
