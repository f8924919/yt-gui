# claude-templates の改良を逆輸入

対応 Issue: [#285](https://github.com/f8924919/yt-gui/issues/285)

## 背景

`.claude/` + `docs/` のハーネスは汎用雛形 `claude-templates` の元ネタになっている。雛形側の改良のうち、yt-gui 固有の事情に依存せず価値があるものを取り込む。雛形との全ファイル突き合わせの結果、差分の大半は汎用化（プレースホルダ化・kickoff 機構・yt-gui 固有記述の抽象化）で輸入対象外だった。

**輸入しないと判断したもの**（確認済み）:

- `.claude/kickoff.md`・各種プレースホルダ・GitHub 以外のホストへの読み替え注記 → 雛形専用
- `docs/ci-guide.md`・`docs/research/README.md` → yt-gui は [build.md](../build.md)・[research/index.md](../research/index.md) に同等以上の記述あり（「リリース後の実資産スモーク」も既存）
- 失敗クラスの知見（外部 API 契約・自己修復不能・権限差、investigate の WebSearch 付与、[testing/policy.md](../testing/policy.md) §7）→ **yt-gui が起源**で反映済み
- `except (A, B)` の括弧化 → yt-gui は Python 3.14 固定で PEP 758 により現行表記のまま有効。移植性目的の変更なので不要

## PR 分割

| PR | ブランチ | 内容 | 状態 |
|---|---|---|---|
| PR1 | `feature/285-hooks-layer` | hooks 層（SessionStart 注入・main 編集ブロック・編集後整形）＋ブランチ削除の除外＋git-workflow §5.6 | 進行中 |
| PR2 | `chore/285-permissions-and-effort` | `permissions` の allow/deny・エージェントの `effort` / `permissionMode` 固定・skill frontmatter＋§5.2 拡充・§5.7 新設 | 未着手 |
| PR3 | `docs/285-review-modes` | evaluator / design-review のモード制（現状維持の値で明示） | 未着手 |

## 設計メモ

- **§5.6 / §5.7 の番号**: 雛形は §5.6=権限・§5.7=hooks だが、yt-gui では PR1（hooks）を先に入れるため **§5.6=hooks・§5.7=権限** とする。各コミット時点で節番号が連続する方を優先した。
- **`block_main_edit.py` を別 hook にする理由**: commit をブロックしても編集は素通りするため、ブランチ切り忘れに気付くのが commit 直前になる。編集時点で止めれば `git stash` 等の巻き戻しが不要になる。
- **`format_edited_file.py` の対象範囲**: 雛形は 1 ディレクトリ限定だが、yt-gui は ruff の対象がリポジトリ全体のため `TARGET_DIRS = ("yt_gui", "tests")` の複数対応に小改造した。`scripts/` や `docs/` 配下は verify ゲートに委ねる。
- **hook のテスト方式**: ブランチ判定・リポジトリ所属判定は `repo_root` を引数に取るヘルパへ切り出し、一時 git リポジトリで直接検証する。`main()` 全体は `REPO_ROOT` / `TASK_INDEX` を差し替えて確認する（hook が対象とするリポジトリはファイル位置で固定のため、subprocess 実行だけでは deny 経路を再現できない）。
- **`docs/task/index.md` の再編**: SessionStart hook は `## タスク` / `## 起票済み・未着手の Issue` を抽出キーにする。完了タスクの経緯・申し送りは [archive/index.md](archive/index.md) の「完了タスクの経緯・申し送り」へ移した。

## PR1 のレビュー反映（evaluator）

- **NotebookEdit がブロックされていなかった**（決定打）: `NotebookEdit` の入力キーは `file_path` ではなく `notebook_path`。matcher に登録済みでも hook が対象パスを取れず素通りしていた。`_edited_path()` で両キーを見るよう修正し、テストを追加。
- **混在 refspec の擦り抜け**: `git push origin main :old` が削除扱いで通っていた。refspec が**すべて** `:` 形のときだけ削除とみなすよう厳密化。
- **非 dict の JSON 入力**でトレースバック＋exit 1 になっていた（Claude Code は非ブロッキング扱いだが stderr が汚れる）。4 hook すべてに `isinstance(..., dict)` ガードを追加。
- **docs 不整合**: `finish-task` skill が旧テーブル名「進行中・未着手」を参照、`rules/docs-upkeep.md` の凡例に「完了」が残存。いずれも修正。

## 検証メモ

- PowerShell のパイプ（`'...' | uv run python hook.py`）は stdin に UTF-8 BOM を付けるため、hook が JSON パースに失敗して**フェイルオープンする**（＝何も起きないので成功と見分けがつかない）。手動スモーク時は BOM なしのファイルを `cmd /c "... < payload.json"` でリダイレクトすること。Claude Code 本体は BOM を付けないため実運用には影響しない。
- hooks の登録（settings.json）はセッション開始時に読み込まれるため、実効確認は**新しいセッション**で行う。
