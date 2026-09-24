# プロンプト監査の指摘反映（文言のみ）

> Issue: なし（`docs` ブランチ・受け入れ条件を持たない作業）
> ステータス: 進行中（実装・検証は完了。push と PR 作成が `gh` の認証切れで未了）
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

- [x] C 「従来」5 箇所の削除 — 証跡: コミット 935ad12
- [x] D `implementer.md` の留保の削除 — 証跡: コミット 935ad12
- [x] E `CLAUDE.md` の見出し文言 — 証跡: コミット 935ad12
- [x] F `CLAUDE.md` の思考言語の文言統一 — 証跡: コミット 935ad12
- [x] verify-gate — 証跡: `uv run pytest` 603 passed（2026-09-24 14:37 頃・作業ツリー = 935ad12 の内容）／`docs-check` 修正点なし・要対応 1 件（メトリクス句）。`docs` ブランチにつき `evaluator` は対象外（git-workflow §5.2）
- [ ] push（`git push -u origin docs/prompt-audit-cleanup`） — 証跡: 未。**`gh` の認証切れでブロック中**
- [ ] PR 作成（ベース `main`・本文日本語・Issue 無しなので `Closes #` は書かない） — 証跡: 未
- [ ] メトリクス句の追記と archive への移動（`docs-guide.md` §4.2） — 証跡: 未

## 訂正ログ

| 日付 | 何を誤って書いたか | 正しくは | どの検査・手順なら捕まえたか |
|---|---|---|---|

## 次にやること（申し送り・2026-09-24 時点）

**このブランチ（`docs/prompt-audit-cleanup`）のまま再開すること**（`main` で再開すると、このメモは注入されない。git-workflow §5 分割点 A）。

1. **`gh` の認証を直す。** ここでブロックしている。現象と切り分け済みの事実:
   - `gh auth status` → `The token in default is invalid.` / `gh api user` → HTTP 401
   - `GH_TOKEN` / `GITHUB_TOKEN` はいずれも未設定（環境変数の横取りではない）
   - `GH_CONFIG_DIR` 未設定。`gh` は `C:\Program Files\GitHub CLI\gh` v2.101.0、実行ユーザーは `f8924`
   - `%APPDATA%\GitHub CLI\hosts.yml` は `users: f8924919: {}` のみで **`oauth_token` を持たない**（トークンは Windows 資格情報マネージャー側）。最終更新 14:39:11 で、その後のログイン試行では**更新されていない**
   - ユーザーは RDP の別 PowerShell からログインしたと報告しているが、本セッションからは 401 のまま。`gh auth status` は失敗時もアカウント名 `f8924919` を出力するため、成否の読み違いの可能性あり（`✓ Logged in` か `X Failed to log in` かで判定する）
   - 直し方: `gh auth logout -h github.com -u f8924919` の後に `gh auth login -h github.com -p https -w`。`gh api user --jq .login` が `f8924919` を返せば成功
   - 素の `git push` は Git Credential Manager が TTY を要求して失敗する（`/dev/tty: No such device`）。`git -c credential.helper='!gh auth git-credential' push` も `gh` 側が無効なので同じく失敗した
2. `git push -u origin docs/prompt-audit-cleanup`
3. `gh pr create`（ベース `main`・本文は日本語・**対応 Issue が無いので `Closes #` は書かない**）
4. PR 番号が確定したら、本メモを `docs/task/archive/` へ戻し、`docs/task/index.md` の `## タスク` 表から行を削除、`docs/task/archive/index.md` の「ドキュメント整備」表へ行を戻す（**この PR の前のコミットで一度書いた行の文面が `git log -p` に残っている**）。その概要セル末尾にメトリクス句を付ける: `メトリクス: コミット N（PR #M）・訂正ログ 0 件・evaluator 0 巡`（N は `git rev-list --count f454b1b..<PR の最終コミット>`）
5. マージ後は `/finish-task`（Issue が無いので B はスキップ、C は同梱済みにつきスキップ。A のブランチ削除のみ）

**この PR の後に残る監査の宿題**（本タスクの範囲外・着手しない）:

- F1（`docs-check` の観点のうち構造で判定できる 5 つを `tests/test_docs_consistency.py` へ移管）を Issue 起票してから `/start-task`。優先順は本業（#39 / #84）の後でよい
- F2（`evaluator.md:24` の trait clause 「自分が good と思いたいバイアスを排し、」の削除）は F1 と同じ PR か、その後の単独 PR で
- F7〜F10（トークン会計・`verify`/`docs-check` の `effort: low`・強調密度・`criteria-review` と `design-review` の骨格の近さ）は実害の実例が無いので、次の `/harness-retro extract` の候補表へ
- 監査レポートの全文は scratchpad（`prompt-audit-report.md`）にあるが、**セッション固有なので再起動で消える**。上の 4 項目が残す必要のある全部である

訂正ログ: 0 件
