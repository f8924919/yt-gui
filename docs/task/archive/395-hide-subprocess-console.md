# Windows の配布用ビルドで外部プログラムの起動時にコンソールウィンドウを出さない

> Issue: [#395](https://github.com/f8924919/yt-gui/issues/395)
> ステータス: 進行中
> ブランチ: `bugfix/395-hide-subprocess-console`
> 基点: `3922cdd`

受け入れ条件の正本は Issue。設計は [arch/downloader.md](../../arch/downloader.md) の「外部プログラムの起動（コンソールを出さない）」。1 PR で終わる小さなタスクなので archive に直接作った（docs-guide §4.2 の特例）。

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

## 訂正ログ

| 日付 | 誤って書いたこと | 正しくは | 原因と再発防止 |
|---|---|---|---|

## 次にやること

`/verify-gate` → 配布用のビルドをユーザーに確かめてもらう（C4）→ PR。

訂正ログ: 0 件
