# 開発ワークフロー改善調査（効率・品質観点）

調査日: 2026-07-07 / 対応 Issue: なし（本メモが正本。個別対応に着手する際に項目ごとに Issue を起票する）

## 選定結果（2026-07-10）

ユーザー判断により **A-1〜A-5 に着手**することを決定し、項目ごとに Issue を起票した。

| 項目 | Issue |
|---|---|
| A-1 CI でカバレッジを計測する | [#210](https://github.com/f8924919/yt-gui/issues/210) |
| A-2 lint / format / mypy の対象範囲の非対称を解消する | [#211](https://github.com/f8924919/yt-gui/issues/211) |
| A-3 ruff ルールセット・mypy 厳格度の引き上げ | [#212](https://github.com/f8924919/yt-gui/issues/212)（A-2 の後に実施） |
| A-4 release.yml に uv キャッシュを追加する | [#213](https://github.com/f8924919/yt-gui/issues/213) |
| A-5 docs-check の点検観点に pyproject.toml 同期を追加する | [#214](https://github.com/f8924919/yt-gui/issues/214) |

B・C・D 群は上記完了後に再検討する（未選定のまま保留）。なお未確認事項のうち branch protection の有無（C-1）は 2026-07-10 に確認済み: main に保護設定あり（test チェック必須・strict・レビュー必須 0 人・enforce_admins 無効）。

## 目的

このプロジェクトの開発ワークフロー（docs 運用・CI・品質ゲート・Git 運用）を、開発効率と成果物品質の観点で棚卸しし、改善候補を優先度付きで整理する。後日、項目単位でタスク化・Issue 化して対応するための調査メモ。

## 調査方法

読み取り専用の investigate サブエージェント 3 本を並行起動し、以下の観点で調査した。

1. ワークフロー定義（CLAUDE.md / docs/git-workflow.md / docs/docs-guide.md / .claude/agents / .claude/skills / .claude/rules）
2. CI・自動化・ツール設定（.github/workflows / pyproject.toml / dependabot / ビルド）
3. リポジトリ実態（コード・テスト規模、docs↔コード整合、Git 履歴 159 マージの運用実績）

## 現状評価（良い点・維持すべき点)

- **docs ↔ コードの整合性が高い**: サンプル確認（`yt_gui/app.py` ⇔ `docs/arch/app.md` 等）で実装と arch ドキュメントが同一コミットで更新されており乖離なし。CLAUDE.md の「docs の鮮度は高い」前提は実態と一致。
- **品質は安定**: 全 472 コミット中 revert 0 件。bugfix/hotfix/fix は計 11 件（約 7%）。
- **テストが充実**: `tests/` 5,834 行・371 テスト関数。直近実測カバレッジ TOTAL 約 85%（`docs/testing/policy.md` 記載）。
- **docs 体系の drift 回避方針が一貫**: 「正本を 1 箇所に置き、他は薄いポインタに徹する」構造（CLAUDE.md ↔ git-workflow ↔ agents/skills ↔ rules）が守られており、明確な矛盾は発見できなかった。
- **サプライチェーン対策が丁寧**: 同梱バイナリのピン管理（`bin/pins.json`）＋週次更新（`update-binaries.yml`）、リリースの 4 OS マトリクス＋来歴署名。

## 改善候補

### A. 低コスト・高効果（優先着手推奨）

#### A-1. CI でカバレッジを計測する

- 現状: `pyproject.toml:45-53` に coverage 設定（omit 含む）があるのに、CI（`.github/workflows/test.yml:57-58`）は `--cov` なしの `uv run pytest` のみ。カバレッジはローカル任意実行のみで自動計測されていない。
- 方針メモ: `docs/testing/policy.md:142` は「数値閾値は初期は設けない（計測のみ）」と定めるが、閾値導入の前提として CI での計測自動化が先に必要。まず `--cov` + レポート出力を CI に追加し、数サイクル観測後に閾値導入を再検討する。

#### A-2. lint / format / mypy の対象範囲の非対称を解消する

- 現状: CI の `ruff format --check` と `mypy` が `yt_gui/` 限定（`test.yml:51-55`）。`tests/` と `scripts/`（サプライチェーン関連スクリプト含む）がフォーマット・型チェックの対象外。`ruff check` は `.` 全体で非対称。
- 方針メモ: 対象を `tests/` `scripts/` にも拡大する。CLAUDE.md 記載のローカルコマンドも合わせて更新する。

#### A-3. ruff ルールセット・mypy 厳格度の引き上げ

- 現状: ruff は `["E","F","I","UP"]` のみ（`pyproject.toml:63-65`）。バグ検出に効く `B`（bugbear）、`SIM`（simplify）、`C4`（comprehensions）、`RUF` 等が未導入。mypy 設定も最小で `disallow_untyped_defs` / `check_untyped_defs` 等なし（`pyproject.toml:75-79`）。
- 方針メモ: どのルールセットまで入れるか・strict をどこまで強めるかは候補が複数あるため、着手時に §5.5 の設計レビュー要否を判定する（git-workflow.md:148 の「実装方針の候補が複数」に該当し得る）。

#### A-4. release.yml に uv キャッシュを追加する

- 現状: `release.yml:65` の `astral-sh/setup-uv@v7` に `enable-cache: true` がなく、4 OS マトリクス全てで毎回依存をフルダウンロード。`docs/task/archive/actions-node24.md:21` に「release.yml では未使用」と事実記録のみあり、意図的見送りか未着手かの理由は残っていない。
- 方針メモ: 意図的見送りの理由が見つからなければキャッシュ有効化。1 行変更でビルド時間を短縮できる見込み。

#### A-5. docs-check エージェントの点検観点に pyproject.toml 同期を追加する

- 現状: `docs/testing/policy.md:39,159` は「テスト対象スコープ拡張時は本ポリシーと `pyproject.toml` の `omit` を併せて更新」と明記しているが、`.claude/agents/docs-check.md:16-23` の点検 6 観点（index 更新漏れ・リンク切れ・関連仕様リンク・命名規則・ドキュメントマップ・タスク連動）にこの同期チェックが含まれていない。docs だけ更新されて omit リストが追従しないドリフトを機械検出できない。
- 方針メモ: docs-check の観点に「testing/policy.md ⇔ pyproject.toml（coverage omit・pytest markers）の整合」を追加する。

### B. プロセスコストの削減（効率化の本丸）

#### B-1. archive 移動専用 PR の統合

- 現状: 全 159 マージ中 36 件（約 23%）が「完了タスクメモを `docs/task/archive/` へ移動するだけ」の PR（例: `docs/archive-198-app-update-phase-a` は 3 ファイル変更・2 行挿入のみ）。`main` 直コミット禁止のため、機能 1 件ごとに「実装 PR + archive 移動専用 PR」の 2 本が構造的に発生している。
- 方針メモ: 選択肢は (a) 実装 PR 内に archive 移動を含める（タスク完了が PR マージと同時に確定する場合のみ可能かの検討要）、(b) `/finish-task` を複数タスクまとめて実行する運用、(c) 現状維持（レビュー粒度優先）。正本ルール（git-workflow.md / docs-guide.md §4.2 / `/finish-task` skill）の意図とのトレードオフがあるため、ユーザー判断が必要な設計判断領域。

#### B-2. サブエージェント多段ゲートのコスト対効果の見直し

- 現状: feature/bugfix タスク 1 件あたり最大 6 回のサブエージェント起動（investigate → criteria-review → design-review(条件付) → verify → docs-check(docs 変更時) → evaluator）。非発火条件（§5.5 非発火例、criteria-review/evaluator の refactor/docs/chore 除外）は整備済みだが、単独開発 + AI 運用の規模に対するコスト（時間・トークン）の定量評価は未実施。
- 方針メモ: `git-workflow.md:106` に Opus コスト超過時の Sonnet 降格検討が既に記載あり（オーナー認識済み）。運用実績のログを踏まえた棚卸しタイミングで判断する。急ぎではない。

### C. 堅牢性の強化（要判断・ややコスト高）

#### C-1. ルールの機械的強制（hooks / branch protection / pre-commit）

- 現状: 「main で直接作業しない」「ブランチ命名規則」「マージはユーザー承認後」（`docs/git-workflow.md:15,50-63`）はすべてドキュメント上の合意のみ。`.claude/settings.json` は context7 プラグイン有効化のみで hooks 未設定、`.claude/settings.local.json` も空。pre-commit 未導入（docs 内に導入検討の記述もなし）。GitHub 側の branch protection 設定の有無は本調査（ローカルファイルのみ）では未確認。
- 方針メモ: 候補は (a) GitHub branch protection で main 直 push を禁止（最優先・設定のみ）、(b) Claude Code hooks で main 上のコミットをブロック、(c) pre-commit で ruff/mypy をローカル強制。まず GitHub 側設定の現状確認から。

#### C-2. テスト CI の Windows 追加

- 現状: pytest は Ubuntu ランナー単体（`test.yml:20`）。単一 OS は `docs/testing/index.md:35` に明記された意図的選択だが、アプリは Windows / macOS 向け。実際に Windows 固有バグの実績あり（#201: `SO_REUSEADDR` の Windows 仕様差でポートフォールバック不発。Windows 実機でのみ再現）。
- 方針メモ: release では 4 OS ビルド済みなので、少なくとも `windows-latest` での pytest 追加を検討。Qt offscreen 前提のテスト方針（`docs/testing/policy.md`）との整合と、OS 依存分岐の実数を確認してから判断。

#### C-3. 大型モジュール × カバレッジ除外の重なり

- 現状: 500 行超は `yt_gui/app.py`（1,544 行・カバレッジ約 66%）、`yt_gui/original_format_panel.py`（1,280 行・omit で計測除外）、`yt_gui/downloader.py`（1,212 行）。`settings_dialog.py`（923 行）も準大型。フェーズ 1〜7 の計画的リファクタ実施済み（`docs/task/archive/refactor-overview.md`）の残存規模であり無秩序な肥大化ではないが、「大きい × 計測されていない」箇所が品質リスクの集中点。
- 方針メモ: `docs/testing/policy.md` の段階導入方針（omit の段階解除）に沿って、omit 解除の次ステップを計画する。A-1（CI 計測）が先。

#### C-4. SAST（CodeQL 等）の導入

- 現状: `.github/workflows/` にセキュリティスキャン系ワークフローなし。バイナリピン等の供給網対策は整備済みなので、静的解析だけが空白。
- 方針メモ: CodeQL（python）を追加する場合は新規ワークフロー追加のみで低コスト。誤検知ノイズとのバランスを見て判断。

### D. 軽微（実害未確認・任意）

- **investigate エージェントの役割定義の緊張**: `investigate.md:33` で「設計判断はしない」と明言しつつ、`investigate.md:43` で設計レビュー要否（yes/no）を判定させており、その基準の一つ「実装方針の候補が複数」（`git-workflow.md:148`）は設計的判断を要する。実務上は機能しているため、定義を見直すなら文言調整程度でよい。
- **git-workflow.md の番号体系の二重化**: メインフローの step 1〜9（`git-workflow.md:69-82`）と詳細ルールの §5.1〜§5.5 が別体系で、初見で追いにくい。実害なし。

## 未確認事項（着手時に要確認）

- GitHub 側 branch protection 設定の有無（C-1。`gh api` で確認可能）。
- release.yml の uv キャッシュ未使用が意図的か（A-4。履歴に理由の記録なし）。
- OS 依存分岐の実数と Windows CI 追加の費用対効果（C-2）。
- サブエージェントゲートの実トークン消費・所要時間（B-2。定量ログなし）。

## 推奨着手順

1. **A-1〜A-5**（CI/ツール設定の底上げ。各々小粒で独立、Issue 1 件ずつに分割可能）
2. **B-1**（archive 移動 PR の統合。ユーザーの設計判断が必要）
3. **C-1**（branch protection の確認と有効化）
4. C-2 / C-3 / C-4 / B-2 / D は上記の後、必要に応じて。

## 進捗

- [x] 調査（investigate ×3・2026-07-07）
- [x] 対応する項目の選定（ユーザー判断・2026-07-10、A-1〜A-5 を選定）
- [x] 選定項目の Issue 起票（2026-07-10、#210〜#214）
- [ ] 選定項目の個別対応（A-1 #210 → A-2 #211 → A-3 #212 → A-4 #213 → A-5 #214 の順）
- [ ] B・C・D 群の再検討（A 群完了後）
