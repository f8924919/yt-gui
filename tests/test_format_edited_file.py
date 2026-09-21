"""Claude Code PostToolUse hook（.claude/hooks/format_edited_file.py）のテスト。

hook は編集された `yt_gui/` `tests/` 配下の `.py` を `ruff format` で整形する。
対象外（拡張子違い・対象ディレクトリ外・リポジトリ外）や整形失敗は黙って通す
（フェイルオープン・#285）。

対象判定は純粋ロジックとして直接検証し、実際の整形は一時ファイルを対象
ディレクトリ配下に作って end-to-end で 1 本確認する。フェイルオープンの 2 分岐
（整形コマンドが無い・整形の起動が失敗する）は、無出力だけでは「分岐に入って
通した」ことを区別できないので、差し替えた呼び出しの記録まで見る（#334）。
"""

import importlib.util
import io
import json
import subprocess
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


# ── フェイルオープンの 2 分岐（#334） ────────────────────────────────────────
#
# どちらの分岐も「無出力・例外なしで終わる」という同じ見え方になるので、終了の
# 仕方だけでは「分岐に入って通した」と「そこまで来ていない」を区別できない
# （policy.md §8.1 A2）。差し替えた `shutil.which` / `subprocess.run` が呼ばれた
# かどうかまで見る。


def _assert_silent(capsys) -> None:
    """フェイルオープンの「黙って通す」は stdout / stderr の両方が空であること。

    hook 自身はどこにも print せず、整形の出力も `capture_output=True` で呑む。
    stdout だけを見ると、stderr へ書く退行を見逃す（#334）。
    """
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def _spy_which(monkeypatch, result):
    """`shutil.which` を差し替え、渡されたコマンド名を記録するリストを返す。"""
    calls: list[str] = []

    def fake_which(cmd, *args, **kwargs):
        calls.append(cmd)
        return result

    monkeypatch.setattr(format_edited_file.shutil, "which", fake_which)
    return calls


def _spy_run(monkeypatch, raises=None):
    """`subprocess.run` を差し替え、渡された argv を記録するリストを返す。"""
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        if raises is None:
            raise AssertionError("このテストでは整形の成功経路を通らないはず")
        raise raises

    monkeypatch.setattr(format_edited_file.subprocess, "run", fake_run)
    return calls


def test_main_is_silent_when_formatter_is_missing(monkeypatch, capsys, fake_repo):
    """整形コマンドが見つからないときは、整形を起動せず黙って通す。"""
    path = _touch(fake_repo / "yt_gui" / "mod.py", "x   =    1")
    which_calls = _spy_which(monkeypatch, None)
    run_calls = _spy_run(monkeypatch)

    _run_main(monkeypatch, {"tool_input": {"file_path": str(path)}}, fake_repo)

    assert which_calls == [format_edited_file.FORMAT_CMD[0]]  # 分岐まで来ている
    assert run_calls == []  # 整形は起動していない
    _assert_silent(capsys)
    assert path.read_text(encoding="utf-8") == "x   =    1"  # 整形されない


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("ruff が消えた"),
        subprocess.TimeoutExpired(cmd="ruff", timeout=60),
    ],
    ids=["oserror", "subprocess-error"],
)
def test_main_is_silent_when_format_fails(monkeypatch, capsys, fake_repo, error):
    """整形の起動が失敗しても黙って通す。

    実装は `except OSError, subprocess.SubprocessError:` と 2 つの型を 1 つの節で
    束ねている。`OSError` は `subprocess.SubprocessError` を継承しない別系統なので、
    tuple から片方を落とす変異は、残った型のケースしか無いと red にならない。
    だから 2 系統それぞれのケースを持つ。
    """
    path = _touch(fake_repo / "tests" / "test_mod.py", "x   =    1")
    _spy_which(monkeypatch, "ruff-stub")
    run_calls = _spy_run(monkeypatch, raises=error)

    _run_main(monkeypatch, {"tool_input": {"file_path": str(path)}}, fake_repo)

    assert len(run_calls) == 1  # 整形を起動し、例外を受けている
    assert run_calls[0][0] == "ruff-stub"  # which の戻り値をそのまま使う
    assert run_calls[0][-1] == str(path)
    _assert_silent(capsys)
    assert path.read_text(encoding="utf-8") == "x   =    1"  # 整形されない


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
