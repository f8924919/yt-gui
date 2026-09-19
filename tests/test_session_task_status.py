"""Claude Code SessionStart hook（.claude/hooks/session_task_status.py）のテスト。

hook は docs/task/index.md の 2 つの表（`## タスク` / `## 起票済み・未着手の
Issue`）を抽出し、additionalContext として注入する。ファイル欠落・パース失敗時は
何も注入せず通す（フェイルオープン・#285）。見出しが見つからないときは黙らずに
その旨を 1 行注入する（両方欠落・片方欠落とも。#326）。

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
    context = session_task_status.build_context(SAMPLE)
    assert "見つからなかった見出し" not in context
    assert "期待する見出しが見つからない" not in context


def test_build_context_reports_no_h2_at_all():
    context = session_task_status.build_context("# t\n\n本文だけ\n")
    assert "期待する見出しが見つからない" in context
    assert "実際: （H2 見出しなし）" in context


def test_build_context_reports_missing_issue_heading():
    """片方（Issue 表）だけ欠けたら、残った表を出しつつ欠けた見出しを知らせる（#326）"""
    context = session_task_status.build_context(ONLY_TASK)
    assert "概要 A" in context  # 残った表は注入される
    assert "**見つからなかった見出し**: ## 起票済み・未着手の Issue" in context
    assert "実際: ## ステータス凡例 / ## タスク" in context


def test_build_context_reports_missing_task_heading():
    context = session_task_status.build_context(ONLY_ISSUE)
    assert "概要 C" in context
    assert "**見つからなかった見出し**: ## タスク（実際: " in context


def test_fails_open_on_invalid_stdin(monkeypatch, capsys, tmp_path):
    """stdin が壊れていても index.md を読めれば注入する（stdin は使わない）。"""
    index = tmp_path / "index.md"
    index.write_text(SAMPLE, encoding="utf-8")
    assert _context(monkeypatch, capsys, index, stdin_text="not json") is not None


# ── 実運用の index.md との疎通 ───────────────────────────────────────────────


def test_repository_task_index_is_parsable(monkeypatch, capsys):
    """本リポジトリの docs/task/index.md が hook の想定構造を満たしている。"""
    repo_index = Path(__file__).parent.parent / "docs" / "task" / "index.md"
    context = _context(monkeypatch, capsys, repo_index)
    assert context is not None
    assert "タスクメモを持つタスク" in context
    assert "起票済み・未着手の Issue" in context
