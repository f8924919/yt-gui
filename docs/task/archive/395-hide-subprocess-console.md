# Windows の配布用ビルドで外部プログラムの起動時にコンソールウィンドウを出さない

> Issue: [#395](https://github.com/f8924919/yt-gui/issues/395)
> ステータス: 進行中
> ブランチ: `bugfix/395-hide-subprocess-console`
> 基点: `3922cdd`

受け入れ条件の正本は Issue。設計は [arch/downloader.md](../../arch/downloader.md) の「外部プログラムの起動（コンソールを出さない）」。1 PR で終わる小さなタスクなので archive に直接作った（docs-guide §4.2 の特例）。

証跡の段へ移った日と主張（policy §8.0）: 2026-11-15、`_run_external` が Windows でだけ `CREATE_NO_WINDOW` を単独で付けること、`yt_gui/` で外部プログラムを起動するのがその関数だけであること、コンソールを持たない親から起動した子がウィンドウを持たないこと（arch の「外部プログラムの起動（コンソールを出さない）」）。

## 原因（3 点）

- コード位置: `yt_gui/downloader.py` の `subprocess.run` 5 か所（danmaku2ass・区間の切り出し・チャプターごとの切り出し・MKV 統合・焼きこみ）。どれも `creationflags` を渡していない。
- 判定の構造: 配布用のビルドは `yt-gui.spec:178` の `console=False` でコンソールを持たない。Windows はコンソールを持たない親から起動したコンソールプログラムに新しいコンソール（ウィンドウ付き）を割り当てる。
- 実値: 下の「プローブ」。コンソールを持たない親（`pythonw.exe`）から起動した子の `GetConsoleWindow()` が、フラグ無しで `3671352`、`creationflags=0x08000000` で `0`。

## 進捗

- [x] C1 起動を `_run_external` にまとめ、win32 では `creationflags=0x08000000` を単独で、他の OS では渡さない — 証跡: `test_run_external_hides_console_only_on_windows`（win32 / darwin / linux。渡った引数を等値で比べる）。既存の 5 経路のテストも green（949 passed、skip 0。8acc8fc）。変異 M1〜M3
- [x] C2 `yt_gui/` で起動関数を直接呼ぶのが `_run_external` の中だけ（ast で読むテスト） — 証跡: `test_external_programs_are_started_only_via_run_external`（`yt_gui/**/*.py` を ast で読み、`subprocess.run/Popen/call/check_call/check_output`・`os.system/popen`・`from subprocess import …` を拾う）。変異 M4・M5
- [x] C3 コンソールを持たない親から `_run_external` で起動した子がウィンドウを持たない（Windows でだけ走るテスト。対照が 0 なら skip） — 証跡: `test_run_external_child_has_no_console_window_from_gui_parent`（このセッションで skip されずに pass。`-rs` の出力に SKIPPED なし）。変異 M1・M2
- [ ] C4 配布用のビルドの焼きこみでウィンドウが開かない（ユーザーの目視） — 証跡: 未
- [x] C5 arch に起動のしかたを書く — 証跡: `docs/arch/downloader.md` の「外部プログラムの起動（コンソールを出さない）」（8acc8fc）

## プローブ（2026-11-15、探索の段）

ツールのセッションの親（`uv run python`）は `GetConsoleWindow()` が 0 で、子はフラグの有無にかかわらず 0 だった（対照にならない）。そこで親を `pythonw.exe` にした。

```
noflag 3671352
flag 0
```

## 変異 → red（2026-11-15、基点 `8acc8fc`）

`yt_gui/downloader.py` を 1 か所ずつ書き換えて `uv run pytest tests/test_downloader.py -q -rfs -k "run_external or started_only"` を回し、毎回 `git checkout -- yt_gui/downloader.py` で戻した。置換は対象が 1 件あることを assert してから行った。

| 変異 | 書き換え | 落ちたテスト |
|---|---|---|
| M1 | `kwargs["creationflags"] = _CREATE_NO_WINDOW` → `pass` | `hides_console_only_on_windows[win32]`、`child_has_no_console_window_from_gui_parent` |
| M2 | `_CREATE_NO_WINDOW \| 0x00000008`（`DETACHED_PROCESS` を併用） | 同上。実プロセスのテストは `{'control': '3345112', 'run_external': '3410648'}` で、併用すると子にウィンドウが付いた |
| M3 | `if sys.platform == "win32":` → `if True:` | `hides_console_only_on_windows[darwin]`、`[linux]` |
| M4 | 焼きこみの `_run_external(` を `subprocess.run(` に戻す | `started_only_via_run_external` |
| M5 | `from subprocess import check_output` を足す | `started_only_via_run_external` |

evaluator 1 巡目の指摘を受けて、同じ手順を `24b3479` で回し直したときの出力（M0 は変異なし。FAILED 行の理由は省いた）:

```
HEAD 24b3479 2026-11-15T17:43:23+09:00
== M0
5 passed, 154 deselected in 0.83s
== M1
FAILED tests/test_downloader.py::test_run_external_hides_console_only_on_windows[win32-expected0]
FAILED tests/test_downloader.py::test_run_external_child_has_no_console_window_from_gui_parent
2 failed, 3 passed, 154 deselected in 1.01s
== M2
FAILED tests/test_downloader.py::test_run_external_hides_console_only_on_windows[win32-expected0]
FAILED tests/test_downloader.py::test_run_external_child_has_no_console_window_from_gui_parent
2 failed, 3 passed, 154 deselected in 1.41s
== M3
FAILED tests/test_downloader.py::test_run_external_hides_console_only_on_windows[darwin-expected1]
FAILED tests/test_downloader.py::test_run_external_hides_console_only_on_windows[linux-expected2]
2 failed, 3 passed, 154 deselected in 0.96s
== M4
FAILED tests/test_downloader.py::test_external_programs_are_started_only_via_run_external
1 failed, 4 passed, 154 deselected in 0.94s
== M5
FAILED tests/test_downloader.py::test_external_programs_are_started_only_via_run_external
1 failed, 4 passed, 154 deselected in 0.95s
```

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 検証ゲート

| 巡 | HEAD | verify | docs-check | evaluator |
|---|---|---|---|---|
| 1 | `24b3479` | green（949 passed、skip 0） | 指摘なし | PASS（follow-up あり。[欠陥] 0 / [証跡・文言] 2。arch が C4 を確認済みと書いていた・変異の FAILED 行が無かった。どちらもこの PR で直した） |

## 次にやること

配布用のビルド（`dist/yt-gui/yt-gui.exe`、`24b3479` と同じコード）の焼きこみをユーザーに確かめてもらう（C4）→ arch の「未確認」を直す → archive/index.md に行を足す → PR。

訂正ログ: 0 件
