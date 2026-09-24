# プロンプト監査の指摘反映（文言のみ）

> Issue: なし（`docs` ブランチ・受け入れ条件を持たない作業）
> ステータス: 完了
> ブランチ: `docs/prompt-audit-cleanup`
> 基点: f454b1b

`/claude-api prompt-audit` でハーネスのプロンプト面（`CLAUDE.md` / `.claude/agents` / `.claude/rules` / `.claude/skills` / `docs/git-workflow.md` / `docs/docs-guide.md` / `docs/testing/policy.md`、計 19 ファイル）を監査した結果のうち、**事実を削らない文言変更だけ**を反映する。

## 監査の前提（レポートの Step 0）

- 対象モデル: 主セッション = Opus 5、`evaluator` / `design-review` = `model: opus`、他 5 本 = `model: sonnet`。いずれも世代エイリアスで日付サフィックス無し。
- アプリコードに LLM API 呼び出しは無い（`openai|langchain|genai|anthropic|claude-*` の走査ヒットは `.venv/` と settings.json の schema URL のみ）ため、API 側のパターン（prefill・`budget_tokens`・強制 `tool_choice` など）は該当なし。
- 変更した行の `git log -L` は最古 2026-05-29・最新 2026-09-19 で、**退役モデル時代の記述は無い**。よって各指摘の根拠は「古いモデル向けに書かれた形跡」ではなくパターン表の該当行であり、**信頼度は最高で「中」**。

## この PR に入れたもの

| # | 指摘 | 変更 |
|---|---|---|
| C | 移行相対の言い回し（「従来どおり」「従来挙動」） | `docs/git-workflow.md` 4 箇所・`docs/testing/policy.md` 1 箇所から「従来」を削除 |
| D | エージェント定義に置かれた来歴の語り | `.claude/agents/implementer.md` の留保の blockquote を削除（`git-workflow.md` §5.2 に一字一句同じものが残る） |
| E | 機構で担保済みの規則に重ねたブースター | `CLAUDE.md`「絶対に守るルール」→「中核ルール」 |
| F | 思考言語の指示の不整合 | `CLAUDE.md`「英語で行う」→「英語で行ってよい」（サブエージェント 7 本の「行ってよい」に統一） |

## この PR に入れなかったもの

- **F1（`docs-check` の観点のうち構造で判定できる 5 つを pytest へ移す）**: 振る舞いを変える変更で、新規テスト（`tests/test_docs_consistency.py`）と 7 箇所の連動修正を伴う。テスト先行（policy §2.6 の変異 → red）が要るので別 Issue・別 PR。
- **F7〜F10（トークン会計が無い / `verify`・`docs-check` の `effort: low` / 強調密度 / `criteria-review` と `design-review` の骨格の近さ）**: いずれも実害の実例を挙げられていないので、git-workflow §5.9「起票の着手条件」に照らすと今起票する条件を満たさない。次の `/harness-retro extract` の候補表へ回す。
- **`evaluator.md:24` の trait clause（監査の F2）**: 判断の質に触れる変更なので、C〜F の文言整理と混ぜない。F1 と同じく別 PR。

## 触っていない（意図的）

- `docs/git-workflow.md` §5.2 訂正ログの止め規則にある「『変えていない』『従来どおり』のような**不変を主張する語**」— 語の**言及**（洗うべき語彙の例示）であって使用ではない。
- `evaluator.md` 評価軸 6 / `docs-check.md` 観点 9 の「（雛形 claude-templates の採用プロジェクトでの事例）」— 同じ文が「繰り返し起きた」と主張しており、この括弧はその**限定句**。落とすことは軸 6 / 観点 9 が禁じている「伝播先で限定句だけが落ちる」形そのものになる。
- `.claude/hooks/*.py` の docstring にある「従来どおり」4 箇所 — 同じ型だがコード側なので、docs のみの本 PR には含めない。

## 進捗

- [x] C 「従来」5 箇所の削除 — 証跡: `git diff` の該当 hunk
- [x] D `implementer.md` の留保の削除 — 証跡: `git diff` の該当 hunk
- [x] E `CLAUDE.md` の見出し文言 — 証跡: `git diff` の該当 hunk
- [x] F `CLAUDE.md` の思考言語の文言統一 — 証跡: `git diff` の該当 hunk
- [x] verify-gate（`docs` ブランチにつき evaluator は対象外） — 証跡: 本文「検証」節

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り・2026-09-24 時点）

- F1（`docs-check` の観点 → pytest 移管）を Issue 起票してから `/start-task`。優先順は本業（#39 / #84）の後でよい。
- F2（`evaluator.md:24` の trait clause）は F1 と同じ PR か、その後の単独 PR で。
- F7〜F10 は次の `/harness-retro extract` の候補表へ。
- 訂正ログ: 0 件
