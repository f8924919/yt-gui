# claude-templates の更新（上流 #20〜#79）を逆輸入

> Issue: [#326](https://github.com/f8924919/yt-gui/issues/326)
> **ステータス: 完了**（2026-09-19 着手・完了。PR1 #327・PR2 #328・PR3 #329・PR4 で完結）
> ブランチ: `feature/326-implementer`（PR4）
> 基点: `main` の `7ffb256`（PR3 マージ後）
> **PR を 4 本に分割して進める。** PR1〜PR3 の本文は `Refs #326` とし、Issue を閉じるのは最後の PR4 の `Closes #326` だけにする。途中の PR をマージしたあと `/finish-task` の B-2 に来ても、ここに書いた分割を理由に close しない。

## 進捗（受け入れ条件 = Issue #326 の PR1〜PR4 節）

- [x] C1 PR1 安全網（SessionStart hook の見出し欠落通知・ネストしたリポジトリの除外・finish-task の Issue close） — 証跡: PR #327・下の「検出器の有効性確認」M1〜M6
- [x] C2 PR2 評価ゲートの規律（policy §8・evaluator 軸 5 / 6・指摘区分と止め時・§5.8・harness.md） — 証跡: PR #328・下の「PR2 の評価ゲートの巡回」
- [x] C3 PR3 進行中メモの注入（hook・pytest・変異） — 証跡: `tests/test_session_task_status.py`・下の「検出器の有効性確認」PR3 の変異 22 件（`433b488`）
- [x] C4 PR3 タスクメモの見出し規約・進捗欄と訂正ログ・archive への直接作成の特例（docs-guide §3.2 / §4.2） — 証跡: `docs/docs-guide.md` §3.2・§4.2、CLAUDE.md タスク管理ルール（evaluator PR3 条件 2 ✅）
- [x] C5 PR3 分割点 A / B・訂正ログの止め規則・skill と rule の追従（git-workflow §5 / §5.2 / §5.6 / §5.8） — 証跡: `docs/git-workflow.md` §5・§5.2・§5.6・§5.8、start-task・finish-task・docs-upkeep（evaluator PR3 条件 3・4 ✅）
- [x] C6 PR3 harness-retro（skill・§5.9・記録ファイル） — 証跡: `.claude/skills/harness-retro/SKILL.md`・`docs/git-workflow.md` §5.9・`docs/harness-retro-log.md`（evaluator PR3 条件 6 ✅）
- [x] C7 PR4 implementer とブリーフ（§5.2「実装の委譲」） — 証跡: `.claude/agents/implementer.md`・`.claude/skills/start-task/implementer-brief-template.md`・`docs/git-workflow.md` §5.2「実装の委譲」（evaluator PR4 1 巡目の [欠陥]「戻す条件」を閉じた）
- [x] C8 PR4 エージェント名の列挙の追従・docs-check 観点 — 証跡: 下の「PR4 の列挙の追従」表・`.claude/agents/docs-check.md` 観点 10（evaluator PR4 条件 2 ✅）
- [x] C9 PR4 長いジョブの起こし方の規則 — 証跡: `docs/git-workflow.md` §5.1（evaluator PR4 条件 3 ✅）
- [x] verify-gate（PR3） — 証跡: 下の「検証ゲート」表の PR3 行

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|
| 2026-09-19 | PR1 の git-workflow §5 step 8 に、上流どおり `gh pr view --json body \| grep -c 'Closes #'` で `Closes #` の有無を機械確認できると書いた | 本文の説明に `Closes #` という語があるだけで当たる（#327 自身で 1 と数えた）。`closingIssuesReferences` を見る | 書いた確認コマンドを、書いた PR 自身に当てること（advisor の指摘で実施） |
| 2026-09-19 | PR2 の設計メモに「yt-gui の `scripts/` はビルド道具で、測定器ではない」と書いた | `scripts/download_binaries.py` の sha256 検証は、偽 PASS の害が最も大きい測定器 | design-review（M4） |
| 2026-09-19 | PR3 の設計メモに、上流スモークのケースを「14 件」と書いた | `CASES` は 13 件（数えずに転記した） | 書く前に一次資料を数える（policy §8.3 C6）。design-review（H1）が数え直して捕まえた |

## 次にやること（申し送り・2026-09-19 時点）

1. 本メモを archive へ移して PR4 を出す（`Closes #326`）。マージ後は `/finish-task`（B で #326 が自動 close されているかを確かめる）。
2. 新しいセッションで SessionStart hook がこのメモを注入するかを確かめる（PR3 マージ後の main で hook を直接実行し、引用ブロック・次にやること・未チェック項目が出ることは確認済み。新セッションでの実地確認は未）。

訂正ログ: 3 件（止まった: 2026-09-19 — 2 件目で止まり、ユーザー判断で遡及記載のまま続行。3 件目でも止まり、ユーザー判断で**以後は止めずに続ける**。理由: 3 件とも書いた直後にレビューで捕まった小さな転記・前提の誤りで、方針の見直しを要する型ではないため）
- 2 件目で読み直した結果: どちらも「書いた指示・前提を実物に当てていなかった」型で、設計の方針は変えない。書いた確認コマンドは書いた PR 自身に当て、前提の分類（測定器か否か）は design-review に回す。

## 背景

前回の取り込み（[#285](285-template-backport.md)・#297、上流 `43374c0` = PR #19 まで）以降に、雛形 `claude-templates` へ PR #20〜#79 が入った。3 テーマ（hook・skill のコード／運用・docs・エージェント定義／scripts 群）を `investigate` で並列に突き合わせ、ユーザーと取り込み範囲を決めた。取り込まないものとその理由は Issue 本文の「取り込まないもの」節が正本。

## PR 分割

| PR | ブランチ | 内容 | 状態 |
|---|---|---|---|
| PR1 | `feature/326-safety-net` | SessionStart hook の見出し欠落通知・ネストしたリポジトリの除外・finish-task の Issue close 安全網 | 完了（#327） |
| PR2 | `feature/326-evaluation-discipline` | policy §8・evaluator 軸 5 / 6・指摘区分と止め時・§5.8 通知・限定句の伝播・rules/harness.md | 完了（#328） |
| PR3 | `feature/326-task-memo-lifecycle` | 進行中メモの申し送り注入・タスクメモの見出し規約・分割点・harness-retro | 完了（#329） |
| PR4 | `feature/326-implementer` | implementer エージェントとブリーフ・長いジョブの起こし方の規則（policy §8.3 C6 の注記「investigate だけ」も直す） | 進行中 |

**順序の理由**: PR3 の「訂正ログの止め規則」と harness-retro は PR2 の §5.2 止め時・§5.8 通知を前提にする。#27（限定句）は当初 PR1 の予定だったが、evaluator 軸 5 と「指摘の区分」節を前提にしているため PR2 へ移した。

## 設計メモ

- **ネストしたリポジトリの除外が yt-gui で効く場面**: 上流の動機は「リポジトリ直下に上流の clone を置く構成」だが、yt-gui では、サブエージェントを worktree 隔離（`isolation: "worktree"`）で動かしたときにリポジトリ配下へ作られる worktree（`.git` がファイル）が該当する。本体が `main` のままでも、worktree 側の別ブランチでの編集を止めない。
- **`build_context()` の引数**: 上流は `build_context(index_text, base_dir)` だが、`base_dir` は進行中メモの読み込み（PR3）でだけ使う。PR1 では `build_context(index_text)` とし、PR3 で引数を足す。
- **finish-task B-2 の分割 PR 条項**: 上流の B-2 は「親 Issue として残す」の明示だけを見る。yt-gui は #285・本 Issue のように 1 Issue を複数 PR に分けるので、「PR を分割して進める旨の明示があり、残りの PR がある」も close しない理由に足した（本メモの冒頭の引用ブロックがその明示）。
- **step 8 の `Closes #` 確認は `closingIssuesReferences` で見る**: 上流は `gh pr view --json body | grep -c 'Closes #'` だが、PR1（#327）の本文は機能説明に `Closes #` という語を含むため 1 件と数えた（実際の紐付けは 0 件）。GitHub が紐付けた番号を直接出す形に替えた。
- **B-1 のコマンドは Bash ツールで実行する**: `${PRS%% *}` や `$(...)` は PowerShell では通らない。実在する PR で試走して確かめた（`feature/285-review-modes` → PR 289・#285、`chore/update-binary-pins` → 同名ブランチのマージ済み PR が 18 本あるため警告が出て、最新の PR 322 を採る）。

## PR2 の設計（上流からの読み替え）

- **policy §8 の項目番号は上流と揃える**（A1〜A10 / B1〜B4 / C1〜C6）。雛形との突き合わせを次回以降も楽にするため。中身は yt-gui の実態へ読み替える:
  - A1: 死因マッピングは「変異ごとに落ちたテスト名を表にする」（PR1 の表の形）。`selftest_all.py` の機械検査・`COVERAGE_EXEMPT` は持ち込まない
  - A6: 上流は「一括ランナーの登録簿に足す」。yt-gui では同じ失敗（足した検査が一度も走らない）が **pytest の収集規則から外れた名前**で起きるので、「`tests/test_*.py`・`test_` 関数の名前にし、足したテストが実行件数に出ていることを確かめる」に置き換える
  - A7: 無変異の状態で green を確かめてから壊す（PR1 で実施済みの手順）
  - A9: `mutation_engine.py` の例は落とし、原則だけ残す
  - A10: 成果物のハッシュ記録は yt-gui では誰も実行しない（pytest は成果物を読まない）ので、評価・測定の前後で `HEAD` と作業ツリーが同じかを見る形に置き換える（design-review M1）。`pgrep` / `pkill` の注記は外す
  - shell の既知の罠の注記: yt-gui の検査は Python（pytest）で、shell は CI の YAML 内に限られるので持ち込まない
  - C6 の注記: 「出所を添える」項目を持つ agent は、PR2 時点では investigate だけ。**PR4 で implementer を足したら、この注記（「investigate だけ」）は偽になるので必ず直す**。§5.2「実装の委譲」の義務との対比も PR4
- **§2.6**: 「追跡下のファイルを変異させない」は、yt-gui の既存の手順（green をコミットしてから手で壊し、`git checkout` で戻す）を否定しない。手で壊すのは今のまま、**自動化するならコピーを変異させる**、と書き分ける。red のログをタスクメモか PR に貼る規則は、そのまま足す
- **evaluator**: 軸 1・4 は yt-gui 固有の文言（yt-dlp 連携・Signal/Slot）のまま残し、軸 5・6、「指摘の区分」節、3 値の総合判定、件数行を足す。進め方の `change_set.py snapshot` は、yt-gui の `git diff main...HEAD` のまま
- **§5.2**: 「評価ゲートの指摘区分と止め時」を evaluator のモード節の後に足す。**CLAUDE.md の evaluator モード（`always`）は変えない**。止め時の規則は巡回の終わり方を決めるもので、起動可否とは別
- **§5.8 通知**: yt-gui の §5.6=hooks・§5.7=権限の次なので、番号は上流と同じ §5.8。該当箇所の表には start-task / verify-gate / finish-task の行と、共通行の「§5 step 8」だけを置く。harness-retro の行と「訂正ログの止め規則」は PR3 で足す
- **`rules/harness.md`**: 当初は `tests/**` と `.claude/hooks/**` だけの予定だったが、design-review（M4）の指摘を受け、ユーザー判断で**広く取る**ことにした。`scripts/download_binaries.py` の sha256 検証・`.github/workflows/` の CI ゲート・hook を登録する `.claude/settings.json` も、偽 PASS を出しうる測定器である。`tests/**` は既存の `testing.md` と重なるが、testing.md はテストファーストと red の単独コミット禁止、harness.md は検出器の検出力と役目が違うので、重なりは許す（差は「読み込まれる瞬間」だけ）
- **評価軸 5 の範囲**（ユーザー判断・design-review H2）: evaluator は `always` で、ほぼ全 feature / bugfix がテストを足すため、上流のままだと「変異 → red の証跡が無い」で毎回 `[欠陥]` になりうる。**テストファーストで実装前に red だった実行ログ（FAILED 行と実装前の HEAD）も証跡として認める**（policy §2.6・§8.1 A1）。回帰テスト・hook・判定ロジックは従来どおり「直してから戻して red を見る」
- **証跡の鮮度**（design-review M2）: 上流は `change_set.py` の fingerprint で「古い」を判定するが、yt-gui には無い。A1 の出すものに**壊す前（または実装前）のコミット hash** を必須にし、evaluator は `git log <hash>..HEAD -- <検出器のファイル>` で鮮度を判定する
- **止め時の規則の追加**（design-review H1・L4）: yt-gui には「変更集合と検証記録」の節が無いので、規則 3 に「`[欠陥]` を直したら verify を回し直してから再評価」、規則 4 に「`[証跡・文言]` の修正がコード・テストに及んだら verify を回し直す」、規則 5 に「要判断が残る巡はユーザーの決定待ちで止まる」を足した（当初の言い回し。2 巡目の指摘を受け、「要判断は区分の代わりではなく `[欠陥]` に添える論点で、要判断つきの `[欠陥]` が残る巡は止まる」に改めた）
- **`Follow-up: #` の確認**（design-review M3）: 上流の `grep -c 'Follow-up: #'` は、PR1 で直した `Closes #` と同じ誤検出の形。行頭に固定して抜き出し、起票した番号と突き合わせる形にした
- **§5.8 の後ろ盾**（design-review M5）: `PushNotification` が使えない・エラーの環境ではチャットの先頭行に同じ 1 行を書く。送るのは主エージェントだけ、`AskUserQuestion` の直前、権限の確認プロンプトは対象外
- **§5.8 の実送信の確認**: PR2 の evaluator 2 巡目で要判断が出て止まったとき、`AskUserQuestion` の直前に `PushNotification` を送った。結果は「Terminal notification sent. Mobile push requested.」（Remote Control 接続中のメインセッションで送れることを確認。2026-09-19）

## PR3 の設計（上流からの読み替え）

- **hook（進行中メモの注入）**: 上流 `session_task_status.py` の `build_context(index_text, base_dir)` と `_in_progress_blocks` / `_memo_lines` をそのまま移す（見出し語・上限の定数を含む）。yt-gui の差分は 2 点: テストは `TASK_INDEX_PATH` 環境変数ではなく既存どおり `TASK_INDEX` の差し替えと `build_context()` の直接呼び出しで行う／Python 3.10 未満のガードは入れない（3.14 固定）。PR1 で入れた片方欠落の 1 行に「`## タスク` が無いので進行中メモも注入できていない」を足す
- **テスト**: 上流 `scripts/smoke_session_status.py` のケース（`CASES` の C1〜C3・H1〜H3 の 13 件。当初「14 件」と書いたが数え直すと 13 件 — 訂正ログ 3 件目）を `tests/test_session_task_status.py` の pytest へ移す。変異（上流の 19 件と yt-gui で足した分岐）は、policy §2.6 の「自動化するならコピーを変異させる」に従い、**リポジトリの一部（hook・テスト・`docs/task/`）を一時ディレクトリへ複写して変異させ、そこで pytest を流す**使い捨てスクリプトで回す（スクリプトは scratchpad に置き、結果の表だけをここに貼る）。無変異の複写で green を先に確かめる（A7）
- **mypy の対象**: 現状は hook のうち `block_main_commit.py` だけが `[tool.mypy] files` に入っている。今回 hook のコードが大きく増えるので、`session_task_status.py` も入れる（ほかの hook は本 Issue の範囲外）
- **docs-guide §3.2**: タスクメモの見出し規約（引用ブロック・申し送り・進捗）と「進捗欄と訂正ログ」を上流どおり置く。§4.2 に「単一 PR で完結する小タスクの特例」（上流 #20）と archive 行のメトリクス句（上流 #26）。§2.1 に `harness-retro-log.md`
- **git-workflow**: §5 に分割点 A / B（yt-gui では hook の節は §5.6）、§5.2 に「訂正ログの止め規則」、§5.3 に harness-retro の行、§5.6 の hook 表の行を進行中メモの注入に更新、§5.8 の該当箇所表に harness-retro と共通の「訂正ログの止め規則」、§5.9 を新設
- **§5.9 の読み替え**: 「置き場所の選び方」の表の例を yt-gui の実物に置き換える（検査ランナーの行は pytest のテストに、「長いジョブの起こし方を hook にした」の例は雛形の採用プロジェクトの事例と明記）。記録ファイル `docs/harness-retro-log.md` は空の雛形で置く
- **start-task**: 上流 #26 の 3 点（手順 1 の「本文の鮮度」の確認・手順 4 でタスクメモを §3.2 の形で作る・分割点の注記）を移す。「本文の鮮度」は GraphQL で本文の編集時刻と前提 Issue の close 時刻を比べる 1 コマンドで、Issue #326 の PR3 条件の「start-task を追従させる」に含める
- **雛形からの意図的な差分**（design-review H2）: 上流の hook は `進行中` なのにリンクの無い行を黙って落とし、index が UTF-8 でないと例外で落ちる。前者は「リンクの無い進行中の行: <セル>」の 1 行を出し、後者は何も注入せず通すように直した（いずれもテストと変異つき）。注入文の末尾も、CLAUDE.md の「まず対応するかを尋ねる」に合わせて「続けると決まったら申し送りから再開する」に改めた（同 M2）
- **mypy の対象を `session_task_status.py` に限った理由**: 本 Issue で大きく書き換える hook だけを入れた。`block_main_edit.py`・`format_edited_file.py` は本 Issue の範囲外で、入れるなら別 Issue（follow-up 候補）
- **注入量の実測**（design-review M1）: 本メモ 1 件が進行中の状態で、注入文は 2,085 字・32 行（2026-09-19、`3cf90de`）。上限は上流どおり行数（メモごと 60 行・合計 200 行）のままにし、文字数の上限は足さない。1 行が長い日本語のメモでも 200 行に届く前に「次にやること」を短く保つ運用で足りる、という判断
- **訂正ログと評価ゲートの巡回表の境界**（design-review H3）: evaluator の指摘は巡回表が正本で、訂正ログには数えない（二重に止まらないように）。訂正ログに載せるのは、メモや PR に書いた主張が誤りだった件だけ。docs-guide §3.2 に明記した
- **本タスクメモ自身を新しい形に直す**（引用ブロック・`## 進捗` を受け入れ条件ごとに・`## 訂正ログ`・`## 次にやること`）。PR3 のマージ後、次のセッションで hook がこのメモの申し送りを注入することを実地の確認にする

## PR4 の設計（上流からの読み替え）

- **implementer（`.claude/agents/implementer.md`）**: 上流 #66 / #77 をほぼそのまま移す（Sonnet / `high`・書き込みが要るので `permissionMode: plan` は付けない・commit / push をしない約束は本文だけで担保）。外すもの: `change_set.py` の snapshot / compare（yt-gui に無い）、hook `check_long_job_command.py` / `block_running_script_edit.py` への言及（入れていない。長いジョブは git-workflow §5.1 の節を指すだけ）、「変異の死因とカバー」の機械書式（yt-gui は死因の表。policy §8.1 A1）。
- **ブリーフの雛形（`start-task/implementer-brief-template.md`）**: 上流どおり。fingerprint・hook の注記を外す。置き場は `.brief/`（`.gitignore` に足す。scratchpad はセッション固有で分割点の `/clear` で消えるので使わない）。
- **git-workflow §5.2「実装の委譲」**: いつ委譲するか / しないか・ブリーフの渡し方・主エージェントの義務 5 点を上流どおり置く（のちに yt-gui で義務 6 を足して 6 点。下の「雛形からの意図的な差分」）。義務 1 の「verify の報告は証跡として採ってよい」の根拠は、上流の fingerprint ではなく「verify は実装していない」ことだけにする。§5 step 6・§5.2 冒頭（実装は Sonnet）・委譲表・effort と `permissionMode` の段落（書き込みを行うのは verify / docs-check / implementer）・費用対効果の段落を追従させる。qemu-g5 の効果測定の注記は「雛形 claude-templates の採用プロジェクトでの 1 タスクの観測」と限定して残す
- **start-task 手順 6**: 自分で書くか implementer へ委譲するかの分岐を上流どおり足す
- **CLAUDE.md**: 上流と同じく「実装の委譲（implementer）」の 1 行を Git / GitHub 運用ルールの節に置く（モードなし）
- **列挙の追従（上流 D'）**: エージェント名を 3 つ以上並べている行を木全体から拾い（`docs/task/archive/` を除く）、1 行ずつ読んで implementer を足すか・足さない理由が文面から読めるかを判定する。件数は数えたコマンドと出力をこのメモに貼る（policy §8.3 C6）。docs-check に観点 10「エージェント / hook / skill を列挙している散文」を足す
- **policy §8.3 C6 の注記**: 「出所を添える」項目を持つ agent を investigate と implementer の 2 本にし、§5.2「実装の委譲」の義務 2・4 との違いの注記を足す（上流 #67 / #77）
- **長いジョブの起こし方**（当初は verify.md に置く案。design-review H3 とユーザー判断で正本を git-workflow §5.1 に移し、verify.md・implementer.md はそこを指す形にした）: hook は入れない（Issue の除外どおり）。上流 verify.md の節から hook への言及を外し、yt-gui の長いジョブ（PyInstaller のビルド・`scripts/download_binaries.py`・CI の待ち）を例にする。pytest 全体は 10 秒前後なので前景でよい、と実測を添える。報告フォーマットに「起こし方」の 1 行を足す（verify.md。PR4 の evaluator 2 巡目のユーザー判断で implementer.md にも足した）。verify.md・implementer は §5.1 を指す
- **permissions**: 上流は「implementer へ委譲するならテストの入口も allow に」と書く。yt-gui は `uv run pytest *` が既に allow にある（§5.7）ので追加なし — 着手時に settings.json で確かめる

### PR4 の列挙の追従（policy §8.3 C6 の数え方つき）

エージェント名を 3 つ以上並べている行を、implementer を足す前の木で数えた（`docs/task/archive/` と本メモを除く。名前が別々に 3 つ以上ある行。`verify` は `verify-gate` にも当たるので多めに拾う側）:

```bash
git grep -n -E 'investigate|criteria-review|design-review|evaluator|verify|docs-check|implementer' \
  -- . ':!docs/task/archive/' ':!docs/task/326-template-backport.md' |
  awk -F: '{line=$0; sub(/^[^:]*:[^:]*:/, "", line); n=0;
    split("investigate criteria-review design-review evaluator verify docs-check", a, " ");
    for (i in a) if (index(line, a[i])) n++; if (n>=3) print $1":"$2}'
→ 14 行（2026-09-19、PR3 マージ後の main = 7ffb256 の木）
```

| 箇所 | 判定 |
|---|---|
| `.claude/agents/evaluator.md:13`・`.claude/agents/design-review.md:13`（Opus にする理由の「Sonnet 勢」の列挙） | **更新**（`implementer` も Sonnet で、結果を主エージェントが検証する側。上流は据え置いたが、§5.2 冒頭の「実装は Sonnet」と揃える） |
| `.claude/skills/start-task/SKILL.md:3`（description） | **更新**（実装の分岐） |
| `docs/git-workflow.md:210`（§5.3 の start-task 行） | **更新**（実装の分岐） |
| `docs/git-workflow.md:119`（読み取り専任の 4 本） | **更新**（`implementer` は書き込みが要るため対象外、と明記） |
| `docs/testing/policy.md:252`（C6 の適用範囲） | **更新**（「出所を添える」項目を持つのは investigate と implementer の 2 本） |
| `docs/git-workflow.md:85`（step 4.5） | 据え置き（実装前レビューの説明） |
| `docs/git-workflow.md:117`（effort を固定する理由） | 据え置き（「特に」「逆に」で 2 例を挙げる文で、全エージェントの名簿ではない） |
| `docs/git-workflow.md:156`（「巡」の定義） | 据え置き（評価ゲートの構成の話で、implementer は登場しない） |
| `docs/git-workflow.md:211`・`:344`、`.claude/skills/verify-gate/SKILL.md:3`・`:41` | 据え置き（PR 前ゲートの構成は `verify` → `docs-check` → `evaluator` で、implementer は step 6 の側） |
| `docs/testing/policy.md:218`（A10 の例） | 据え置き（docs-check と evaluator の干渉の例示で、名簿ではない） |

表のほかに、委譲表（§5.2）に implementer の行を足し、「費用対効果」の段落に「小さい実装は implementer を介さず自分で書く」を足した（どちらも 3 つ以上並べる行ではないので上の 14 行には入らない）。

- **雛形からの意図的な差分**: 主エージェントの義務に 6「commit / push は主エージェントが行い、委譲時の HEAD と委譲後の HEAD・`origin/<branch>` を比べる」を足した。implementer の「commit しない」は本文の約束だけで、implementer は feature ブランチで動くので main 保護 hook の対象でもない（当初「main 保護 hook の不発火があるから」と書いたが、feature ブランチには無関係で根拠がずれていた — design-review H2 の指摘）。実際の歯止めは §5.7 の都度確認だけで、親の権限モードによっては効かない。
- **design-review（PR4）の反映とユーザー判断**: 長いジョブの規則の正本を git-workflow §5.1 に移した（長いジョブを起こすのは主に主エージェントで、verify は起こさない。ユーザー判断）。変異 → red の確認は主エージェントに固定し、implementer には作業ツリーを戻す git 操作を禁じた（ユーザー判断）。メトリクス句の evaluator 巡数は PR ごとに並べる（ユーザー判断）。「Sonnet 勢」への implementer の追加は維持し、役割語で書かれた git-workflow の同じ主張（「…受け入れ条件レビュー・実装が結果を客観的に検証できる」）も揃えた（ユーザー判断）。ほか: `download_binaries.py --yes`（GPL 同意の入力待ちを避ける）、implementer に「テストを弱めない」と「同じ木で動かす（worktree 隔離では起動しない）」、義務 1 の理由を「verify-gate の verify は最後の変更の後に走るゲート」に、C6 の注記を implementer の実際の報告項目に合わせた、docs-check 観点 10 に役割語・数の言い方の列挙を足した。PowerShell ツールにも `run_in_background` があることはツール定義で確かめた

## PR2 の評価ゲートの巡回

| 巡 | 区分 | 指摘 | 閉じ方の種別 | 証跡 |
|---|---|---|---|---|
| 1 | [欠陥] | 受け入れ条件 1 が挙げる fail-closed が policy §8 から理由の記録なしに落ちていた（`policy.md` A1・`harness.md` 規則 1） | 条件どおり読み替えて追加（変異の適用・テストの起動・収集の失敗を死亡と数えない）。「雛形との違い」注記にも記録 | `3f8e18d` |
| 1 | [証跡・文言] | 上流の事例 3 か所（`policy.md` §8.3 冒頭・`evaluator.md` 軸 6・`docs-check.md` 観点 9）に出典の限定句が無い | 「雛形 claude-templates の採用プロジェクトでの事例」を付けた | `3f8e18d` |
| 1 | [証跡・文言] | verify-gate 手順 5 と §5.8 の表に「要判断が残るとき止まる」（§5.2 規則 5）が無い | 両方に追加 | `3f8e18d` |
| 1 | 要判断（当時の報告の区分。現行の規則 5 では要判断は区分ではなく `[欠陥]` に添える論点） | hash が記録されていない証跡の区分（evaluator.md は [欠陥]、§5.2 の所在の原則では証跡・文言相当） | §5.2 の所在の原則に揃えた: ログがあり hash だけ無いなら同じ変異の再実行で閉じるので [証跡・文言]、ログ自体が無ければ [欠陥]。§5.2 の「古い」の定義にも追記。**当初は主エージェントが独断で決めていたが、2 巡目の指摘を受けてユーザーが承認した**（2026-09-19） | `3f8e18d` |
| 2 | [欠陥] | spec とコードの食い違いの扱いが §5.2 の欠陥の定義（欠陥）・規則 5（区分の外の要判断）・evaluator.md（要対応）で 3 通りに割れていた | **ユーザー判断**: 食い違いは常に [欠陥]。どちらを正とするかが決まらなければ要判断を論点として添え、決定待ちで止まる。§5.2 規則 5・evaluator.md 軸 3 / 制約 / 要判断・verify-gate 手順 5・§5.8 の表を揃えた | `88dd7e1` |
| 2 | [証跡・文言] | 1 巡目の要判断がユーザーの決定の記録なしに閉じられていた | ユーザーの承認を記録し、証跡欄を `3f8e18d` に替えた | `88dd7e1` |
| 2 | [証跡・文言] | hash の無い証跡の扱いが evaluator.md の区分の要約・軸 5 (b) のメタ行・§5.2 の表の鮮度の定義に届いていなかった | 3 か所を同じ所在の原則（ログがあり記録が欠けるなら再実行で閉じる = 証跡・文言）に揃えた | `88dd7e1` |
| 3 | [欠陥] | evaluator.md 軸 5 の区分の書き出し（「証跡やメタ行が無いは [欠陥]」）が、同じ段の hash・メタ行の扱い（証跡・文言）と §5.2 に矛盾していた | 書き出しを「ログ自体が無いは [欠陥]、あるが古い（hash・メタ行が無い場合を含む）は [証跡・文言]」に替えた | `46df91b` |
| 3 | [証跡・文言] | タスクメモに、要判断を区分として扱う古い用法（巡回表の区分列・設計メモの規則 5 の言い回し）が残っていた | 当時の用法である旨を注記した | `46df91b` |
| 3 | [証跡・文言] | evaluator.md の制約だけ、要判断を書く条件（どちらを正とするかが決まらないとき）が無条件になっていた | 条件を入れて軸 3・§5.2 規則 5 と揃えた | `46df91b` |
| 4 | [証跡・文言] | 巡回表が 2 巡目と 3 巡目の行の間の空行で途切れ、3 巡目の行が表として表示されない | 空行を消し、3 巡目の証跡欄を `46df91b` に替えた（あわせて参考指摘の軸 5 (b) の適用範囲を明確化） | `8d446ab` |

4 巡目の総合判定は **PASS（follow-up あり）**（[欠陥] 0 件 / [証跡・文言] 1 件）。残った 1 件はこの PR で直したので follow-up Issue は作らない。§5.2 規則 2 により再評価は行わない。

## PR4 の評価ゲートの巡回

| 巡 | 区分 | 指摘 | 閉じ方の種別 | 証跡 |
|---|---|---|---|---|
| 1 | [欠陥] | Issue が挙げるブリーフの書式のうち「戻す条件」の節が雛形に無い | コード（雛形）修正: 「手を止めて戻す条件」節を足し、§5.2 のブリーフの渡し方にも 1 行 | `8d446ab` |
| 1 | [証跡・文言] | git-workflow の方向語 2 件（「上の費用対効果」「下記『実装の委譲』」）が逆 | 文言修正 | `8d446ab` |
| 1 | [証跡・文言] | タスクメモが diff より古い（C7〜C9 が未チェック・次にやることが済んだ項目・「implementer は verify.md の節を指す」） | 文言修正 | `8d446ab` |
| 1 | [証跡・文言] | 義務の要約が CLAUDE.md と start-task で食い違う・委譲表の「受け取るもの」に数の出所が無い | 文言修正（両方に「変異 → red は自分で」、表に「数の出所」） | `8d446ab` |
| 2 | [欠陥] | §5.1 の「サブエージェントの報告に起こし方を 1 行」に implementer の報告フォーマットが従っていない（4176ca5 で §5.1 へ移して主語が一般化された時に取り残された）。要判断つき | **ユーザー判断**: implementer に欄を足す。報告フォーマット・委譲表の「受け取るもの」・§5.1 の文に implementer を入れた | `2172d1d` |
| 2 | [証跡・文言] | タスクメモの PR4 設計の implementer 行に「長いジョブは verify.md の節を指すだけ」が残っていた・巡回表の証跡欄が「本コミット」のまま | 文言修正・証跡欄を `8d446ab` に | `2172d1d` |

| 3 | [証跡・文言] | 巡回表の 1 巡目と 2 巡目の間の空行で表が切れていた・2 巡目の証跡欄が「本コミット」のまま・委譲表の verify 行に「起こし方」が無い | 空行を消す・証跡欄を `2172d1d` に・verify 行に「起こし方」を足し、§5.1 の主語を「コマンドを走らせるサブエージェント（verify・implementer）」に絞った | 本コミット |

3 巡目の総合判定は **PASS（follow-up あり）**（[欠陥] 0 件 / [証跡・文言] 3 件）。3 件はこの PR で直したので follow-up Issue は作らない。§5.2 規則 2 により再評価は行わない。

1 巡目の参考指摘（`--yes` が無いときは止まり続けるとは限らず、stdin が閉じていれば黙って終わる）も §5.1 の文言に反映した。

## 検出器の有効性確認（policy §2.6）

PR1 の hook 変更は、green の状態をコミット（`e79122d`）してから判定を 1 か所ずつ壊し、`tests/test_session_task_status.py` と `tests/test_block_main_edit.py` を流した。各変異のあとは `git checkout -- <file>` で戻した。

| 変異 | 対象 | 落ちたテスト |
|---|---|---|
| M1 ネスト判定を `main()` の条件から外す | `block_main_edit.py` | `test_allows_edit_in_nested_repo_on_main`（1 failed, 38 passed） |
| M2 ルートに達しても探索を止めない | `block_main_edit.py` | `test_in_nested_repo_false_for_plain_subdir` / `_for_root_file` ほか main 上の deny 3 件（5 failed） |
| M3 `.git` の有無を見ない | `block_main_edit.py` | `test_in_nested_repo_detects_git_dir` / `_git_file` / `test_allows_edit_in_nested_repo_on_main`（3 failed） |
| M4 両方欠落のとき空文字を返す | `session_task_status.py` | `test_reports_when_no_heading_matches` / `test_build_context_reports_no_h2_at_all`（2 failed） |
| M5 片方欠落の通知を出さない | `session_task_status.py` | `test_build_context_reports_missing_issue_heading` / `_task_heading`（2 failed） |
| M6 実際の見出しの一覧を空にする | `session_task_status.py` | `test_reports_when_no_heading_matches` / `test_build_context_reports_missing_issue_heading`（2 failed） |

### PR3（進行中メモの注入）

- **テストファーストの red**: 実装前の HEAD `a2230f9` で、追加したテストを流して 18 failed / 12 passed（`build_context()` の新しい引数と注入が無いため。既存の見出し欠落のテスト 4 件も新しい呼び出し形で落ちた）。
- **変異（1 回目・`91f6dfe`）**: green をコミットした後、hook・テスト・`docs/task/` を一時ディレクトリへ複写し、複写側の hook を 1 か所ずつ壊して pytest を流した（policy §2.6「自動化するならコピーを変異させる」。ランナーは scratchpad の使い捨て）。上流の 19 件のうち 18 件（「両方無いときも表の組み立てへ進む」を移し漏らした）と、yt-gui で足した「リポジトリルート基準」の 1 件で 19 件、撃墜 19 / 19。
- **ランナー自身の不具合**: 1 回目の最初の実行は pytest に `-rN`（要約なし）を渡していたため FAILED 行を拾えず、「死因なし・0 / 19」と出た。件数（`12 failed` 等）は出ていたので、死因の表を件数と突き合わせて気づいた（policy §8.1 A1 の「件数だけで満足しない」がそのまま効いた）。
- **テストファーストの red（2 回目）**: design-review H2 の 2 分岐（リンクの無い進行中の行・UTF-8 でない index）のテストを足し、実装前の HEAD `d64f088` で 2 failed / 30 passed。
- **変異（最新・`433b488`）**: ランナーに design-review H1 の安全策を入れた（複写元は `git archive HEAD`・変異ごとに新しいディレクトリ・`PYTHONDONTWRITEBYTECODE=1`・死亡は exit 1 だけ・収集件数が対照と一致しなければハーネスの失敗）。対照 32 passed。**撃墜 22 / 22**、原本は無傷。上流の 19 件（evaluator の指摘で移し漏れの 1 件を足した）＋ yt-gui で足した分岐の 3 件（リンクの無い進行中の行・UTF-8 でない index・リポジトリルート基準）。途中、ruff format が `except (A, B):` を Python 3.14 の `except A, B:` に直していたため置換対象が 0 回になり、fail-closed でハーネスが止まった（置換対象を直して再実行）。死因は次のとおり（`433b488` での実行）。

| 変異 | failed 数 | 落ちたテスト（死因） |
|---|---|---|
| 進行中の判定を潰す | 14 | C1-in-progress-one・C1-in-progress-two-heading-variants・C1-not-started-is-not-opened・C2-per-memo-limit・C2-total-limit・C2-within-limit-not-cut・C3-all-checked・C3-in-progress-row-without-link・C3-memo-missing・C3-no-checkbox-table-form・C3-old-format-no-sections・H2-no-issue-heading・test_main_injects_in_progress_memo_next_to_index・test_repository_task_index_is_parsable |
| 未着手も開く | 1 | C1-not-started-is-not-opened |
| 「申し送り」を語から外す | 1 | C3-no-checkbox-table-form |
| 「進捗」を前方一致から完全一致へ | 1 | C1-in-progress-two-heading-variants |
| 未チェックの印を [x] に | 7 | C1-in-progress-one・C1-in-progress-two-heading-variants・C2-per-memo-limit・C2-total-limit・C2-within-limit-not-cut・C3-all-checked・test_main_injects_in_progress_memo_next_to_index |
| 入れ子の未チェックを見ない | 1 | C1-in-progress-one |
| 引用ブロックを出さない | 2 | C1-in-progress-one・C1-in-progress-two-heading-variants |
| メモごとの上限を外す | 1 | C2-per-memo-limit |
| 合計の上限を外す | 1 | C2-total-limit |
| 合計上限の後のメモを黙って落とす | 1 | C2-total-limit |
| メモ欠落を黙って飛ばす | 1 | C3-memo-missing |
| 「チェック項目が無い」と「未チェック項目なし」を同じ文にする | 1 | C3-no-checkbox-table-form |
| 節が無いときの 1 行を出さない | 1 | C3-old-format-no-sections |
| 「訂正ログ」を申し送りの語に足す | 1 | C1-in-progress-one |
| 片方の見出しの欠落を知らせない | 4 | H1-no-task-heading・H2-no-issue-heading・test_build_context_reports_missing_issue_heading・test_build_context_reports_missing_task_heading |
| 両方あっても欠落を知らせる | 7 | test_build_context_has_no_missing_note_when_both_present・C1-in-progress-one・H1-no-task-heading・H2-no-issue-heading・test_build_context_reports_missing_issue_heading・test_build_context_reports_missing_task_heading・test_repository_task_index_is_parsable |
| ## タスク が無いときに進行中メモに触れない | 1 | H1-no-task-heading |
| 実際の見出しを出さない | 3 | H1-no-task-heading・H2-no-issue-heading・test_build_context_reports_missing_issue_heading |
| 両方無いときも表の組み立てへ進む | 3 | H3-no-both-headings・test_build_context_reports_no_h2_at_all・test_reports_when_no_heading_matches |
| リンクの無い進行中の行を黙って落とす | 1 | C3-in-progress-row-without-link |
| UTF-8 でない index で落ちる | 1 | test_fails_open_when_index_is_not_utf8 |
| メモを index の親ではなくリポジトリルート基準で解決する | 2 | test_main_injects_in_progress_memo_next_to_index・test_repository_task_index_is_parsable |

## 検証ゲート

| PR | verify | docs-check | evaluator |
|---|---|---|---|
| PR1 | green（ruff check / format --check / mypy / pytest 584 passed。E501 の折り返しのみ修正） | 指摘なし | 1 巡目 PASS（要対応 0 件。参考の文言 2 点は反映済み。evaluator 自身も hook の複製へ 4 変異を入れて red を確認） |
| PR2 | green（コード変更なし。巡ごとに回し直し、pytest 584 passed） | 自動修正 1 件は重複のため戻した。§8.3 C6 の出典の限定句を追加 | 4 巡で PASS（follow-up あり）。1〜3 巡目は FAIL（各 [欠陥] 1 件）。経緯は「PR2 の評価ゲートの巡回」 |
| PR3 | green（ruff check / format --check / mypy 59 files / pytest 600 passed） | 不整合なし（CLAUDE.md のドキュメントマップに記録ファイルは載せない判断。arch の関連仕様行の欠落は既存で範囲外） | 1 巡目 PASS（follow-up あり）: [欠陥] 0 件 / [証跡・文言] 5 件（死因表が古い・上流の変異 1 件の移し漏れ・finish-task C-4 の文の吸い込み・§5.3 の start-task 行・次にやることが古い）をこの PR で直した。規則 2 により再評価なし |
| PR4 | green（コード変更なし。巡ごとに回し直し、pytest 600 passed） | 列挙の追従（観点 10）で漏れなし。タスクメモの「義務 5 点」を補った | 3 巡で PASS（follow-up あり）。1・2 巡目は FAIL（各 [欠陥] 1 件: ブリーフの戻す条件・implementer の起こし方の欄。2 巡目は要判断つきでユーザー判断）。経緯は「PR4 の評価ゲートの巡回」 |
