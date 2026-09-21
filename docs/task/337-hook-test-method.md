# #337 policy §1 の hook のテスト方式を実態に合わせる

> Issue: [#337](https://github.com/f8924919/yt-gui/issues/337)
> ステータス: 進行中（2026-09-22 着手）
> ブランチ: `bugfix/337-hook-test-method`
> 基点: `3bdf5db`（`main`）

## 進捗（受け入れ条件 = Issue #337 の C3〜C7）

- [x] C3 §1 の hook の 2 行を書き直す（ファイル名で名指し・誤記の訂正・新規の模範・`uv` 経路の逐語・具体数を書かない） — 証跡: `docs/testing/policy.md` §1 の hook 2 行（「**全件をスクリプトとして起動して検証する**」「**判定ロジックは in-process で検証する**」「`session_task_status.py` と `format_edited_file.py` には**起動するテストが無い**」）と、表の直後の注記「**hook のテストの方式**」（新規の模範・in-process を原則にする理由・起動経路で見るもの・`uv` の逐語）
- [x] C4 記述と実態の一致を、コマンド・出力・ハッシュつきで記録する — 証跡: 下の「C4 の実測」（基点 `3bdf5db`・作業ツリー clean）
- [x] C5 兄弟の記述を追従させる（母集団と語を明示して洗う） — 証跡: 下の「C5 の洗い出し」表。`tests/test_block_main_edit.py` の冒頭 docstring を追従させ、`docs/task/` の 4 件は `#337` への参照なので直していない
- [x] C6 `uv run pytest` green・`ruff format --check` 通過。テスト関数は変えない — 証跡: `uv run pytest -q` → 603 passed、`uv run ruff format --check .` → 61 files already formatted。`tests/` の変更は `test_block_main_edit.py` の**冒頭 docstring のみ**（テスト関数・fixture・アサーションは無変更）
- [x] C7 書いた後に C4 を流し直し、文言と実測の一致を確かめる — 証跡: 下の「C7 の自己レビュー」。**自分が課した「具体数を書かない」に自分で違反していたのを捕まえた**
- [ ] verify-gate — 証跡: 未

## C1 の記録（`block_main_commit.py` が全件スクリプト起動である理由）

**Issue 本文の「決めたこと」と重複させず、ここを正本にする**（将来 B〈実態を subprocess へ寄せる〉を再検討する人が同じ調査を繰り返さないため）。

- **起源は hook の初導入（[#232](https://github.com/f8924919/yt-gui/issues/232) / PR [#233](https://github.com/f8924919/yt-gui/pull/233)）の「疎通確認」節**。要旨は「hooks はセッション開始時に読み込まれるため、`settings.json` と同一の起動コマンド形式で stdin JSON を流す実地シミュレーションで代替した」。**「だから subprocess にした」という明示的な因果は書かれていない**ので、PR #233 の文脈から読み取れる範囲に留まる。
- **[#240](https://github.com/f8924919/yt-gui/issues/240)（クロスリポジトリ）は既存方式を踏襲しただけ**で、新たに subprocess を選んだ理由は書かれていない（[240-hook-cross-repo.md](archive/240-hook-cross-repo.md)）。
- **subprocess テストでしか見つけられなかった不具合の実例は見当たらなかった。** 調べた範囲は #232 / #233 / #235 / #236 / #240 / #241。**実際に不発火を見つけたのは [#235](https://github.com/f8924919/yt-gui/issues/235) / PR [#236](https://github.com/f8924919/yt-gui/pull/236) の exec form の問題で、pytest ではなくセッション内の実地 smoke**（shell form のままだとシェル展開・PATH 解決に依存し、素の `git commit` が deny されなかった）。
- **メモリにある「main 保護 hook のライブ発火が不安定」（2026-07-12）は #232 の subprocess 設計（2026-07-11）より後**なので、その問題が設計の動機だったわけではない。

## C4 の実測

**基点 `3bdf5db`（未コミットの変更なし。2026-09-22）。** 「hook をスクリプトとして起動しているか」は **`sys.executable` と `HOOK_PATH` を渡している箇所**で数える。`subprocess.run` を語として数えると、`monkeypatch` の行やコメント・docstring に当たって**多く出る**（`tests/test_format_edited_file.py` は 2 行当たるが、どちらもコメントと docstring で起動は 0 本）。

```
$ grep -c '^def test_' tests/test_block_main_commit.py tests/test_block_main_edit.py tests/test_session_task_status.py tests/test_format_edited_file.py
tests/test_block_main_commit.py:40
tests/test_block_main_edit.py:23
tests/test_session_task_status.py:19
tests/test_format_edited_file.py:16
$ grep -rn "sys.executable" tests/test_block_main_commit.py tests/test_block_main_edit.py tests/test_session_task_status.py tests/test_format_edited_file.py
tests/test_block_main_commit.py:33:        [sys.executable, str(HOOK_PATH)],
tests/test_block_main_edit.py:235:        [sys.executable, str(HOOK_PATH)],
$ grep -c "= _run_hook_subprocess(" tests/test_block_main_edit.py
2
$ grep -c "importlib" tests/test_block_main_commit.py tests/test_block_main_edit.py tests/test_session_task_status.py tests/test_format_edited_file.py
tests/test_block_main_commit.py:0
tests/test_block_main_edit.py:3
tests/test_session_task_status.py:3
tests/test_format_edited_file.py:3
```

| テストファイル | テスト関数 | スクリプト起動 | in-process |
|---|---|---|---|
| `tests/test_block_main_commit.py` | 40 | **全件**（`importlib` が 0 件で、hook へ届く経路は起動ヘルパ 1 本だけ） | 無し |
| `tests/test_block_main_edit.py` | 23 | **2 本**（フェイルオープン系） | 残り |
| `tests/test_session_task_status.py` | 19 | **0 本** | 全件 |
| `tests/test_format_edited_file.py` | 16 | **0 本** | 全件 |

**`block_main_commit.py` の「全件」は、`importlib` が 0 件であることから導いた**（hook のロジックへ届く経路が起動ヘルパしかない）。起動ヘルパを呼ぶ行を数えると 43 行だが、これは定義行と入れ子のヘルパを含むので**テスト本数とは一致しない** — 数として使わない。

## C5 の洗い出し

母集団は `docs/` 配下・`.claude/` 配下・`CLAUDE.md`・`tests/*.py`。語は `subprocess 実行で検証` / `subprocess で検証` / `subprocess 実行で確認` / `スクリプトとして起動` / `importlib で読み込み`。

| 当たった場所 | 判定 |
|---|---|
| `docs/testing/policy.md` の hook 2 行と新しい注記 | **書き換え対象そのもの**（C3） |
| `tests/test_block_main_edit.py` の冒頭 docstring | **追従させた**（C5）。理由づけは両方残す — 「ブランチに依存せず `REPO_ROOT` の差し替えも要らない」（なぜ起動でよいか）と「`if __name__ == "__main__":` を通る経路を見る唯一のテスト」（起動で何が見えるか）。方式の正本は §1 を指す |
| `tests/test_block_main_edit.py` の起動テストの docstring（「スクリプトとして起動しても不正入力で落ちない」） | **変更不要**（新しい記述と整合） |
| `docs/task/archive/334-hook-failopen-tests.md`・`docs/task/archive/index.md`・`docs/task/index.md` | **`#337` への参照**（「#337 で別に扱う」）であって独立した主張ではない。**直さない** |
| `docs/testing/policy.md` の `download_binaries.py` の行の「`importlib` で読み込み」 | **正しい**（`tests/test_download_binaries.py` に `importlib` が実在）。無関係 |

`docs/git-workflow.md`・`.claude/rules/*`・`CLAUDE.md` は**当たり 0 件**。

## C7 の自己レビュー

C3 を書き終えたあとに C4 の数え直しと、**書いた文言そのものの点検**を流した。

```
$ sed -n '34,44p' docs/testing/policy.md | grep -oE '[0-9]+ *(本|件|個)|全 [0-9]+'
2 本
```

**自分が C3 で決めた「policy.md に具体数を書かない」に、自分で違反していた** — 注記の「スクリプトとしての起動経路で見るもの」に「（`block_main_edit.py` の 2 本）」と書いていた。「（`block_main_edit.py` のフェイルオープン系）」に直し、同じ grep が 0 件になることを確かめた。

**この型は #333 の訂正ログ 3 件と同じ**（自分が書く数・主張を確かめずに書く）。今回は**規則を書いた直後に自分で当てた**ので、訂正ログを積む前に捕まえられた。C7 を条件に入れた `criteria-review` の指摘が効いた形。

数え直しの結果は「C4 の実測」の表と一致した（`sys.executable` の行番号だけ `tests/test_block_main_edit.py:235` → `:237` に動いた — docstring を 2 行増やしたため。**行番号を主張に使っていないので表の値は不変**）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること

- `/verify-gate`（verify → docs-check → evaluator）→ PR。**PR に archive 移動を同梱する**（docs-guide §4.2 の原則。#334 と同じ形）。
- 本 PR では **`settings.json` の `uv run …` の起動形式を叩くテストは足さない**（ユーザー判断 2026-09-22）。docs に「見ていない」と明記するところまで。

訂正ログ: 0 件
