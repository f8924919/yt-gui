# `.claude/rules/` ルール層の新設（path-scoped）

対応 Issue: [#125](https://github.com/f8924919/yt-gui/issues/125)

## 背景

Claude Code の `.claude/rules/` は `paths` frontmatter で「特定ファイル種別を編集する瞬間にだけ」ルールをコンテキストへ注入できる（path-scoped）。`paths` 無しは CLAUDE.md と同等の常時ロードになるため旨味は path-scoped 一択。過去の遵守ミス（テストファースト順序逆転 #75、docs の index/リンク漏れ＝`docs-check` agent の存在理由）に、編集時の再注入で補完を効かせる。

## 設計判断

- **薄いポインタに徹し正本は docs のまま**: ルール本文に手順をコピーすると単一情報源が崩れ drift する（skill 層・evaluator と同じ方針。git-workflow §5.2/§5.3）。各 rule は正本 docs を指し、外しやすい要点のみ再掲。
- **順序ゲートの補完**: path-scoped は「マッチするファイルを読んだ後」に発火するため新規領域では遅れることがある。`/start-task`・`/verify-gate` を代替せず補完として位置づける。
- **対象は path-scoped 一択**: git-workflow.md はプロセス（タスク境界で効く）でファイル種別に紐づかないため rules 化せず、現状の「CLAUDE.md 要約＋本体 on-demand」を維持。
- **テンプレ逆輸入はスコープ外**: `~/workspace/claude-templates` への backport は運用して効果を見てから別タスクで行う。

## 変更内容

- `.claude/rules/testing.md`（新規、`paths: tests/**, **/test_*.py` → 正本 testing/policy.md）
- `.claude/rules/docs-upkeep.md`（新規、`paths: docs/**/*.md` → 正本 docs-guide.md）
- `docs/git-workflow.md` §5.4「ルール層（path-scoped）」を新設
- `docs/task/index.md` に本タスクを追記

## メモ

- 設計正本は開発ワークフロー定義（git-workflow.md）側のため、アプリ実装の spec/arch 更新は不要（skill-layer #102 と同じ）。
- 効果検証後、テンプレートへ `docs-upkeep.md`（言語非依存）・`testing.md`（paths を kickoff で言語別に置換）を backport する別タスクを検討。
