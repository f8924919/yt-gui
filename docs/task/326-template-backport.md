# claude-templates の更新（上流 #20〜#79）を逆輸入

対応 Issue: [#326](https://github.com/f8924919/yt-gui/issues/326)

> **PR を 4 本に分割して進める。** PR1〜PR3 の本文は `Refs #326` とし、Issue を閉じるのは最後の PR4 の `Closes #326` だけにする。途中の PR をマージしたあと `/finish-task` の B-2 に来ても、ここに書いた分割を理由に close しない。

## 背景

前回の取り込み（[#285](archive/285-template-backport.md)・#297、上流 `43374c0` = PR #19 まで）以降に、雛形 `claude-templates` へ PR #20〜#79 が入った。3 テーマ（hook・skill のコード／運用・docs・エージェント定義／scripts 群）を `investigate` で並列に突き合わせ、ユーザーと取り込み範囲を決めた。取り込まないものとその理由は Issue 本文の「取り込まないもの」節が正本。

## PR 分割

| PR | ブランチ | 内容 | 状態 |
|---|---|---|---|
| PR1 | `feature/326-safety-net` | SessionStart hook の見出し欠落通知・ネストしたリポジトリの除外・finish-task の Issue close 安全網 | 完了（#327） |
| PR2 | `feature/326-evaluation-discipline` | policy §8・evaluator 軸 5 / 6・指摘区分と止め時・§5.8 通知・限定句の伝播・rules/harness.md | 進行中 |
| PR3 | `feature/326-task-memo-lifecycle` | 進行中メモの申し送り注入・タスクメモの見出し規約・分割点・harness-retro | 未着手 |
| PR4 | `feature/326-implementer` | implementer エージェントとブリーフ・長いジョブの起こし方の規則（policy §8.3 C6 の注記「investigate だけ」も直す） | 未着手 |

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
- **止め時の規則の追加**（design-review H1・L4）: yt-gui には「変更集合と検証記録」の節が無いので、規則 3 に「`[欠陥]` を直したら verify を回し直してから再評価」、規則 4 に「`[証跡・文言]` の修正がコード・テストに及んだら verify を回し直す」、規則 5 に「要判断が残る巡はユーザーの決定待ちで止まる」を足した
- **`Follow-up: #` の確認**（design-review M3）: 上流の `grep -c 'Follow-up: #'` は、PR1 で直した `Closes #` と同じ誤検出の形。行頭に固定して抜き出し、起票した番号と突き合わせる形にした
- **§5.8 の後ろ盾**（design-review M5）: `PushNotification` が使えない・エラーの環境ではチャットの先頭行に同じ 1 行を書く。送るのは主エージェントだけ、`AskUserQuestion` の直前、権限の確認プロンプトは対象外
- **§5.8 の実送信の確認**: PR2 の evaluator 2 巡目で要判断が出て止まったとき、`AskUserQuestion` の直前に `PushNotification` を送った。結果は「Terminal notification sent. Mobile push requested.」（Remote Control 接続中のメインセッションで送れることを確認。2026-09-19）

## PR2 の評価ゲートの巡回

| 巡 | 区分 | 指摘 | 閉じ方の種別 | 証跡 |
|---|---|---|---|---|
| 1 | [欠陥] | 受け入れ条件 1 が挙げる fail-closed が policy §8 から理由の記録なしに落ちていた（`policy.md` A1・`harness.md` 規則 1） | 条件どおり読み替えて追加（変異の適用・テストの起動・収集の失敗を死亡と数えない）。「雛形との違い」注記にも記録 | `3f8e18d` |
| 1 | [証跡・文言] | 上流の事例 3 か所（`policy.md` §8.3 冒頭・`evaluator.md` 軸 6・`docs-check.md` 観点 9）に出典の限定句が無い | 「雛形 claude-templates の採用プロジェクトでの事例」を付けた | `3f8e18d` |
| 1 | [証跡・文言] | verify-gate 手順 5 と §5.8 の表に「要判断が残るとき止まる」（§5.2 規則 5）が無い | 両方に追加 | `3f8e18d` |
| 1 | 要判断 | hash が記録されていない証跡の区分（evaluator.md は [欠陥]、§5.2 の所在の原則では証跡・文言相当） | §5.2 の所在の原則に揃えた: ログがあり hash だけ無いなら同じ変異の再実行で閉じるので [証跡・文言]、ログ自体が無ければ [欠陥]。§5.2 の「古い」の定義にも追記。**当初は主エージェントが独断で決めていたが、2 巡目の指摘を受けてユーザーが承認した**（2026-09-19） | `3f8e18d` |
| 2 | [欠陥] | spec とコードの食い違いの扱いが §5.2 の欠陥の定義（欠陥）・規則 5（区分の外の要判断）・evaluator.md（要対応）で 3 通りに割れていた | **ユーザー判断**: 食い違いは常に [欠陥]。どちらを正とするかが決まらなければ要判断を論点として添え、決定待ちで止まる。§5.2 規則 5・evaluator.md 軸 3 / 制約 / 要判断・verify-gate 手順 5・§5.8 の表を揃えた | 本コミット |
| 2 | [証跡・文言] | 1 巡目の要判断がユーザーの決定の記録なしに閉じられていた | ユーザーの承認を記録し、証跡欄を `3f8e18d` に替えた | 本コミット |
| 2 | [証跡・文言] | hash の無い証跡の扱いが evaluator.md の区分の要約・軸 5 (b) のメタ行・§5.2 の表の鮮度の定義に届いていなかった | 3 か所を同じ所在の原則（ログがあり記録が欠けるなら再実行で閉じる = 証跡・文言）に揃えた | 本コミット |

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

## 検証ゲート

| PR | verify | docs-check | evaluator |
|---|---|---|---|
| PR1 | green（ruff check / format --check / mypy / pytest 584 passed。E501 の折り返しのみ修正） | 指摘なし | 1 巡目 PASS（要対応 0 件。参考の文言 2 点は反映済み。evaluator 自身も hook の複製へ 4 変異を入れて red を確認） |
