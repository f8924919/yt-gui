# claude-templates の更新（上流 #82〜#99）から docs 3 点を逆輸入

> Issue: [#333](https://github.com/f8924919/yt-gui/issues/333)
> ステータス: 進行中（2026-09-22 着手）
> ブランチ: `feature/333-template-backport`（PR [#335](https://github.com/f8924919/yt-gui/pull/335)）
> 基点: `b46c6e0`（`main`）
> 上流の基点: claude-templates `8fa3bad`（= PR #79 マージ。前回 [#326](archive/326-template-backport.md) の到達点）／取り込み対象は `origin/main` = `5b262d0`

## 進捗（受け入れ条件 = Issue #333 の C1〜C8）

- [x] C1 §8.3 C6 の母集団から出所の限定を外す（書き先は 3 か所のまま・数えた時点・暗算で書かない・実例を #326 の訂正ログへ差し替え） — 証跡: `docs/testing/policy.md` §8.3 C6「**数・件数・回数**を…**出所は問わない**」「**足した本数からの暗算・記憶・目視で書かない。**」（`ce795bd`）
- [x] C2 数え方の道具を性質と確かめ方で書く（版依存の断定をしない・プローブ・フォールバック・行数と一致数の区別） — 証跡: 同 C6「**1 行に複数ある一致を落とさないもの**」「**特定のコマンドを名指しで禁止にはしない**」「そういう道具が無い環境では、同じ正規表現を走らせて一致を並べて数える」「**行数と一致数を区別する。**」（`ce795bd`）
- [x] C3 §8.3 C5 に「その数値を出した実行の作業ツリー」を足す — 証跡: 同 C5「**貼るハッシュは「表を書いた時点の HEAD」ではなく「その数値を出した実行の作業ツリー」**」（`ce795bd`）
- [x] C4 限定を外したことに伴う注記の追従（適用範囲・義務 2/4 との違い。agent 定義 2 本と start-task 手順 3 は変更しない） — 証跡: 「C6 の適用範囲」注記の「**出所を問わない**（上記）」「**主エージェント自身が書く数に対応する agent 側の項目は無い**」、義務 2・4 の注記の「**C6 は「数そのものを、出所にかかわらず書く前に数え直す」**」。変更しなかった 3 ファイルは下の「限定語の洗い出し」
- [x] C5 訂正ログの止め規則に「誤った値そのものの語で伝播先を洗う」箇条を足す（箇条 1 の読み直し・旧 4 → 5 の繰り下げ） — 証跡: `docs/git-workflow.md`「訂正ログの止め規則」箇条 4「**訂正を 1 件積んだら、止まる前から毎回、その誤りの語で伝播先を洗う。**」・箇条 1「表を頭から読み直し」・箇条 5「（1〜4 のすべて。…）」（`ce795bd`）
- [x] C6 §8.1 に A12 を足す（A11 は明示的な欠番行・対比句は落とす・実例は yt-gui 自身・§8 冒頭の番号注記の更新・雛形との違い注記） — 証跡: `docs/testing/policy.md` の A12 行「**docs が「〜できます」と約束した挙動に、それを踏むテストがあるか**」と A11 の欠番行、§8 冒頭「項目番号（A1〜A12〈**A11 は欠番**〉/ B1〜B4 / C1〜C6）」、「雛形との違い」注記の A11 / A12 の 2 文（`ce795bd`）。対比句は「**A8 と対**」へ読み替えた
- [x] C7 取り込まないものを PR 本文に列挙する — 証跡: PR [#335](https://github.com/f8924919/yt-gui/pull/335) 本文「取り込まなかったもの（7 項目…）」（`gh issue view 333 --json body -q .body | sed -n '/### C7 /,/### C8 /p' | grep -c '^- '` → 7）
- [x] C8 検証（lint / 型 / pytest・docs-check・follow-up Issue の起票と `Follow-up: #<N>`） — 証跡: PR #335 本文の「検証」節（verify green・docs-check 3 件反映・evaluator PASS（follow-up あり））。`gh pr view 335 --json body -q .body | grep -oE '^Follow-up: #[0-9]+'` → `Follow-up: #334`
- [x] verify-gate — 証跡: verify green（ruff check / format --check / mypy 61 files / pytest 600 passed）→ docs-check 指摘 3 件を `9b8bab6` で反映 → evaluator PASS（follow-up あり）・`[欠陥]` 0 件 / `[証跡・文言]` 4 件を `7a1d686`・`e22d119` で全件この PR で直した

## 設計の要点（上流からの読み替え）

- **項目番号は上流と揃える**（#326 と同じ方針。次回の突き合わせを楽にするため）。今回は **A11 を欠番**にし、表に `| A11 | （欠番）… |` の行を明示的に置く。**行が飛ぶだけにしない** — 次に項目を足す人が番号を詰めてしまい、上流との対応が崩れる。
- **A11（雛形の木は採用先の代表か）と `scripts/adopter_tree.py` は取り込まない。** yt-gui は**採用先**であり、「自分の木が採用先の代表でない」という雛形固有の前提を持たない。理由は既存の「雛形との違い（次回の突き合わせ用）」注記へ書く。
- **上流 A12 行末の「A11 と対 — A11 は『形が無い』、A12 は『約束に錨が無い』」は落とす**（A11 を採用しないので参照が宙に浮く）。
- **A12 の実例は yt-gui 自身のものを使う。** `.claude/hooks/format_edited_file.py` の docstring が「ruff・対象ファイルのいずれかが見つからない場合や整形が失敗した場合も黙って通す（フェイルオープン）」と約束しているのに、`tests/test_format_edited_file.py` は `shutil.which` が `None` を返す分岐と `except OSError, subprocess.SubprocessError` の分岐を**どちらも踏んでいない**。**穴そのものは follow-up Issue へ落とす**（今回の PR は docs のみで完結させる）。
- **C6 の書き先は 3 か所のまま**（受け入れ条件・Issue 本文・タスクメモ）。上流 #87 が「PR 本文・Issue のコメントへ広げると §8.1 A9 の注記と連動する」として意図的に留めた設計判断で、本タスクはそこに触れない。
- **`.claude/agents/investigate.md` / `implementer.md` と `start-task` 手順 3 は変更しない。** 前 2 本の限定（「ここに書くのは報告する側に要る分だけ」）は**報告側の義務**としての限定なので妥当。手順 3 は `investigate` 起動直後の文脈に置かれた注意で、規則全体の母集団は policy が持つ（上流 #87 と同じ判断）。
- **上流に無い読み替え**: 上流 C6 の「一次資料（**登録簿**・index・一覧）」は yt-gui では既に「index・一覧・コマンドの出力」に読み替え済みなので触らない。上流 C6 の「`scripts/consistency.py refs` のような機械検査には掛からない」の除外注記と、止め規則 箇条 5 の「入れるなら形だけを WARN で見張り」は、yt-gui に該当する仕組みが無いので落とす。
- **実測値そのものを恒久 docs に置かない**（§8.1 A9）。道具の癖は版に依存するので、**性質と確かめ方**で書く（上流 #92）。

## 着手前に数えた値

数えた時点: `b46c6e0`（未コミットの変更なし。2026-09-22）

| # | 数えるもの | コマンド | 値 |
|---|---|---|---|
| ① | 上流の新規マージ PR | `git log --oneline --merges 8fa3bad..origin/main \| grep -oE 'pull request #[0-9]+' \| wc -l`（claude-templates） | **12 本** |
| ② | 上流の変更ファイル（`docs/task/` 以外） | `git diff --name-only 8fa3bad origin/main -- project-skeleton ':!project-skeleton/docs/task' \| wc -l`（同上） | **14 件** |
| ③ | `§8.3 C6` を指すポインタ | `git grep -n -F "§8.3 C6" -- .claude docs ':!docs/task/archive'` | **3 一致 / 3 行**（`implementer.md`・`investigate.md`・`start-task/SKILL.md`） |
| ④ | 旧限定語 | `git grep -n -F -e "報告にある数" -e "受け取った報告" -- . ':!docs/task/archive'` | **3 一致 / 2 行**（いずれも `docs/testing/policy.md`） |
| ⑤ | §8 冒頭の番号注記 | `git grep -n -F "A1〜A10" -- docs .claude CLAUDE.md ':!docs/task/archive'` | **1 一致 / 1 行**（`docs/testing/policy.md`）。除外を外すと **2 一致 / 2 行**（`docs/task/archive/326-template-backport.md` の経緯の記述。凍結済みなので直さない） |
| ⑥ | 現行 docs の `.md:<行>` 参照（上流 #80 を取らない根拠） | `git grep -nE '\.md:[0-9]+' -- docs .claude CLAUDE.md ':!docs/task/archive' \| wc -l` | **0 件**（木全体では 31 一致 / 4 ファイル。すべて凍結済みの `docs/task/archive/`） |

**③〜⑤は「一致数」と「当たった行数」を区別している**（④は 2 行に 3 一致。同じ行に 2 つの限定語がある）。使った道具が 1 行の複数一致を落とさないことを、④ の行（まさにその形）で確かめたプローブ:

```
$ git grep -o -F -e "報告にある数" -e "受け取った報告" b46c6e0 -- . ':!docs/task/archive' | wc -l
3
$ git grep -c -F -e "報告にある数" -e "受け取った報告" b46c6e0 -- . ':!docs/task/archive'
b46c6e0:docs/testing/policy.md:2
```

**一致 3 > 行 2** なので、この道具は 1 行に複数ある一致を落としていない。

## A12 の実例の裏取り（変異・`9b8bab6`）

`evaluator` が「主張が実測を上回る」と指摘したので、`.claude/hooks/format_edited_file.py` を 1 か所ずつ変異させて実測した（追跡下のファイルを直接変異させ、各回 `git checkout -- <file>` で復元。前後で `git status --porcelain` が空・HEAD は `9b8bab6`。[policy.md](../testing/policy.md) §8.1 A4）。

| 変異 | `uv run mypy` | `uv run pytest` |
|---|---|---|
| M1 `if executable is None: return` を**削除** | **red**（`List item 0 has incompatible type "str \| None"` 1 error） | 600 passed |
| M2 `if executable is None:` の `return` を `raise SystemExit(1)` に変える | Success（61 files） | 600 passed |
| M3 `try` / `except OSError, subprocess.SubprocessError` を外して例外を伝播させる | Success（61 files） | 600 passed |

**フェイルオープンの挙動だけを変える M2 / M3 は全部 green** で、テストはこの約束をまったく見ていない。**M1 が red になるのは型の網**（`executable` が `str | None` のまま `subprocess.run` の第 1 引数リストへ渡る）であって、挙動の錨ではない。当初 A12 に書いた「この 2 分岐を消しても検証はすべて green」は M1 で偽だったので、文面を挙動側の言い方へ直した（訂正ログ 1 件目）。

## 限定語の洗い出し（C4・新設した止め規則 箇条 4 の自己適用）

今回は「数の出所を報告に限る」という**限定を外した**ので、その限定を書いた語で木全体を洗った。数えた時点: 実装後の `ce795bd`（未コミットの変更なし）。

```
$ git grep -n -F -e "報告にある数" -e "受け取った報告" -- . ':!docs/task/archive'
docs/task/333-template-backport.md:41:| ④ | 旧限定語 | `git grep ... "報告にある数" ...` | **3 一致 / 2 行** |
$ git grep -n -F -e "サブエージェントの報告一般" -- . ':!docs/task/archive'
（0 件・exit 1）
```

着手前は **3 一致 / 2 行**（いずれも `docs/testing/policy.md`）で、両方を書き換えたので恒久 docs 側は 0 件になった。**残った 1 件は本メモ自身**で、着手前の表の行が洗い出しコマンドそのものを引用しているためのもの（現在の説明ではなく手順の記録なので直さない）。**新設した箇条 4 の「当該タスクのメモは除外しない」がそのまま効いた形** — 除外したままだとこの 1 件は見えず、「説明文として残っていないか」を確かめられなかった。

`.claude/agents/investigate.md` / `implementer.md` と `.claude/skills/start-task/SKILL.md` の 3 箇所（`git grep -n -F "§8.3 C6"` の母集団）は**意図的に変更していない** — 報告側の義務としての限定は妥当なので（上の「設計の要点」）。`git show --stat ce795bd` に 3 ファイルとも現れないことで確かめた。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|
| 2026-09-22 | A12 の実例に「この 2 分岐を消しても検証はすべて green のまま通る」と書いた | `which` 側の早期 return を**削除**すると mypy が `[list-item]` で red になる。green のまま通るのは**挙動だけを変えたとき**（M2 / M3） | **書く前に変異させて実測すること**（§8.1 A1 と同じ形。docs に「壊しても green」と書くなら、それ自体が検出力の主張なので変異の証跡が要る）。`evaluator` が複製を変異させて捕まえた |
| 2026-09-22 | 着手前の表 ⑤ に、コマンドは `':!docs/task/archive'` 無しで貼り、値は除外つきの「1 行」と書いた | 貼ったコマンドの出力は **2 一致 / 2 行**（除外つきなら 1 一致 / 1 行） | **貼るコマンドを実際に流して出力と値を突き合わせる**（§8.3 C6。③④⑥は除外を付けているのに ⑤ だけ付け忘れ、値だけ除外つきで書いた）。`evaluator` が同じコマンドを流して捕まえた |
| 2026-09-22 | PR 本文に転記する C7「取り込まないもの」の数を **6 項目**と書いた | **7 項目**（`gh issue view 333 --json body -q .body \| sed -n '/### C7 /,/### C8 /p' \| grep -c '^- '` → 7） | **数えてから書く**（§8.3 C6）。起票時は 5 項目で、着手前の `criteria-review` の指摘で 2 項目足したのに、記憶の「6」で書いた。PR 本文を書く直前に数えたので自分で捕まえた |

## 次にやること

- PR [#335](https://github.com/f8924919/yt-gui/pull/335) のレビュー・マージを待つ。マージ後は `/finish-task`。
- **訂正ログ 3 件。止め規則（[git-workflow.md](../git-workflow.md) §5.2「訂正ログの止め規則」箇条 1・3）で 2 件目と 3 件目に止まった。**2 件目では「PR 本文の数は先にコマンドを流して貼る」と決めて続け、その直後に同じ型の 3 件目が出た。**3 件目の判断（ユーザー・2026-09-22）: 以後は止めずに続ける** — 3 件はすべて「数・主張を確かめずに書いた」型で、残る作業は PR 作成のみ、そこに書く数（取り込まないもの 7 項目・変更 6 ファイル）はすべて PR 本文を書く直前に数え直す形にしたので、新たな数の主張が出ないため。
- 続けると決まったら: Issue #333 本文の C6（A12 の主張・⑤ の値）と Issue #334 本文の同じ主張を直し、PR を出す。PR 本文には C7 の「取り込まないもの」**7 項目**と `Closes #333` / 行頭の `Follow-up: #334` を並べる。

訂正ログ: 3 件（止まった: 2026-09-22）
