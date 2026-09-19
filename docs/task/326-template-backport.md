# claude-templates の更新（上流 #20〜#79）を逆輸入

対応 Issue: [#326](https://github.com/f8924919/yt-gui/issues/326)

> **PR を 4 本に分割して進める。** PR1〜PR3 の本文は `Refs #326` とし、Issue を閉じるのは最後の PR4 の `Closes #326` だけにする。途中の PR をマージしたあと `/finish-task` の B-2 に来ても、ここに書いた分割を理由に close しない。

## 背景

前回の取り込み（[#285](archive/285-template-backport.md)・#297、上流 `43374c0` = PR #19 まで）以降に、雛形 `claude-templates` へ PR #20〜#79 が入った。3 テーマ（hook・skill のコード／運用・docs・エージェント定義／scripts 群）を `investigate` で並列に突き合わせ、ユーザーと取り込み範囲を決めた。取り込まないものとその理由は Issue 本文の「取り込まないもの」節が正本。

## PR 分割

| PR | ブランチ | 内容 | 状態 |
|---|---|---|---|
| PR1 | `feature/326-safety-net` | SessionStart hook の見出し欠落通知・ネストしたリポジトリの除外・finish-task の Issue close 安全網 | 進行中 |
| PR2 | `feature/326-evaluation-discipline` | policy §8・evaluator 軸 5 / 6・指摘区分と止め時・§5.8 通知・限定句の伝播・rules/harness.md | 未着手 |
| PR3 | `feature/326-task-memo-lifecycle` | 進行中メモの申し送り注入・タスクメモの見出し規約・分割点・harness-retro | 未着手 |
| PR4 | `feature/326-implementer` | implementer エージェントとブリーフ・長いジョブの起こし方の規則 | 未着手 |

**順序の理由**: PR3 の「訂正ログの止め規則」と harness-retro は PR2 の §5.2 止め時・§5.8 通知を前提にする。#27（限定句）は当初 PR1 の予定だったが、evaluator 軸 5 と「指摘の区分」節を前提にしているため PR2 へ移した。

## 設計メモ

- **ネストしたリポジトリの除外が yt-gui で効く場面**: 上流の動機は「リポジトリ直下に上流の clone を置く構成」だが、yt-gui では、サブエージェントを worktree 隔離（`isolation: "worktree"`）で動かしたときにリポジトリ配下へ作られる worktree（`.git` がファイル）が該当する。本体が `main` のままでも、worktree 側の別ブランチでの編集を止めない。
- **`build_context()` の引数**: 上流は `build_context(index_text, base_dir)` だが、`base_dir` は進行中メモの読み込み（PR3）でだけ使う。PR1 では `build_context(index_text)` とし、PR3 で引数を足す。
- **finish-task B-2 の分割 PR 条項**: 上流の B-2 は「親 Issue として残す」の明示だけを見る。yt-gui は #285・本 Issue のように 1 Issue を複数 PR に分けるので、「PR を分割して進める旨の明示があり、残りの PR がある」も close しない理由に足した（本メモの冒頭の引用ブロックがその明示）。
- **B-1 のコマンドは Bash ツールで実行する**: `${PRS%% *}` や `$(...)` は PowerShell では通らない。実在する PR で試走して確かめた（`feature/285-review-modes` → PR 289・#285、`chore/update-binary-pins` → 同名ブランチのマージ済み PR が 18 本あるため警告が出て、最新の PR 322 を採る）。

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
