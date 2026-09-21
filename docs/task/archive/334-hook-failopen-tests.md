# #334 format_edited_file hook のフェイルオープン 2 分岐にテストを足す

> Issue: [#334](https://github.com/f8924919/yt-gui/issues/334)
> ステータス: 進行中（2026-09-22 着手）
> ブランチ: `bugfix/334-hook-failopen-tests`
> 基点: `18306ba`（`main`）
> 単一 PR で完結する小タスクなので archive に直接置く（[docs-guide.md](../../docs-guide.md) §4.2 の特例）

## 進捗（受け入れ条件 = Issue #334 の C1〜C5）

- [x] C1 `shutil.which` が `None` のとき無出力・例外なしで終わるテスト — 証跡: `tests/test_format_edited_file.py::test_main_is_silent_when_formatter_is_missing`（`cad3ae4`）
- [x] C2 整形が例外を送出するとき無出力・例外なしで終わるテスト（`OSError` 系・`subprocess.SubprocessError` 系を各 1 ケース以上） — 証跡: 同 `::test_main_is_silent_when_format_fails[oserror]`（`FileNotFoundError`）と `[subprocess-error]`（`subprocess.TimeoutExpired`）
- [x] C3 分岐に入ったこと自体を spy で確かめる（C1 は which 呼ばれた + run 呼ばれない、C2 は run 呼ばれた + 引数） — 証跡: `_spy_which` / `_spy_run` と、C1 の `assert which_calls == [...]` / `assert run_calls == []`、C2 の `assert len(run_calls) == 1` / `run_calls[0][0] == "ruff-stub"` / `run_calls[0][-1] == str(path)`
- [x] C4 変異 → red の証跡（対照 green・変異 4 つ・死因の表・復元確認・壊す前の hash） — 証跡: 下の「変異 → red」
- [x] C5 `uv run pytest -q -rs` が green で、足したテストが passed に数えられている — 証跡: 下の「対照（無変異）」。`-v` で 3 件とも `PASSED`（skipped / deselected でない）
- [ ] verify-gate — 証跡: 未

## 設計の要点

- **既存の in-process パターンに合わせる**（`_run_main(monkeypatch, payload, repo_root)` ヘルパ）。`docs/testing/policy.md` §1 が hook を「subprocess 実行で検証する」と書いていることとの乖離は [#337](https://github.com/f8924919/yt-gui/issues/337) で別に扱う（ユーザー判断 2026-09-22）。**新規テストも in-process なので乖離はわずかに広がる** — その旨を PR 本文に書く。
- **2 分岐に到達するには実在する対象ファイルが要る。** `_target()` が `path.is_file()` を要求するので、`fake_repo` fixture（`tmp_path` に `yt_gui/` `tests/` `docs/` を作る）＋ `_touch` で `yt_gui/` 配下に `.py` を置き、`REPO_ROOT` を差し替える。
- **spy の作法はリポジトリ既存のものに合わせる。** hook のテスト群には「呼ばれたか」を見る作法が無いので、`tests/test_downloader.py` の呼び出し記録（`captured = {}` / `calls: list`）に倣う。
- **C2 は 2 型それぞれのケースを持つ。** 実装は `except OSError, subprocess.SubprocessError:` の**1 つの except 節で 2 型を束ねている**ため、**tuple から片方を落とす変異**は、テストで使う例外が残った型だけだと red にならない。これが変異 ③ を入れる理由。
- **`.claude/hooks/format_edited_file.py` は変更しない。** 変える必要が出たら止めて Issue にコメントし、ユーザーに確認する（[git-workflow.md](../../git-workflow.md) §5.1）。
- **docs の更新先は無い**（hook の正本は `docs/git-workflow.md` §5.6 の表で、テストを足すだけなら記述は変わらない。`docs/arch/` に hook のファイルは無い）。

## 着手前に数えた値

数えた時点: `18306ba`（未コミットの変更なし。2026-09-22）

| # | 数えるもの | コマンド | 値 |
|---|---|---|---|
| ① | `tests/test_format_edited_file.py` のテスト関数 | `grep -c '^def test_' tests/test_format_edited_file.py` | **14** |
| ② | hook 3 ファイルのテストのうち真の subprocess 実行（#337 の根拠） | `grep -rn "_run_hook_subprocess(" tests/test_block_main_edit.py` | **2 本**（`test_session_task_status.py`・`test_format_edited_file.py` は 0 本） |

## 変異 → red（C4）

**壊す前のコミット: `cad3ae4`**（テストを足した green のコミット。作業ツリーは clean）。

### 対照（無変異・A7）

```
$ uv run pytest -q              → 603 passed
$ uv run pytest tests/test_format_edited_file.py -q -rs  → 17 passed（skip 0）
```

`-v` で新規 3 件が `PASSED` であることも確認した（`test_main_is_silent_when_formatter_is_missing`・`test_main_is_silent_when_format_fails[oserror]`・`[subprocess-error]`）。A6。

### 変異と死因

追跡下の `.claude/hooks/format_edited_file.py` を 1 か所ずつ変異させ、**各回 `git checkout -- <file>` で戻して `git diff --quiet` で無傷を確認**した（A4）。**置換対象が 1 件でなければハーネスの失敗として止める**ようにしてある（A1 の fail-closed）。

| # | 変異 | 結果 | 死因（落ちたテスト） |
|---|---|---|---|
| M1 | `if executable is None: return` を削除 | 1 failed / 16 passed | `test_main_is_silent_when_formatter_is_missing` |
| M2 | `except OSError, subprocess.SubprocessError:` を `except ZeroDivisionError:` に（try/except を実質無効化） | 2 failed / 15 passed | `test_main_is_silent_when_format_fails[oserror]`・`[subprocess-error]` |
| M3 | except の tuple から **`OSError` を落とす** | 1 failed / 16 passed | `test_main_is_silent_when_format_fails[oserror]` **のみ** |
| M4 | except の tuple から **`subprocess.SubprocessError` を落とす** | 1 failed / 16 passed | `test_main_is_silent_when_format_fails[subprocess-error]` **のみ** |

**撃墜 4 / 4。狙ったテストがそれぞれ落ちている**（件数だけでなく死因が一致）。**M3 / M4 が 2 ケース設計の根拠**で、片方のケースしか無ければ対応する tuple 縮退の変異は生き残っていた。変異後も原本は無傷（最終の `git status --porcelain` が空・HEAD は `cad3ae4`）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること

- `/verify-gate` を回す（verify → docs-check → evaluator）。
- PR 本文に変異の死因表と「既存の in-process パターンに合わせた。policy §1 との乖離は #337 で扱う」を書く。

訂正ログ: 0 件
