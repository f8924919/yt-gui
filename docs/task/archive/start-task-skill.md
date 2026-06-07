# start-task skill の新設（ワークフロー前半のオーケストレーション）

対応 Issue: [#105](https://github.com/f8924919/yt-gui/issues/105)

## 背景

Skills 層（#102 / PR #103）で後半（verify-gate / finish-task）は埋めたが、前半（git-workflow §5 step 1〜6）の入口 skill が無かった。`start-task` を新設し、3 skill（start → verify-gate → finish）でワークフロー全工程を挟む。

## 設計判断

- **最重要目的は「順序の強制」**: docs 先・テストファーストを順序ゲートで守らせ、実装先行（順序逆転）を防ぐ。memory の記録（過去に順序逆転の指摘あり）に直接効く。
- **判断ステップは自動化しない**: step 4（docs 設計）・step 5（テスト内容）は §5.1/§5.2 で主エージェント＋ユーザーが行う判断。skill は確認ゲートに留め、docs/テストを自動生成しない。これを「やらないこと」に明記。
- **ルールは再定義せず参照**: Issue テンプレ・ブランチ命名・更新先の正本は git-workflow §3/§4/§5（drift 防止、[[yt-gui-skill-layer-policy]] と同方針）。

## 変更内容

- `.claude/skills/start-task/SKILL.md`（新規）
- `docs/git-workflow.md` §5 冒頭に入口参照を追記、§5.3 の skill 表に `start-task` 行を追加

## メモ

- 本タスクの設計正本は開発ワークフロー定義（git-workflow.md）側のため、アプリ実装の spec/arch 更新は不要。
