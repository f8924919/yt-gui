# #337 policy §1 の hook のテスト方式を実態に合わせる

> Issue: [#337](https://github.com/f8924919/yt-gui/issues/337)
> ステータス: 完了（2026-09-22 着手・完了。PR [#339](https://github.com/f8924919/yt-gui/pull/339)）
> ブランチ: `bugfix/337-hook-test-method`
> 基点: `3bdf5db`（`main`）

## 進捗（受け入れ条件 = Issue #337 の C3〜C7）

- [x] C3 §1 の hook の 2 行を書き直す（ファイル名で名指し・誤記の訂正・新規の模範・`uv` 経路の逐語・具体数を書かない） — 証跡: `docs/testing/policy.md` §1 の hook 2 行（「**全件をスクリプトとして起動して検証する**」「**判定ロジックは in-process で検証する**」「`session_task_status.py` と `format_edited_file.py` には**起動するテストが無い**」）と、表の直後の注記「**hook のテストの方式**」（新規の模範・in-process を原則にする理由・起動経路で見るもの・`uv` の逐語）
- [x] C4 記述と実態の一致を、コマンド・出力・ハッシュつきで記録する — 証跡: 下の「C4 の実測」（基点 `3bdf5db`・作業ツリー clean）
- [x] C5 兄弟の記述を追従させる（母集団と語を明示して洗う） — 証跡: 下の「C5 の洗い出し」表。`tests/test_block_main_edit.py` の冒頭 docstring を追従させ、`docs/task/` の 4 件は `#337` への参照なので直していない
- [x] C6 `uv run pytest` green・`ruff format --check` 通過。テスト関数は変えない — 証跡: `uv run pytest -q` → 603 passed、`uv run ruff format --check .` → 61 files already formatted。`tests/` の変更は `test_block_main_edit.py` の**冒頭 docstring のみ**（テスト関数・fixture・アサーションは無変更）
- [x] C7 書いた後に C4 を流し直し、文言と実測の一致を確かめる — 証跡: 下の「C7 の自己レビュー」。**自分が課した「具体数を書かない」に自分で違反していたのを捕まえた**
- [x] verify-gate — 証跡: verify green（ruff / mypy 61 files / pytest 603 passed・skip 0）→ docs-check 判断事項 3 件を反映 → evaluator **1 巡目 FAIL**（`[欠陥]` 1 / `[証跡・文言]` 4）→ 全件を閉じて **2 巡目 PASS（follow-up あり）**（`[欠陥]` 0 / `[証跡・文言]` 3）・3 件ともこの PR で直した

## C1 の記録（`block_main_commit.py` が全件スクリプト起動である理由）

**Issue 本文の「決めたこと」と重複させず、ここを正本にする**（将来 B〈実態を subprocess へ寄せる〉を再検討する人が同じ調査を繰り返さないため）。

**結論: この方式を選んだ理由は、一次資料のどれも実態と合っていない。** だから `docs/testing/policy.md` §1 には**理由を書かず**、検証済みの事実（全件をスクリプトとして起動している・`sys.executable` で `.py` を直叩きしている）だけを書いた（ユーザー判断 2026-09-22・案 c）。調べた内容は次のとおり。

| 一次資料 | 書かれている理由 | 実態との突き合わせ |
|---|---|---|
| [#232](https://github.com/f8924919/yt-gui/issues/232) の「対応内容」項目 3 | 「`tests/` に hook スクリプトの単体テストを追加する（subprocess で stdin JSON を流し出力を検証。scripts のテスト前例 `test_refresh_pins.py` **等に倣う**）」 | **前例自身が in-process** — `grep -c "importlib" tests/test_refresh_pins.py` → 3、`grep -c "sys.executable" tests/test_refresh_pins.py` → 0。**倣った先と方式が一致していない** |
| PR [#233](https://github.com/f8924919/yt-gui/pull/233) の「疎通確認」節 | 「`settings.json` と同一の起動コマンド形式で stdin JSON を流す実地シミュレーションで代替した」 | これは**手動 smoke** の記述（pytest は同 PR で「新規・13 テスト」として別項目）。**pytest は登録形式を再現していない** — テストは初版 `353e8b2` から現在まで `[sys.executable, str(HOOK_PATH)]` で、登録は `uv run --no-sync --project … python <path>` |
| [#240](https://github.com/f8924919/yt-gui/issues/240)（クロスリポジトリ） | 記述なし（[240-hook-cross-repo.md](240-hook-cross-repo.md) は「subprocess 起動方式を踏襲」） | **既存方式の踏襲のみ**で、選んだ理由は書かれていない |

**subprocess テストでしか見つけられなかった不具合の実例は見当たらなかった。** 調べた範囲は #232 / #233 / #235 / #236 / #240 / #241。**実際に不発火を見つけたのは [#235](https://github.com/f8924919/yt-gui/issues/235) / PR [#236](https://github.com/f8924919/yt-gui/pull/236) の exec form の問題で、pytest ではなくセッション内の実地 smoke**（shell form のままだとシェル展開・PATH 解決に依存し、素の `git commit` が deny されなかった）。**pytest が登録形式を再現していたなら #235 は pytest で red になっていたはず**で、これも「再現していない」ことの裏付けになる。

**メモリにある「main 保護 hook のライブ発火が不安定」（2026-07-12）は #232 の設計（2026-07-11）より後**なので、その問題が動機だったわけではない。

### 当初この節に書いていた誤り（`evaluator` が検出。**巡回表が正本で、訂正ログには載せない** — [docs-guide.md](../../docs-guide.md) §3.2「evaluator の指摘は載せない（…訂正ログにも数えると二重に止まる）」）

最初は `policy.md` §1 に「`settings.json` と同じ起動形式を pytest で再現し、セッション内での発火確認の代替にした経緯（#232 / PR #233）」と書いた。**これは偽で、しかも同じ節の 9 行下に置いた「登録された起動形式そのものは、いずれのテストも検証していない」と正面から矛盾していた** — **この Issue が除こうとした乖離を、同じ節の中で再生産していた**。原因は、`investigate` の報告が引いた PR #233 の「疎通確認」節の文面を、**それが pytest の話なのか手動 smoke の話なのかを確かめずに転記した**こと。

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

**`block_main_commit.py` の「全件」は、`importlib` が 0 件であることから導いた**（hook のロジックへ届く経路が起動ヘルパしかない）。**起動ヘルパを呼ぶ行を数えてもテスト本数とは一致しない**（定義行と入れ子のヘルパを含み、引く語をどう選ぶかで値が動く）ので、**その数は使わない** — `importlib` が 0 件であることの方が、「hook のロジックへ届く経路が起動しかない」を直接に言える。

## C5 の洗い出し

母集団は `docs/` 配下・`.claude/` 配下・`CLAUDE.md`・`tests/*.py`。語は `subprocess 実行で検証` / `subprocess で検証` / `subprocess 実行で確認` / `スクリプトとして起動` / `importlib で読み込み`。**`importlib 読込`（助詞なし）を入れていなかったので 1 件取りこぼした**（`evaluator` が検出。下の表の `240-hook-cross-repo.md` の行）— **語形の揺れ（助詞の有無・送り仮名）まで広げて引くこと**。

| 当たった場所 | 判定 |
|---|---|
| `docs/testing/policy.md` の hook 2 行と新しい注記 | **書き換え対象そのもの**（C3） |
| `tests/test_block_main_edit.py` の冒頭 docstring | **追従させた**（C5）。理由づけは両方残す — 「ブランチに依存せず `REPO_ROOT` の差し替えも要らない」（なぜ起動でよいか）と「`if __name__ == "__main__":` から通す」（起動で何が見えるか）。**「唯一のテスト」とは書かない** — `block_main_commit.py` 側は全件がその経路を通るので、リポジトリ全体で読むと偽になる（`docs-check` の指摘）。方式の正本は §1 を指す |
| `tests/test_block_main_edit.py` の起動テストの docstring（「スクリプトとして起動しても不正入力で落ちない」） | **変更不要**（新しい記述と整合） |
| `docs/task/archive/334-hook-failopen-tests.md`・`docs/task/archive/index.md`・`docs/task/index.md` | **`#337` への参照**（「#337 で別に扱う」）であって独立した主張ではない。**直さない** |
| `docs/task/archive/240-hook-cross-repo.md`「`tests/test_block_main_commit.py` 新設（**importlib 読込**・一時 git リポジトリで検証）」 | **`#337` への参照ではなく、§1 で訂正したのと同じ誤りの独立した主張**（`evaluator` が検出。当初の洗い出しは語 `importlib で読み込み` で引いたので `importlib 読込` に当たらなかった）。**直さない判断（本タスクの判断。規定ではない）**: archive は**その時点の記録**で、書き直すと「当時そう理解していた」という事実まで消える。**近い規定は [docs-guide.md](../../docs-guide.md) §3.2 の「それより前のタスクメモ（archive を含む）は自由形式のまま置いておく（書き直さない）」だが、これは体裁の話で、事実の誤りを凍結してよいとは書いていない**（`evaluator` の指摘。当初は §4.2 を出典として挙げていたが、§4.2 は archive 移動の手順だけで該当規定は無い）。**誤りの訂正の正本は `policy.md` §1 と本メモ**。**archive 側から訂正へ辿れるように、[archive/index.md](index.md) の「完了タスクの経緯・申し送り」へ訂正のポインタを 1 行置いた**（[docs-guide.md](../../docs-guide.md) §3.2 の「完了したタスクの経緯…は archive/index.md の『完了タスクの経緯・申し送り』へ書く」に従う。**当初は「archive からそこへ辿れる」と書いていたが、`archive/240-hook-cross-repo.md` に `#337` への参照は 0 件で偽だった** — `evaluator` が検出）。なお `docs/task/archive/285-template-backport.md` の「subprocess 実行だけでは deny 経路を再現できない」は新しい記述と整合する |
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

数え直しの結果は「C4 の実測」の表と一致した（docstring の行数を変えたので `sys.executable` の**行番号は動く**が、**行番号を主張の根拠に使っていない**ので表の値は不変。行番号そのものはここに書かない — 書けばそれ自体が腐る）。

## 数の語の洗い出しで 2 度取りこぼした（`docs-check` / `evaluator` が検出）

`policy.md` の注記に「`format_edited_file.py` のフェイルオープン **2 分岐**」という数が残っていた。当初は「**hook のコードが持つ分岐の数は構造そのものだから残してよい**」と判断したが、**C3 の文面にその例外は無く**、`tests/test_format_edited_file.py` の docstring と重複した数でもある（§8.1 A9）。**例外を作らず数を落とした**（「フェイルオープンの各分岐」）。

**洗い出しの語を 2 度狭く採って取りこぼした。**

| 誰が | 引いた語 | 結果 |
|---|---|---|
| 主エージェント（C7） | `(本\|件\|個)` | **取りこぼし**（「2 分岐」に当たらない） |
| `docs-check` | `(本\|件\|個\|つ\|分岐)` | 1 件検出 |
| `evaluator` | 上に `箇所\|行\|回\|通り\|種\|ケース` 等を足し、漢数字も対象 | 同じ 1 件のみ（他に残数なし） |

**教訓: 「数を書いていないか」を引くときは、数の単位を列挙で当てにいくと必ず漏れる。** 単位を広く採るか、`[0-9]` と漢数字の出現そのものを見て 1 件ずつ読む方が確実。最終の確認は `sed -n '34,44p' docs/testing/policy.md | grep -noE '[0-9]+ *(本|件|個|つ|分岐|箇所|行|回|通り|種|ケース)|全 [0-9]+'` で 0 件（**範囲は §1 の hook 2 行と直後の注記**。`policy.md` 全体にかけると §2.6 / §8 の既存散文に当たる）。

## evaluator の指摘と閉じ方（1 巡目・FAIL・`[欠陥]` 1 / `[証跡・文言]` 4）

**再評価の起動プロンプトにこの表を渡す**（[git-workflow.md](../../git-workflow.md) §5.2「止め時の規則」3）。

| 区分 | 指摘 | 閉じ方の種別 | 証跡 |
|---|---|---|---|
| `[欠陥]` | `policy.md` §1 の経緯「`settings.json` と同じ起動形式を pytest で再現し、セッション内での発火確認の代替にした」が偽で、同じ節の 9 行下の「登録形式はいずれのテストも検証していない」と矛盾 | **条件改訂 + 記述の書き換え**（ユーザー判断・案 c: 経緯を落として事実だけにする）。Issue #337 の C3 の指示文も訂正した | `docs/testing/policy.md` §1 の `block_main_commit.py` の行（「**この方式を選んだ理由は一次資料で裏取りできていない**ので、ここには書かない」）・本メモ「C1 の記録」の一次資料 3 点の表・下の「当初この節に書いていた誤り」 |
| `[証跡・文言]` | 「フェイルオープン **2 分岐**」が policy.md に残る（C3 の禁止に例外は無い・docstring と重複） | **記述の書き換え**（数を落とす）。C3 に「例外は作らない」を明記 | 同注記「フェイルオープンの各分岐」・本メモ「数の語の洗い出しで 2 度取りこぼした」 |
| `[証跡・文言]` | メモの行番号（`:235` → `:237`）が HEAD（`:239`）と不一致。**数の腐りを論じる段落の中で数が腐っていた** | **記述の書き換え**（行番号を書かない） | 本メモ「C7 の自己レビュー」 |
| `[証跡・文言]` | C5 の洗い出しが `archive/240-hook-cross-repo.md` の「`importlib` 読込」を取りこぼした（語形の揺れ） | **記述の追記**（語形の揺れまで引く旨と、archive を直さない判断） | 本メモ「C5 の洗い出し」の表と語の一覧 |
| `[証跡・文言]` | C1 の記録が #232 の明示的理由（前例に倣う）を落としていた | **記述の書き換え**（一次資料 3 点の表にして、どれも実態と合っていないことまで書いた） | 本メモ「C1 の記録」 |

**`evaluator` が「対象外」と判定した軸**: 評価軸 5（変異 → red）— 判定ロジック・テスト・hook を足していない（`tests/` の差分は docstring のみ）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること

- `/verify-gate`（verify → docs-check → evaluator）→ PR。**PR に archive 移動を同梱する**（docs-guide §4.2 の原則。#334 と同じ形）。
- 本 PR では **`settings.json` の `uv run …` の起動形式を叩くテストは足さない**（ユーザー判断 2026-09-22）。docs に「見ていない」と明記するところまで。

訂正ログ: 0 件（`evaluator` の指摘 1 巡分は上の巡回表が正本。docs-guide §3.2 により訂正ログには数えない）
