---
name: start-task
description: タスクの立ち上げを定型化する。Issue 確認/起票（本文の鮮度チェック）→ main 最新化＋ブランチ作成 → investigate 起動 → 受け入れ条件レビュー（criteria-review・助言）→ docs 先行ゲート（タスクメモをここで作る）→（§5.5 発火時）設計レビュー（design-review・助言）→ テスト先行ゲート → 実装（自分で書くか implementer へ委譲するかの分岐）、の順に進める。特に「docs 先・テストファースト」の順序を強制し、実装先行（順序逆転）を防ぐ。新しいタスクに着手するときに使う。
argument-hint: "[issue-number or task-description]"
---

# start-task — タスク立ち上げ（ワークフロー前半）

[docs/git-workflow.md](../../../docs/git-workflow.md) §5 step 1〜6 を定型化するオーケストレーション skill。`verify-gate`（step 7）・`finish-task`（step 9）と対になる前半の入口。
**ルール（Issue テンプレ・ブランチ命名・更新先など）の正本は git-workflow §3/§4/§5**。この skill は順序と入口に徹し、ルールを再定義しない。

## この skill の最重要目的：順序の強制

**docs 先・テストファースト**を順序ゲートとして強制する。実装を docs/テストより先に進めない（過去に順序逆転の指摘実績あり）。step 4・5 を飛ばして step 6 に進まないこと。

## 手順

1. **Issue 確認 / 起票**（§3）
   - 対象 Issue があれば内容（背景・受け入れ条件・対象範囲）を確認する。
   - **本文の鮮度（二値）**: 本文の編集時刻（GraphQL の `lastEditedAt`、null なら `createdAt`）と、本文が**前提**にしている Issue の `closedAt` を時刻で比べる。**本文の方が古ければ、着手前に本文を現状（前提タスクの archive メモ・現在の docs とコード）と突き合わせて直し、直した旨と旧本文からの変更点をコメントに残してから進む**（起票時の本文が前提タスクより前の実装を書いていて、着手時に全面書き直しになる事故を、着手前の 1 コマンドで見つける）。**前提が open のままならユーザーに確認する**（**【通知】** [git-workflow.md](../../../docs/git-workflow.md) §5.8）。
     - **前提** = 本文**またはコメント**で依存として引かれている Issue（「#n → 本 Issue の順で着手」「#n で追加した〜を使う」など）。背景に経緯として出てくる Issue は含めない。前提が無ければこの確認は不要。
     - `updatedAt` は使わない（コメントの追加でも進む）。前提ごとに 1 回、次を Bash ツールで実行する（`<n>` = 本 Issue、`<p>` = 前提）:

       ```bash
       gh api graphql -F owner='{owner}' -F repo='{repo}' -F n=<n> -F p=<p> -f query='query($owner:String!,$repo:String!,$n:Int!,$p:Int!){repository(owner:$owner,name:$repo){a:issue(number:$n){number createdAt lastEditedAt} b:issue(number:$p){number state closedAt}}}' --jq '.data.repository | (.a.lastEditedAt // .a.createdAt) as $t | if .b.state == "OPEN" then "#\(.a.number): 前提 #\(.b.number) が open → ユーザーに確認" elif $t < .b.closedAt then "#\(.a.number): 本文 \($t) < #\(.b.number) の close \(.b.closedAt) → 本文を直してから進む" else "#\(.a.number): 本文 \($t) >= #\(.b.number) の close \(.b.closedAt) → 進む" end'
       ```
   - 無ければ §3 テンプレ（背景/目的・受け入れ条件・対象ファイル・関連 docs リンク）で起票する。受け入れ条件の中身はユーザーと確認しながら決める（勝手に確定しない）。**【通知】** ここで止まるので通知を出す（[git-workflow.md](../../../docs/git-workflow.md) §5.8）。

2. **`main` 最新化＋ブランチ作成**（§4）
   - `git checkout main && git pull --ff-only origin main`
   - §4 の命名規則でブランチを作成する（Issue を伴う作業は `feature/<issue>-<desc>` / `bugfix/...` / `hotfix/...`、伴わない作業は `refactor/` `docs/` `chore/`）。

3. **調査（`investigate` 起動）**（step 3）
   - `investigate` サブエージェントを起動し、docs 先・コード裏取りの結論（要点・関連 `path:line`・裏取りメモ）だけを受け取る。
   - **設計・実装方針の判断は委譲しない**。investigate は判断材料の収集のみ。
   - **報告に出てきた数・件数・回数を、そのまま受け入れ条件・Issue 本文・タスクメモへ転記しない。** 転記する前に**一次資料を自分で数える**（規則の正本は [testing/policy.md](../../../docs/testing/policy.md) §8.3 C6。ここには再掲しない）。

3.5. **受け入れ条件レビュー（`criteria-review` 起動）**（step 3.5）
   - `investigate` の結論を踏まえ、`criteria-review` サブエージェントを起動して受け入れ条件・spec **そのものの妥当性**（テスト可能・網羅的・非曖昧・Issue 意図との整合）を点検し、指摘・改善案を受け取る。
   - **`bugfix` / 原因の特定を含む Issue、テスト・hook を足す／変える Issue では、受け入れ条件が [testing/policy.md](../../../docs/testing/policy.md) §8 の「出すもの」を要求しているかも点検対象に含める**（原因の 3 点・否定形の独立 run 数・ログのメタ行・変異 → red の証跡）。無ければ条件へ追記を提案する。
   - **助言でありゲートではない**。指摘の採否・受け入れ条件の修正可否は主エージェント＋ユーザーが判断する（§5.1）。**【通知】** 条件を書き換えるかを仰ぐときは通知を出す（[git-workflow.md](../../../docs/git-workflow.md) §5.8）。`evaluator`（step 7・実装の適合性を PR 前に評価）とは対象が逆である点に注意。
   - `refactor` / `docs` / `chore`（受け入れ条件を持たない作業）では省略してよい。条件を修正した場合は Issue 本文へ反映してから先へ進む。

4. **【確認ゲート】docs 先行**（step 4）
   - 設計を `docs/spec/` / `docs/arch/` に**先に**反映する（[docs-guide.md](../../../docs/docs-guide.md) §4 の更新先に従う）。
   - **タスクメモ `docs/task/<slug>.md` をここで作る**（[docs-guide.md](../../../docs/docs-guide.md) §3.2「タスクメモの見出し規約」「進捗欄と訂正ログ」の形）: 冒頭の引用ブロック（Issue・ステータス・ブランチ・基点。空行を挟まず連続させる）、`## 進捗` は**受け入れ条件ごとに `- [ ] Cn … — 証跡: 未`** の 1 行（段階を項目にしない）、空の `## 訂正ログ`（見出しと表ヘッダ）、`## 次にやること`（末尾に `訂正ログ: 0 件`）。同時に `docs/task/index.md` の `## タスク` 表へ `進行中` で載せ、「起票済み・未着手の Issue」表に同じ Issue の行があれば外す。以後 SessionStart hook がこのメモの申し送り・未完了項目を毎セッション注入する（git-workflow §5.6）。1 PR で完結する小タスクは archive に直接作ってよい（docs-guide §4.2 の特例）。
   - **これは判断であり skill は自動化しない**。設計内容は主エージェントが立案し、設計上の選択・トレードオフはユーザーに確認する（§5.1）。**【通知】** 設計の分岐を仰ぐときは通知を出す（[git-workflow.md](../../../docs/git-workflow.md) §5.8）。skill の役割は「実装より先に docs を固める」順序を守らせること。

4.5. **設計レビュー（`design-review` 起動・条件付き）**（step 4.5）
   - **発火可否は主観で決めない**。[CLAUDE.md](../../../CLAUDE.md) の「**設計レビュー（design-review）モード**」と investigate（step 3）の「設計レビュー推奨」から、**§5.2 / §5.5 の定義どおりに**判定する（モード表・トリガ・フォールバックの正本は git-workflow 側。ここでは再定義しない）。起動する場合は、docs に固めた設計案を `design-review` サブエージェント（Opus）で点検し、指摘・改善案を受け取る。
   - **助言でありゲートではない**。設計方針の最終決定は主エージェント＋ユーザー（§5.1）。推奨が `yes` のとき主エージェントは自己判断でスキップせず、省略する場合は**理由をユーザーに提示して承認を得る**（**【通知】** [git-workflow.md](../../../docs/git-workflow.md) §5.8）。ユーザーはオン / オフ両方向でオーバーライドできる。
   - 判定の結果「起動しない」となった場合は省略してよい。`criteria-review`（step 3.5・条件の妥当性）とは対象が異なり、設計案そのものを見る。

5. **【確認ゲート】テスト先行**（step 5）
   - 受け入れ条件・spec に基づいてテストを**先に**書く（実装に合わせて書かない。[テスト方針](../../../docs/testing/policy.md)）。
   - **テスト内容の決定は判断であり skill は自動化しない**。何を検証するかは主エージェント＋ユーザーが決める（**【通知】** [git-workflow.md](../../../docs/git-workflow.md) §5.8）。skill は「実装より先にテストを書く」順序を守らせること。

6. **実装 → green**（step 6）
   - 実装してテストを green にする。red 単独ではコミットせず、green にしてから 1 コミットにまとめる（§5.1）。
   - **自分で書くか `implementer` へ委譲するかを決める。** 委譲してよいのは**対象ファイルが列挙でき、判定・期待値が固まっている**場合だけ。委譲するなら [`implementer-brief-template.md`](implementer-brief-template.md) を `.brief/<slug>.md` へ複写して埋め、起動プロンプトにはパスと「読め・読み直せ」だけを書く。**取り決めと主エージェント側の義務（検証を自分で回し直す・行単位の突合・実際の例外で読む・境界をまたぐ引用を洗う・発火順序まで確かめる・commit は自分で）の正本は [git-workflow.md](../../../docs/git-workflow.md) §5.2「実装の委譲」**（ここには再掲しない）。

> **セッションの分割点**（git-workflow §5 の分割点 A / B）: 手順 4.5 の後（設計確定後）と手順 6 の後（`/verify-gate` の前）は新セッションに分けてよい。分ける前にタスクメモの「次にやること」を更新し、再開は SessionStart hook が注入した申し送りに従う。

> ここから先（PR 前の検証ゲート）は `/verify-gate`、マージ後は `/finish-task` に引き継ぐ。

## やらないこと

- **docs 設計・テスト内容の自動生成／判断の肩代わり**。step 4・5 は確認ゲートに留め、中身は主エージェント＋ユーザーが決める（§5.1/§5.2）。
- ルール（Issue テンプレ・ブランチ命名・更新先）の再定義。正本は git-workflow §3/§4/§5。
- 順序の省略。docs/テストを飛ばして実装に進まない。
- 設計外の問題の独断対応。出たらユーザーに対応案を提示して確認する（§5.1）。**【通知】** [git-workflow.md](../../../docs/git-workflow.md) §5.8。
