# Skills 層の新設（検証ゲート / タスク完了処理）

対応 Issue: [#102](https://github.com/f8924919/yt-gui/issues/102)

## 背景

3分離パターンの層構造（CLAUDE.md → Skills → サブエージェント）のうち、サブエージェント層は揃っているが Skills 層がゼロだった。git-workflow §5 の定型オーケストレーションを skill 化し、再現性と効率を上げる。効果の高い 2 つから着手。

## 設計判断

- **skill は手順の入口に徹し、ルールを再定義しない**: 起動条件・モデル選定などの正本は git-workflow §5.2。skill にコピーすると drift するため参照に留める（[[yt-gui-evaluator-agent-policy]] と同じ単一情報源の方針）。
- **verify-gate**: ブランチ種別を判定し `verify`（常時）/ `docs-check`（docs 変更時）/ `evaluator`（feature/bugfix/hotfix・省略不可）を順に起動。evaluator の「裁量でスキップしない」を skill 手順として明文化。
- **finish-task**: main 最新化＋ブランチ削除＋archive 移動。archive 移動は main 直コミット禁止のため docs ブランチ＋PR で行う（今セッションの #101 の手順を踏襲）。

## 変更内容

- `.claude/skills/verify-gate/SKILL.md`（新規）
- `.claude/skills/finish-task/SKILL.md`（新規）
- `docs/git-workflow.md` §5 step 7 / step 9 に skill 参照を追記、§5.3「スキル（オーケストレーション入口）」を新設

## メモ

- skill のファイル形式は `.claude/skills/<name>/SKILL.md`、frontmatter は `name` ＋ `description`（既存 plugin skill で裏取り）。
- 本タスクの設計正本は開発ワークフロー定義（git-workflow.md）側のため、アプリ実装の spec/arch 更新は不要。
