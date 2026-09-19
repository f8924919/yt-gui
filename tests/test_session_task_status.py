"""Claude Code SessionStart hook（.claude/hooks/session_task_status.py）のテスト。

hook は docs/task/index.md の 2 つの表（`## タスク` / `## 起票済み・未着手の
Issue`）を抽出し、additionalContext として注入する。ファイル欠落・パース失敗時は
何も注入せず通す（フェイルオープン・#285）。見出しが見つからないときは黙らずに
その旨を 1 行注入する（両方欠落・片方欠落とも。#326）。
`## タスク` 表で `進行中` の行はタスクメモを開き、冒頭の引用ブロック・
「次にやること／申し送り」節・「進捗」節の未チェック項目を上限つきで注入する（#326）。
進行中メモのケース表は雛形 claude-templates の `scripts/smoke_session_status.py` を移したもの。

表の抽出・整形は純粋ロジックとして直接検証し、注入の有無は `TASK_INDEX` を
差し替えた main() で確認する。実運用の index.md に対する疎通も 1 本置く。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent / ".claude" / "hooks" / "session_task_status.py"
)

_spec = importlib.util.spec_from_file_location("session_task_status", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
session_task_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session_task_status)


SAMPLE = """# タスク一覧

前書き。

## ステータス凡例

- **未着手** : 着手前

## タスク

タスクメモを持つタスク。

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [foo.md](foo.md) | 進行中 | 概要 A | 2026-07-31 |
| [bar.md](bar.md) | 未着手 | 概要 B | 2026-07-30 |

<!-- 記入例:
| [example.md](example.md) | 未着手 | 記入例は無視される | YYYY-MM-DD |
-->

## 起票済み・未着手の Issue

| Issue | 概要 | 着手時に読むもの |
|---|---|---|
| [#12](https://example.invalid/12) | 概要 C | — |
"""

EMPTY_SAMPLE = """# タスク一覧

## タスク

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| （進行中・未着手のタスクはありません） | — | — | — |

## 起票済み・未着手の Issue

| Issue | 概要 | 着手時に読むもの |
|---|---|---|
| （未着手の Issue はありません） | — | — |
"""


def _context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    task_index: Path,
    stdin_text: str = "{}",
) -> str | None:
    """`TASK_INDEX` を差し替えて main() を実行し、注入された文脈を返す。"""
    monkeypatch.setattr(session_task_status, "TASK_INDEX", task_index)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    session_task_status.main()
    out = capsys.readouterr().out
    if not out.strip():
        return None
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert isinstance(context, str)
    return context


# ── 表の抽出・整形 ───────────────────────────────────────────────────────────


def test_sections_groups_by_h2():
    grouped = session_task_status._sections(SAMPLE)
    assert "## タスク" in grouped
    assert "## 起票済み・未着手の Issue" in grouped
    assert "## ステータス凡例" in grouped


def test_sections_skips_html_comments():
    """記入例（HTML コメント）は表の行として拾わない。"""
    grouped = session_task_status._sections(SAMPLE)
    rows = session_task_status._table_rows(grouped["## タスク"])
    assert all("記入例は無視される" not in cell for row in rows for cell in row)


def test_table_rows_drops_header_and_separator():
    grouped = session_task_status._sections(SAMPLE)
    rows = session_task_status._table_rows(grouped["## タスク"])
    assert len(rows) == 2
    assert rows[0][0] == "[foo.md](foo.md)"
    assert rows[0][1] == "進行中"


def test_format_renders_rows_as_bullets():
    rows = [["[foo.md](foo.md)", "進行中", "概要 A", "2026-07-31"]]
    assert session_task_status._format(rows) == ["- [foo.md](foo.md) / 進行中 / 概要 A"]


def test_format_collapses_empty_placeholder_row():
    rows = [["（進行中・未着手のタスクはありません）", "—", "—", "—"]]
    assert session_task_status._format(rows) == ["- なし"]


# ── main()（注入 / フェイルオープン） ────────────────────────────────────────


def test_injects_both_tables(monkeypatch, capsys, tmp_path):
    index = tmp_path / "index.md"
    index.write_text(SAMPLE, encoding="utf-8")
    context = _context(monkeypatch, capsys, index)
    assert context is not None
    assert "概要 A" in context and "概要 B" in context
    assert "[#12](https://example.invalid/12)" in context
    assert "概要 C" in context


def test_injection_excludes_unrelated_sections(monkeypatch, capsys, tmp_path):
    """凡例など対象外の H2 は注入しない（文脈コストを抑えるため）。"""
    index = tmp_path / "index.md"
    index.write_text(SAMPLE, encoding="utf-8")
    context = _context(monkeypatch, capsys, index)
    assert context is not None
    assert "着手前" not in context


def test_injects_none_markers_when_empty(monkeypatch, capsys, tmp_path):
    index = tmp_path / "index.md"
    index.write_text(EMPTY_SAMPLE, encoding="utf-8")
    context = _context(monkeypatch, capsys, index)
    assert context is not None
    assert context.count("- なし") == 2


def test_fails_open_when_index_missing(monkeypatch, capsys, tmp_path):
    assert _context(monkeypatch, capsys, tmp_path / "no_such_index.md") is None


def test_reports_when_no_heading_matches(monkeypatch, capsys, tmp_path):
    """見出しが 1 つも一致しないときは黙らず、期待と実際の見出しを注入する（#326）。

    黙って諦めると見出しの改名で注入が静かに止まり、CLAUDE.md の「注入が無い =
    hook が動いていない」の判断を誤らせる。
    """
    index = tmp_path / "index.md"
    index.write_text("# タスク一覧\n\n## 別の見出し\n\n本文\n", encoding="utf-8")
    context = _context(monkeypatch, capsys, index)
    assert context is not None
    assert "期待する見出しが見つからない" in context
    assert "期待: ## タスク / ## 起票済み・未着手の Issue" in context
    assert "実際: ## 別の見出し" in context


# ── 見出しの欠落の通知（build_context） ──────────────────────────────────────

_ISSUE_HEADING = "## 起票済み・未着手の Issue"
ONLY_TASK = SAMPLE.split(_ISSUE_HEADING)[0]
ONLY_ISSUE = "# タスク一覧\n\n" + _ISSUE_HEADING + SAMPLE.split(_ISSUE_HEADING)[1]


def test_build_context_has_no_missing_note_when_both_present():
    context = session_task_status.build_context(SAMPLE, Path())
    assert "見つからなかった見出し" not in context
    assert "期待する見出しが見つからない" not in context


def test_build_context_reports_no_h2_at_all():
    context = session_task_status.build_context("# t\n\n本文だけ\n", Path())
    assert "期待する見出しが見つからない" in context
    assert "実際: （H2 見出しなし）" in context


def test_build_context_reports_missing_issue_heading():
    """片方（Issue 表）だけ欠けたら、残った表を出しつつ欠けた見出しを知らせる（#326）"""
    context = session_task_status.build_context(ONLY_TASK, Path())
    assert "概要 A" in context  # 残った表は注入される
    assert "**見つからなかった見出し**: ## 起票済み・未着手の Issue" in context
    assert "実際: ## ステータス凡例 / ## タスク" in context


def test_build_context_reports_missing_task_heading():
    context = session_task_status.build_context(ONLY_ISSUE, Path())
    assert "概要 C" in context
    assert "**見つからなかった見出し**: ## タスク（実際: " in context


def test_fails_open_on_invalid_stdin(monkeypatch, capsys, tmp_path):
    """stdin が壊れていても index.md を読めれば注入する（stdin は使わない）。"""
    index = tmp_path / "index.md"
    index.write_text(SAMPLE, encoding="utf-8")
    assert _context(monkeypatch, capsys, index, stdin_text="not json") is not None


# ── 進行中メモの注入（build_context） ──────────────────────────────────────
# 合成メモ。見出しのブレ（「進捗（…）」「【申し送り】次にやること」）は実運用で出た形。

QUOTE = (
    "> Issue: [#900](https://example.invalid/900)\n"
    "> **ステータス: 進行中**（2000-01-01 着手）\n"
    "> ブランチ: `feature/900-x`\n"
)

MEMO_FULL = (
    "# #900 — 見本\n\n" + QUOTE + "\n## 何が起きているか\n\n本文 BODY-900。\n\n"
    "## 進捗\n\n- [x] 済み DONE-900\n- [ ] 未完 TODO-900a\n  - [ ] 入れ子 TODO-900b\n"
    "* [ ] 星 TODO-900c\n- [x] 済み DONE-900d\n\n"
    "## 訂正ログ\n\n| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |\n"
    "|---|---|---|---|\n| 2000-01-01 | FIXLOG-900 | 正 | 検査 |\n\n"
    "## 次にやること（申し送り・2000-01-01 時点）\n\n1. NEXT-900 を回す。\n\n"
    "### 触ってはいけない\n\n- HANDS-OFF-900\n\n"
    "## 参考\n\nREF-900\n"
)
MEMO_VARIANT = (
    "# #901 — 見出しのブレ\n\n" + QUOTE.replace("900", "901") + "\n"
    "## 進捗（受け入れ条件 = Issue C1〜C3。証跡の列は完了時にパスを書く）\n\n"
    "- [x] C1 — 証跡: x\n- [ ] C2 TODO-901\n\n"
    "## 【申し送り】次にやること — B 案\n\nNEXT-901\n"
)
MEMO_OLD = "# 古い形式\n\n## 背景\n\nBODY-902\n\n## 結論\n\nDONE-902\n"
MEMO_ALL_DONE = (
    "# 全部済み\n\n"
    + QUOTE
    + "\n## 進捗\n\n- [x] a\n- [x] b\n\n## 次にやること\n\nNEXT-903\n"
)
MEMO_TABLE = (
    "# 表形式の進捗\n\n" + QUOTE + "\n## 進捗\n\n| 条件 | 証跡 |\n|---|---|\n"
    "| C1 | TABLE-904 |\n\n## 申し送り\n\nNEXT-904\n"
)
MEMO_NOT_STARTED = (
    "# 未着手\n\n" + QUOTE + "\n## 進捗\n\n- [ ] SHOULD-NOT-905\n\n"
    "## 次にやること\n\nSHOULD-NOT-905-next\n"
)


def _long_memo(tag: str, n: int) -> str:
    items = "\n".join(f"- [ ] {tag}-item-{i:03d}" for i in range(1, n + 1))
    return f"# {tag}\n\n{QUOTE}\n## 進捗\n\n{items}\n\n## 次にやること\n\nNEXT-{tag}\n"


def _index(rows: list[tuple[str, str]]) -> str:
    body = "".join(f"| [{f}]({f}) | {st} | 概要 | 2000-01-01 |\n" for f, st in rows)
    return (
        "# タスク一覧\n\n## タスク\n\n"
        "| タスク | ステータス | 概要 | 更新日 |\n|---|---|---|---|\n"
        + body
        + "\n<!-- 記入例:\n| [x.md](x.md) | 進行中 | y | z |\n-->\n\n"
        "## 起票済み・未着手の Issue\n\n| Issue | 概要 | 着手時に読むもの |\n|---|---|---|\n"
        "| #1 | a | b |\n"
    )


# 見出しが欠けた index。改名後の見出しと表の中身は実物に無い固有の文字列にする
# （index の差し替えが壊れて実物を読んだとき、偶然 PASS しないように）
RENAMED_TASK = "## SYNTH-改名したタスク表-7c1"
RENAMED_ISSUE = "## SYNTH-改名した Issue 表-7c1"
_TASK_TABLE = (
    "| タスク | ステータス | 概要 | 更新日 |\n|---|---|---|---|\n"
    "| [900.md](900.md) | 進行中 | SYNTH-TASK-7c1 | 2000-01-01 |\n"
)
_ISSUE_TABLE = (
    "| Issue | 概要 | 着手時に読むもの |\n|---|---|---|\n| #1 | SYNTH-ISSUE-7c1 | b |\n"
)
INDEX_NO_TASK = (
    f"# タスク一覧\n\n{RENAMED_TASK}\n\n{_TASK_TABLE}\n"
    f"## 起票済み・未着手の Issue\n\n{_ISSUE_TABLE}"
)
INDEX_NO_ISSUE = (
    f"# タスク一覧\n\n## タスク\n\n{_TASK_TABLE}\n{RENAMED_ISSUE}\n\n{_ISSUE_TABLE}"
)
INDEX_NO_BOTH = (
    f"# タスク一覧\n\n{RENAMED_TASK}\n\n{_TASK_TABLE}\n{RENAMED_ISSUE}\n\n{_ISSUE_TABLE}"
)
MISSING_ONE = "見つからなかった見出し"
MISMATCH = "期待する見出しが見つからないため表を注入できなかった"
NO_MEMO_NOTE = "進行中メモも注入できていない"

# (ID, index の行 [(ファイル名, ステータス)], ファイル {名前: 本文}, 含むべき文字列, 含まない文字列)
# ファイルに "@index" があれば、行から組み立てずにその本文を index にする
MEMO_CASES = [
    (
        "C1-in-progress-one",
        [("900.md", "進行中")],
        {"900.md": MEMO_FULL},
        ["タスクメモを持つタスク", "900.md", "ステータス: 進行中", "feature/900-x"]
        + ["NEXT-900", "HANDS-OFF-900", "TODO-900a", "TODO-900b", "TODO-900c"],
        # ## 訂正ログ は注入しない（独立 H2 の契約）。両方の見出しがあれば欠落の 1 行も出さない
        ["DONE-900", "BODY-900", "REF-900", "FIXLOG-900", MISSING_ONE, MISMATCH],
    ),
    (
        "H1-no-task-heading",
        [],
        {"@index": INDEX_NO_TASK, "900.md": MEMO_FULL},
        ["起票済み・未着手の Issue", "SYNTH-ISSUE-7c1", MISSING_ONE, "## タスク（実際"]
        + [RENAMED_TASK, NO_MEMO_NOTE],
        ["タスクメモを持つタスク", "SYNTH-TASK-7c1", "NEXT-900", MISMATCH],
    ),
    (
        "H2-no-issue-heading",
        [],
        {"@index": INDEX_NO_ISSUE, "900.md": MEMO_FULL},
        ["タスクメモを持つタスク", "SYNTH-TASK-7c1", "NEXT-900", MISSING_ONE]
        + ["## 起票済み・未着手の Issue（実際", RENAMED_ISSUE],
        ["SYNTH-ISSUE-7c1", NO_MEMO_NOTE, MISMATCH],
    ),
    (
        "H3-no-both-headings",
        [],
        {"@index": INDEX_NO_BOTH, "900.md": MEMO_FULL},
        [MISMATCH, RENAMED_TASK, RENAMED_ISSUE],
        [MISSING_ONE, "SYNTH-TASK-7c1", "SYNTH-ISSUE-7c1", "NEXT-900"],
    ),
    (
        "C1-in-progress-two-heading-variants",
        [("900.md", "進行中"), ("901.md", "進行中")],
        {"900.md": MEMO_FULL, "901.md": MEMO_VARIANT},
        ["NEXT-900", "NEXT-901", "TODO-901", "feature/901-x"],
        ["C1 — 証跡"],
    ),
    (
        "C1-not-started-is-not-opened",
        [("905.md", "未着手"), ("900.md", "進行中")],
        {"905.md": MEMO_NOT_STARTED, "900.md": MEMO_FULL},
        ["NEXT-900"],
        ["SHOULD-NOT-905"],
    ),
    (
        "C3-old-format-no-sections",
        [("902.md", "進行中")],
        {"902.md": MEMO_OLD},
        ["引用ブロックが無い", "「次にやること／申し送り」の節が無い", "「進捗」の節が無い"],
        ["BODY-902", "DONE-902"],
    ),
    (
        "C3-all-checked",
        [("903.md", "進行中")],
        {"903.md": MEMO_ALL_DONE},
        ["未チェック項目なし", "NEXT-903"],
        ["チェック項目が無い"],
    ),
    (
        "C3-no-checkbox-table-form",
        [("904.md", "進行中")],
        {"904.md": MEMO_TABLE},
        ["チェック項目が無い", "NEXT-904"],
        ["未チェック項目なし", "TABLE-904"],
    ),
    (
        "C3-memo-missing",
        [("missing.md", "進行中"), ("900.md", "進行中")],
        {"900.md": MEMO_FULL},
        ["メモが読めない: ", "missing.md", "NEXT-900"],
        [],
    ),
    (
        "C2-per-memo-limit",
        [("L.md", "進行中")],
        {"L.md": _long_memo("L", 100)},
        ["L-item-001", "…以下は ", "L.md を読む"],
        ["L-item-099"],
    ),
    (
        "C2-total-limit",
        [(t + ".md", "進行中") for t in "ABCDE"],
        {t + ".md": _long_memo(t, 70) for t in "ABCDE"},
        ["A-item-001", "…以下は ", "合計上限のため注入しなかった進行中メモ: ", "E.md"],
        ["D-item-040", "E-item-001"],
    ),
    (
        "C2-within-limit-not-cut",
        [("S.md", "進行中")],
        {"S.md": _long_memo("S", 10)},
        ["S-item-001", "S-item-010", "NEXT-S"],
        ["…以下は "],
    ),
]


@pytest.mark.parametrize(
    ("rows", "files", "must", "must_not"),
    [case[1:] for case in MEMO_CASES],
    ids=[case[0] for case in MEMO_CASES],
)
def test_build_context_in_progress_memos(tmp_path, rows, files, must, must_not):
    """進行中メモの注入（C1〜C3）と見出し欠落（H1〜H3）。メモは index の親基準で解決する。"""
    for name, text in files.items():
        if name != "@index":
            (tmp_path / name).write_text(text, encoding="utf-8")
    index_text = files.get("@index") or _index(rows)
    context = session_task_status.build_context(index_text, tmp_path)
    missing = [m for m in must if m not in context]
    present = [m for m in must_not if m in context]
    assert not missing and not present, (missing, present, context)


def test_main_injects_in_progress_memo_next_to_index(monkeypatch, capsys, tmp_path):
    """main() は index.md の親ディレクトリを基準にメモを開く（実契約の経路）。"""
    (tmp_path / "900.md").write_text(MEMO_FULL, encoding="utf-8")
    index = tmp_path / "index.md"
    index.write_text(_index([("900.md", "進行中")]), encoding="utf-8")
    context = _context(monkeypatch, capsys, index)
    assert context is not None
    assert "NEXT-900" in context and "TODO-900a" in context


# ── 実運用の index.md との疎通 ───────────────────────────────────────────────


def test_repository_task_index_is_parsable(monkeypatch, capsys):
    """本リポジトリの docs/task/index.md が hook の想定構造を満たしている。"""
    repo_index = Path(__file__).parent.parent / "docs" / "task" / "index.md"
    context = _context(monkeypatch, capsys, repo_index)
    assert context is not None
    assert "タスクメモを持つタスク" in context
    assert "起票済み・未着手の Issue" in context
