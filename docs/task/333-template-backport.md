# claude-templates の更新（上流 #82〜#99）から docs 3 点を逆輸入

> Issue: [#333](https://github.com/f8924919/yt-gui/issues/333)
> ステータス: 進行中（2026-09-22 着手）
> ブランチ: `feature/333-template-backport`
> 基点: `b46c6e0`（`main`）
> 上流の基点: claude-templates `8fa3bad`（= PR #79 マージ。前回 [#326](archive/326-template-backport.md) の到達点）／取り込み対象は `origin/main` = `5b262d0`

## 進捗（受け入れ条件 = Issue #333 の C1〜C8）

- [ ] C1 §8.3 C6 の母集団から出所の限定を外す（書き先は 3 か所のまま・数えた時点・暗算で書かない・実例を #326 の訂正ログへ差し替え） — 証跡: 未
- [ ] C2 数え方の道具を性質と確かめ方で書く（版依存の断定をしない・プローブ・フォールバック・行数と一致数の区別） — 証跡: 未
- [ ] C3 §8.3 C5 に「その数値を出した実行の作業ツリー」を足す — 証跡: 未
- [ ] C4 限定を外したことに伴う注記の追従（適用範囲・義務 2/4 との違い。agent 定義 2 本と start-task 手順 3 は変更しない） — 証跡: 未
- [ ] C5 訂正ログの止め規則に「誤った値そのものの語で伝播先を洗う」箇条を足す（箇条 1 の読み直し・旧 4 → 5 の繰り下げ） — 証跡: 未
- [ ] C6 §8.1 に A12 を足す（A11 は明示的な欠番行・対比句は落とす・実例は yt-gui 自身・§8 冒頭の番号注記の更新・雛形との違い注記） — 証跡: 未
- [ ] C7 取り込まないものを PR 本文に列挙する — 証跡: 未
- [ ] C8 検証（lint / 型 / pytest・docs-check・follow-up Issue の起票と `Follow-up: #<N>`） — 証跡: 未
- [ ] verify-gate — 証跡: 未

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
| ⑤ | §8 冒頭の番号注記 | `git grep -n -F "A1〜A10" -- docs .claude CLAUDE.md` | **1 行**（`docs/testing/policy.md`） |
| ⑥ | 現行 docs の `.md:<行>` 参照（上流 #80 を取らない根拠） | `git grep -nE '\.md:[0-9]+' -- docs .claude CLAUDE.md ':!docs/task/archive' \| wc -l` | **0 件**（木全体では 31 一致 / 4 ファイル。すべて凍結済みの `docs/task/archive/`） |

**③〜⑤は「一致数」と「当たった行数」を区別している**（④は 2 行に 3 一致。同じ行に 2 つの限定語がある）。使った道具が 1 行の複数一致を落とさないことは、④ の行がまさにその形なので `git grep -o` と `git grep -c` の両方を採って確かめた（一致 3 > 行 2）。

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること

- docs の編集（C1〜C6）→ verify-gate（`/verify-gate`）→ follow-up Issue の起票 → PR。
- PR 本文には C7 の「取り込まないもの」の列挙と `Follow-up: #<N>` を必ず並べる。

訂正ログ: 0 件
