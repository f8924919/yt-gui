# 設計レビュー機構の導入: design-review エージェント新設とトリガ発火条件

- Issue: [#194](https://github.com/f8924919/yt-gui/issues/194)
- ブランチ: `feature/194-design-review-agent`
- ステータス: 進行中
- 更新日: 2026-07-04

## 目的

[#191](https://github.com/f8924919/yt-gui/issues/191) の `criteria-review`（受け入れ条件の妥当性・step 3.5）に続き、**設計そのものの妥当性**を実装前に点検する手順を追加する。全タスク常時実行はノイズ・コスト過剰、主エージェントの主観スキップは `evaluator` 必須化と同じ自己評価バイアスに陥る。よって **①発火は客観トリガで機械的に判定**（investigate の副産物として推奨を出す）、**②発火時のレビューは独立 `design-review`（Opus）** が docs 化された設計を点検する助言、とする。

## 設計メモ（investigate #194 の裏取り）

- **配置**: 発火判定は investigate（step 3）、実際のレビューは docs 先行（step 4）の後・テスト先行（step 5）の前 ＝ **step 4.5**（レビュー対象＝docs に固めた具体的な設計）。step 番号は renumber せず 4.5 挿入（`.claude/skills/start-task/SKILL.md:34-40` の間）。
- **モデル**: Opus。理由は evaluator と同じ〈生成者＝Opus 主エージェントの成果物を弱い評価者が追認する〉に加え〈設計批評自体が高裁量〉（`docs/git-workflow.md` §5.2）。
- **性格**: 助言（非ゲート）。ただし推奨 yes 時の主観スキップは禁止し、省略には**ユーザー承認**を要する（反バイアス）。
- **§5.5 新設**: git-workflow §5.4（ルール層）末尾の後に発火条件節を追加。

## criteria-review（step 3.5）初運用の指摘反映

本タスクは criteria-review を初めて実運用し、受け入れ条件を強化した:

- 「提示」→「**承認を得る**」に拘束を強化（条件5・7、反バイアスの核心）。
- Opus 理由を evaluator の丸写しでなく**2 点（追認リスク＋設計批評の高裁量）**で具体化（条件3）。
- `evaluator.md:11` / `git-workflow.md` の「evaluator のみ Opus」記述の**更新漏れ**を条件に追加（条件8・9）。
- `design-review.md` に**起動タイミング（step 4.5）**を明記（条件4）。

## 変更対象

| ファイル | 変更 |
|---|---|
| `.claude/agents/design-review.md` | 新規（Opus・read-only・助言・5 軸） |
| `.claude/agents/investigate.md` | 報告フォーマットに「設計レビュー推奨」追加 |
| `.claude/agents/evaluator.md` | Opus 自己説明を design-review 併記へ更新 |
| `.claude/skills/start-task/SKILL.md` | step 4.5 追加・フロントマター説明更新 |
| `docs/git-workflow.md` | §5 step 一覧に 4.5・§5.2 表と Opus 記述 2 箇所・§5.3 説明・§5.5 発火条件を新設 |
| `docs/task/index.md` | 本タスク行を追加 |

## 検証方針

- 製品コード（`yt_gui/`）不変のため自動テストのスコープ外。単体テストは追加しない。
- `docs-check` で docs 整合を点検、`evaluator` で受け入れ条件充足を判定。
