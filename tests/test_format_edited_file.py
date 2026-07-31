"""Claude Code PostToolUse hook（.claude/hooks/format_edited_file.py）のテスト。

hook は編集された `yt_gui/` `tests/` 配下の `.py` を `ruff format` で整形する。
対象外（拡張子違い・対象ディレクトリ外・リポジトリ外）や整形失敗は黙って通す
（フェイルオープン・#285）。

対象判定は純粋ロジックとして直接検証し、実際の整形は一時ファイルを対象
ディレクトリ配下に作って end-to-end で 1 本確認する。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "format_edited_file.py"

_spec = importlib.util.spec_from_file_location("format_edited_file", HOOK_PATH)
assert _spec is not None and _spec.loader is not None
format_edited_file = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(format_edited_file)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """`yt_gui/` `tests/` `docs/` を持つ疑似リポジトリ。"""
    for name in ("yt_gui", "tests", "docs"):
        (tmp_path / name).mkdir()
    return tmp_path


def _touch(path: Path, text: str = "x = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── 対象判定 ─────────────────────────────────────────────────────────────────


def test_target_accepts_source_dir(fake_repo):
    path = _touch(fake_repo / "yt_gui" / "app.py")
    assert format_edited_file._target(str(path), fake_repo) == path.resolve()


def test_target_accepts_tests_dir(fake_repo):
    path = _touch(fake_repo / "tests" / "test_app.py")
    assert format_edited_file._target(str(path), fake_repo) == path.resolve()


def test_target_accepts_nested_path(fake_repo):
    path = _touch(fake_repo / "yt_gui" / "locales" / "ja.py")
    assert format_edited_file._target(str(path), fake_repo) == path.resolve()


def test_target_rejects_other_suffix(fake_repo):
    path = _touch(fake_repo / "yt_gui" / "notes.md", "# x\n")
    assert format_edited_file._target(str(path), fake_repo) is None


def test_target_rejects_other_directory(fake_repo):
    """対象外ディレクトリ（docs/ 等）は verify ゲートに委ねる。"""
    path = _touch(fake_repo / "docs" / "conf.py")
    assert format_edited_file._target(str(path), fake_repo) is None


def test_target_rejects_repo_root_file(fake_repo):
    path = _touch(fake_repo / "main.py")
    assert format_edited_file._target(str(path), fake_repo) is None


def test_target_rejects_outside_repo(fake_repo, tmp_path):
    path = _touch(tmp_path / "elsewhere" / "a.py")
    assert format_edited_file._target(str(path), fake_repo) is None


def test_target_rejects_missing_file(fake_repo):
    assert (
        format_edited_file._target(str(fake_repo / "yt_gui" / "gone.py"), fake_repo)
        is None
    )


# ── main()（フェイルオープン） ───────────────────────────────────────────────


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
    repo_root: Path | None = None,
) -> None:
    if repo_root is not None:
        monkeypatch.setattr(format_edited_file, "REPO_ROOT", repo_root)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    format_edited_file.main()


def test_main_is_silent_on_invalid_stdin(monkeypatch, capsys):
    _run_main(monkeypatch, "not json")
    assert capsys.readouterr().out == ""


def test_main_is_silent_on_missing_file_path(monkeypatch, capsys):
    _run_main(monkeypatch, {"tool_input": {}})
    assert capsys.readouterr().out == ""


def test_main_is_silent_on_non_object_json(monkeypatch, capsys):
    """dict 以外の JSON（配列等）でも例外を出さず通す。"""
    for payload in ([1, 2], 42):
        _run_main(monkeypatch, payload)
    assert capsys.readouterr().out == ""


def test_main_is_silent_on_non_object_tool_input(monkeypatch, capsys):
    _run_main(monkeypatch, {"tool_input": "oops"})
    assert capsys.readouterr().out == ""


def test_main_skips_non_target_file(monkeypatch, capsys, fake_repo):
    path = _touch(fake_repo / "docs" / "conf.py", "x=1\n")
    _run_main(monkeypatch, {"tool_input": {"file_path": str(path)}}, fake_repo)
    assert capsys.readouterr().out == ""
    assert path.read_text(encoding="utf-8") == "x=1\n"  # 整形されない


# ── 実際の整形（end-to-end） ─────────────────────────────────────────────────


def test_formats_edited_file(monkeypatch, capsys):
    """本リポジトリの tests/ 配下に置いた未整形ファイルが整形される。"""
    probe = REPO_ROOT / "tests" / "_format_hook_probe.py"
    probe.write_text("x   =    1\n", encoding="utf-8")
    try:
        _run_main(monkeypatch, {"tool_input": {"file_path": str(probe)}})
        assert probe.read_text(encoding="utf-8") == "x = 1\n"
    finally:
        probe.unlink(missing_ok=True)
    assert capsys.readouterr().out == ""
