# Git / GitHub 運用ルール

ブランチ運用・Issue ベース開発・PR の詳細ルールを定めます。中核ルールの要約は [CLAUDE.md](../CLAUDE.md) の「Git / GitHub 運用ルール」を参照してください。

> 本ルールは制定以降の作業に適用します。制定前に作成済みのブランチ・PR には遡及しません。

---

## 1. ブランチモデル

**GitHub Flow** を採用します（`develop` ブランチは使いません）。

- `main` が常にデプロイ可能な唯一の長期ブランチ。
- すべての変更は `main` から切ったフィーチャーブランチで行い、`main` へ PR を出してマージする。
- **`main` で直接コミットしない。**

このルールは二段構えで機械的に強制されている（#232）。

- **クライアント側（早期警告）**: Claude Code の PreToolUse hook（[.claude/hooks/block_main_commit.py](../.claude/hooks/block_main_commit.py)・[.claude/hooks/block_main_edit.py](../.claude/hooks/block_main_edit.py)・[.claude/settings.json](../.claude/settings.json)）が、カレントブランチが `main` のときの `git commit` / `git push` と、**リポジトリ内ファイルの編集**（`Edit` / `Write` / `NotebookEdit`）をブロックする。対象は Claude Code のツール経由の操作のみ（matcher `Bash|PowerShell` / `Edit|Write|NotebookEdit`）。判定はカレントブランチのみで、git コマンド失敗時等は**フェイルオープン**（誤って全コマンドをブロックしない）。起動子は `uv run --no-sync python`（本リポジトリの必須ツールである uv を使う。素の `python` は Windows で Microsoft Store スタブに化けることがあるため不採用）。settings.json の hook 定義は **exec form**（`command` + `args` 配列・`${CLAUDE_PROJECT_DIR}` プレースホルダは Claude Code が置換）とする（shell form はシェル展開・PATH 解決依存で Windows にて不発火だったため。#235）。hooks はセッション開始時に読み込まれるため、変更後の実効確認は新しいセッションで行う。uv 不在等で hook 自体が起動できない場合も Claude Code は非ブロッキング扱いでコマンドを通す（フェイルオープン）が、その状態では hook が無効なので注意。hook 層全体の設計方針は §5.6 を参照。
- **サーバー側（最後の砦）**: branch protection の `enforce_admins` が有効で、feature ブランチからの `git push origin main` を含む main への直 push は管理者であっても GitHub 側で拒否される。PR 経由のマージには影響しない。緊急時にどうしても直 push が必要な場合は `gh api -X DELETE repos/f8924919/yt-gui/branches/main/protection/enforce_admins` で一時解除し、対応後に `-X POST` で必ず再有効化する。

hook の検出は「単発・複合コマンド（`&&` / `;` / `|` 区切り）のサブコマンド位置での `git commit` / `git push` 一致」に留める（`git -c k=v commit` のようなオプション挟み込みや文字列内の擦り抜けは追わず、サーバー側の enforce_admins に委ねる。誤ブロック回避を優先する設計）。

ただし**リモートブランチの削除**（`git push --delete` / `-d`、`:branch` 形の refspec）は `main` 上でも通す。マージ済みブランチの削除は `main` へ戻ってから行う正規の手順（§5 step 9・[`/finish-task`](../.claude/skills/finish-task/SKILL.md)）であり、これを塞ぐと運用が回らない。削除は `main` の履歴を変更しないため、本 hook の目的（main への直接の変更を防ぐ）から外れる。

ブランチ判定は hook 入力の `cwd` を起点にした**実効ディレクトリ**に対して行う（#240）。複合コマンド内の `cd <path>` セグメントを追跡し、git のグローバルオプション `-C <path>`（空白区切り・複数指定の累積）も解決したうえで、対象リポジトリのカレントブランチを判定する。これにより別リポジトリの feature ブランチへの commit/push は誤ブロックせず、別リポジトリの `main` 上なら従来どおりブロックする。`--git-dir` / `--work-tree` によるリポジトリ指定・クォート付きパス（スペースを含むパス）は追わず、パス解決に失敗するケースは一律フェイルオープン（通す）。

```
main ──┬──────────────────┬──→ (本番)
       │ feature/12-foo    │
       └──────────────────┘ PR → main
```

## 2. GitHub 操作

- 接続・起票・閲覧・PR 作成などの GitHub 操作には必ず `gh` コマンドを使用する。
- PR のベースブランチは常に `main`。
- マージ方式はマージコミット（リポジトリの履歴に合わせる）。**マージはユーザーの承認後に行う。**

## 3. Issue ベース開発

修正・機能追加は Issue の内容に基づいて実施します。

- Claude が Issue を起票する際は、**AI が単独で実装・完結できる粒度**の技術仕様を記述する。最低限、以下を含める。
  - **背景 / 目的**: なぜ必要か
  - **受け入れ条件**: 完了の判定基準（チェックリスト形式が望ましい）
  - **対象ファイル・モジュール**: 変更が想定される箇所
  - **関連ドキュメント**: 該当する `docs/spec/` / `docs/arch/` へのリンク
- Issue 本文・コメントは原則日本語で記述する。ただし**既存の Issue / PR スレッドが日本語以外で書かれている場合は、そのスレッドの言語に合わせる**（[CLAUDE.md 言語ルール](../CLAUDE.md#言語ルール)の「既存スレッドへの追従（例外）」に従う）。Claude が新規起票する場合は日本語をデフォルトとする。

### Issue と `docs/task/` の役割分担

| | GitHub Issue | `docs/task/{slug}.md` |
|---|---|---|
| 役割 | 起票・仕様・受け入れ条件の**正本** | 作業中の**設計・進捗メモ** |
| 主な内容 | 背景・受け入れ条件・対象範囲 | 実装方針・検討メモ・検証結果 |
| 紐付け | 本文に対応する task ファイルを記載 | 冒頭に対応 Issue 番号 (`#12`) を記載 |

両者は相互リンクで紐付けます。タスクの進捗・完了管理は従来どおり [docs/task/index.md](task/index.md) で行います（[CLAUDE.md タスク管理ルール](../CLAUDE.md#タスク管理ルール)参照）。

## 4. ブランチ命名規則

| 種別 | 命名 | Issue 番号 | 用途 |
|---|---|---|---|
| フィーチャー | `feature/<issue>-<short-description>` | 必須 | 機能追加 |
| バグ修正 | `bugfix/<issue>-<short-description>` | 必須 | 不具合修正 |
| ホットフィックス | `hotfix/<issue>-<short-description>` | 必須 | 緊急修正 |
| リファクタリング | `refactor/<short-description>` | 不要 | 振る舞い不変の内部改善 |
| ドキュメント | `docs/<short-description>` | 不要 | ドキュメントのみの変更 |
| 雑務 | `chore/<short-description>` | 不要 | 依存更新・設定変更など |

- `<short-description>` は内容を表す英小文字 + ハイフン（kebab-case）。例: `feature/12-proxy-settings`。
- `feature` / `bugfix` / `hotfix` は対応する Issue を前提とし、ブランチ名に Issue 番号を含める。
- `refactor` / `docs` / `chore` は Issue を伴わない作業のため番号は付けない。

## 5. 作業フロー（標準）

**docs（設計）先行・テストファースト**を基本とする。設計をドキュメントで固めてから実装に入り、テストは仕様に基づいて先に書く。step 1〜6（前半）は `/start-task` skill で順序を強制しながら立ち上げられる（§5.3）。

1. 対象 Issue を確認（無ければ §3 の要件で起票）。
2. `main` を最新化し、§4 の規則でブランチを作成。
3. docs 先・コード裏取りで調査する（[CLAUDE.md](../CLAUDE.md) の調査ルール）。**調査は読み取り専用の `investigate` サブエージェント（Sonnet）へ委譲し、主エージェントは結論（要点・関連 `path:line`）だけを受け取る**（[CLAUDE.md 調査ルール](../CLAUDE.md#調査ルール-docs-先コード裏取り)参照）。設計・実装方針の判断は委譲せず主エージェントが行う。
   - **step 3.5（受け入れ条件レビュー）**: docs 先行・実装に入る前に、`criteria-review` サブエージェント（Sonnet）で **受け入れ条件・spec そのものの妥当性**（テスト可能・網羅的・非曖昧・Issue 意図との整合）を点検する。**助言でありゲートではない**（指摘の採否・条件の修正は主エージェント＋ユーザーが判断、§5.1）。`evaluator`（step 7）が実装の**適合性**を PR 前に独立評価するのに対し、こちらは実装前に**条件自体の妥当性**を見る（対象が逆で補完関係）。`refactor` / `docs` / `chore`（受け入れ条件を持たない作業）は対象外。
4. **設計を `docs/spec/` / `docs/arch/` に先に反映する**（実装前にドキュメントで設計を固める。[docs-guide.md](docs-guide.md) §4 の更新先に従う）。
   - **step 4.5（設計レビュー・条件付き）**: §5.5 の発火条件に該当する場合、docs に固めた設計案を `design-review` サブエージェント（Opus）で点検する（アーキ整合・代替案・結合/スコープ・リスク・docs 整合）。**助言でありゲートではない**（設計方針の最終決定は主エージェント＋ユーザー、§5.1）。発火可否は主エージェントの主観では決めず、investigate（step 3）の「設計レビュー推奨」と §5.5 のトリガで機械的に判定する。推奨が yes のとき主エージェントは自己判断でスキップせず、省略する場合は理由をユーザーに提示して承認を得る。`criteria-review`（step 3.5・条件の妥当性）とは対象が異なり、設計案そのものの妥当性を見る。
5. **テストを先に書く**。テストは spec / 受け入れ条件に基づいて書き、実装に合わせて書かない（[テスト方針](testing/policy.md)）。
6. 実装してテストを green にする。
7. **検証ゲート**（PR 前。いずれもサブエージェントへ委譲、§5.2。`/verify-gate` skill でブランチ種別に応じて一括起動できる、§5.3）:
   - lint / フォーマット / 型チェック / テストを `verify` サブエージェント（Sonnet）で green にする（[CLAUDE.md](../CLAUDE.md) のコマンド参照）。
   - docs / CLAUDE.md を変更した場合は `docs-check` サブエージェント（Sonnet）で整合性（index 更新漏れ・リンク切れ・命名・関連仕様リンク）を点検する。
   - **`feature` / `bugfix` / `hotfix` ブランチでは `evaluator` サブエージェント（Opus）で評価ゲートを通す**（受け入れ条件・spec の充足を独立判定。`verify` で green にした後に実行する）。起動可否は [CLAUDE.md](../CLAUDE.md) の評価ゲート（evaluator）モードに従う（§5.2）。
8. `gh` で PR を作成（ベース `main`、本文は原則日本語＝対応する Issue スレッドが日本語以外ならその言語に合わせる、関連 Issue を `Closes #<issue>` で紐付け）。
9. **ユーザーの承認後**にマージし、マージ済みブランチを削除。完了タスクの archive 移動は**原則 step 6〜8 の実装 PR に同梱**する（[docs-guide.md](docs-guide.md) §4.2。#222）。マージ後の後処理（main 最新化・ブランチ削除、同梱できなかった場合のまとめ archive 移動）は `/finish-task` skill で実行できる（§5.3）。

### 5.1 補足ルール

- **設計外の問題への対応**: 実装中に設計段階で考慮していなかった問題が出た場合は、勝手に判断せず**対応案をユーザーに提示して確認を取る**（設計の変更はユーザーの判断事項として扱う）。
- **コミット粒度**: テストを先に書いても、失敗（red）のテスト単独ではコミットしない。実装まで進めて green にしてから 1 コミットにまとめる。

### 5.2 サブエージェントへの委譲

機械的・探索的な作業、および独立評価は専用のサブエージェントへ委譲し、主エージェントの文脈を温存する。定義は `.claude/agents/` 配下。調査・検証・docs 整合・受け入れ条件レビューは Sonnet、独立評価（`evaluator`）と設計レビュー（`design-review`）は Opus を使う（理由は後述）。**設計・仕様の判断、テスト内容の決定、設計外の問題への対応は委譲せず、主エージェントとユーザーが行う**（§5.1）。

| エージェント | モデル / effort | 委譲する作業 | 対応するフロー | 主エージェントが受け取るもの |
|---|---|---|---|---|
| [`investigate`](../.claude/agents/investigate.md) | Sonnet / `medium` | docs 先・コード裏取りの調査 | step 3 | 結論・関連 `path:line`・裏取りメモ |
| [`criteria-review`](../.claude/agents/criteria-review.md) | Sonnet / `medium` | 受け入れ条件・spec の妥当性を実装前に点検（助言） | step 3.5 | 受け入れ条件の指摘・改善案（採否は委譲しない） |
| [`verify`](../.claude/agents/verify.md) | Sonnet / `low` | lint / フォーマット / 型 / テストを green にする | step 7 | 検証結果・修正点・要判断項目 |
| [`docs-check`](../.claude/agents/docs-check.md) | Sonnet / `low` | docs 整合性の点検と機械的修正 | step 7 | 点検結果・修正点・要対応項目 |
| [`design-review`](../.claude/agents/design-review.md) | Opus / `high` | 設計案の妥当性を実装前に点検（助言・§5.5 発火時） | step 4.5 | 設計の指摘・改善案（設計方針の決定は委譲しない） |
| [`evaluator`](../.claude/agents/evaluator.md) | Opus / `high` | 受け入れ条件・spec の充足を独立評価 | step 7 | 総合判定・受け入れ条件ごとの合否・要対応項目 |

**effort をエージェント側で固定する理由**: 指定しないとセッションの effort をそのまま継承するため、**同じエージェントの判定力がその日の設定で変わる**。特に `evaluator` / `design-review` は「レビュアーが生成者より弱いと追認してしまう」という理由で Opus を割り当てているのに、effort がセッション任せだとその前提が崩れる。逆に `verify` / `docs-check` は結果を客観的に検証できる機械的作業なので、最も頻度が高いにもかかわらず高い effort を継承するのは無駄。**モデル（能力の器）と effort（考える深さ）を別々に固定**し、どちらもセッション設定に依存させない。より厳しく見たい回はユーザーが起動時にオーバーライドしてよい（`design-review` / `evaluator` を `xhigh` に上げる等）。

読み取り専任のエージェント（`investigate` / `criteria-review` / `design-review` / `evaluator`）は、`tools` から `Edit` / `Write` を外すだけでは `Bash` 経由の書き込み・commit を防げない。そこで frontmatter に **`permissionMode: plan`（読み取り専用モード）** を指定し、本文の約束ではなく機構で担保する。特に `evaluator` の独立性は本ワークフローの中核であり、口約束に委ねない。ただし親セッションが `bypassPermissions` / `acceptEdits` / auto モードの場合は親の権限モードが優先されエージェント側の指定は無視されるため、各エージェント本文の「読み取り専用」の記述も残す（二段構え）。`verify` / `docs-check` は修正を行うため対象外。

委譲の判断は費用対効果で行う。検証が一発で通る見込みなら `verify` を介さず主エージェントが直接回す、軽い確認は `investigate` を介さず直接読む、といった使い分けでよい。

ただし **`evaluator` は例外**で、その場の費用対効果で省略してよいものとして扱わない。評価の目的は主エージェントの自己評価バイアスの排除にあり、「単純だから評価不要」という判断自体がそのバイアスに当たる（かつテストが green でも露見しない）ため、起動可否を主エージェントの裁量に委ねず、**モードとブランチ種別で機械的に決める**（後述の「評価ゲート（evaluator）のモード」）。省略を許すかどうかはモードの選択としてあらかじめ決めておく事項であり、個々の PR で判断しない。

`evaluator` と `design-review` が Opus なのは、調査・検証・docs 整合・受け入れ条件レビューが結果を客観的に検証できる機械的・構造的タスクなのに対し、この 2 つは裁量を伴う判断だから。特に生成側（主エージェント）も Opus のため、評価者・レビュアーが生成者より弱いと、`evaluator` では実装の見落としを、`design-review` では不十分な設計を、それぞれ追認してしまう。コストが問題になった場合は Sonnet への降格を検討する（独立性が判定力の一部を補う）。

`criteria-review` は `evaluator` と対をなすが**性格が逆**で、実装前に受け入れ条件**自体**の妥当性を点検する**助言**であり、ゲート化しない（通過可否・条件の修正は主エージェント＋ユーザーが判断、§5.1）。`evaluator` のようにブランチ種別で強制はせず、受け入れ条件を持つ作業で任意に用いる。構造的な点検（測定可能性・網羅性・曖昧さ）が主で裁量は小さいため Sonnet とする。

`design-review` も助言でゲート化しないが、`criteria-review` と違い**設計批評そのものが高い裁量を要する**（＋設計案は Opus の主エージェントが生成する成果物なので弱い評価者は追認しがち）ため Opus とする。常時ではなく §5.5 の発火条件に該当する時だけ起動する点も両者と異なる。

#### 評価ゲート（evaluator）のモード

`evaluator` の起動可否は **[CLAUDE.md](../CLAUDE.md) の「評価ゲート（evaluator）モード」** を単一の正本として決める（[`/verify-gate`](../.claude/skills/verify-gate/SKILL.md) はこの値を読むだけで、判定ルールを再定義しない）。対象は受け入れ条件を持つ `feature` / `bugfix` / `hotfix` ブランチのみで、`refactor` / `docs` / `chore` はモードに関わらず常に対象外。

| モード | 挙動 |
|---|---|
| `always` | 対象ブランチで**必ず**起動（省略不可）。「単純だから不要」という判断自体が、evaluator で排除したい自己評価バイアスに当たるため、起動可否を裁量に委ねない |
| `auto` | 変更規模が**閾値**を超える回に起動する。閾値以下はスキップしてよい |
| `off` | 起動しない。`.claude/agents/evaluator.md` は残るため、いつでも `auto` / `always` へ戻せる |

**`auto` の閾値**（いずれかを満たせば「大きい変更」とみなす）:

| 基準 | 判定手段 |
|---|---|
| 変更ファイル数 ≧ 5、または変更行数（追加 + 削除）≧ 200 | `git diff --shortstat main...HEAD` |
| `docs/spec/` 配下の**新規** spec ファイルを含む | `git diff --name-status main...HEAD` の `A` 行（未コミット分は `git status --short` の `??`） |

**値そのものは [CLAUDE.md](../CLAUDE.md) にのみ書く**（本節は定義であって値ではない。値を 1 箇所で切り替えられることがモード制の目的なので、ここに現行値を再掲しない）。モード行が見つからない・改名されている場合は、勝手に `off` 扱いにせず**ユーザーにモードを確認する**（安全側フォールバック）。

`auto` / `off` は立ち上げ初期の負荷を下げるための割り切りであり、思想的には `always` が正統（バイアス排除の観点）。実績としても、モード制導入時点で evaluator は #285 の 2 本の PR で**「単純な設定変更」に見えた回に決定打の不具合を検出**しており、規模による省略は割に合わない。

#### 設計レビュー（design-review）のモード

`design-review`（step 4.5）の起動可否も **[CLAUDE.md](../CLAUDE.md) の「設計レビュー（design-review）モード」** を単一の正本として決める。evaluator と違い実装前・助言・高コスト（Opus）なので、既定は §5.5 の構造トリガに従う `auto`。

| モード | 挙動 |
|---|---|
| `always` | 規模・トリガに関わらず、設計を伴うタスク（docs 先行で設計を固めた回）で毎回起動する |
| `auto` | **§5.5 の発火トリガに該当する回だけ**起動する（investigate の「設計レビュー推奨」が yes の時）。設計余地の大きい変更を守りつつ、単純タスクでは省く |
| `off` | 起動しない。`.claude/agents/design-review.md` は残るため、いつでも `auto` / `always` へ戻せる |

値そのものは evaluator と同じく [CLAUDE.md](../CLAUDE.md) にのみ書く。モード行が見つからない・改名されている場合は**従来挙動の `auto`（§5.5 のトリガ判定）へ倒す**（助言でありゲートではないため、evaluator と違ってユーザー確認までは求めない）。

evaluator の `auto` が「変更規模のしきい値」で発火するのに対し、design-review の `auto` は **§5.5 の構造トリガ**（新モジュール・新しい境界・複数モジュール横断など）で発火する。設計の複雑さは diff の大きさと相関しないため、判定軸を分けている。

`criteria-review` はモードを設けない。安価（Sonnet）で、受け入れ条件を持つ作業なら常に価値があるため常時運用の助言とする。

### 5.3 スキル（オーケストレーション入口）

定型の多段手順は `.claude/skills/` 配下の skill にまとめ、`/<skill 名>` で起動する。skill は**手順の入口**であり、起動条件やモデル選定などの**ルールは再定義せず §5.2 等の正本を参照**する（二重管理＝drift を避けるため）。

| skill | 役割 | 対応するフロー |
|---|---|---|
| [`start-task`](../.claude/skills/start-task/SKILL.md) | Issue 確認/起票・ブランチ作成・`investigate` 起動・`criteria-review`（受け入れ条件レビュー・助言）・（§5.5 発火時）`design-review`（設計レビュー・助言）・docs 先/テスト先の順序ゲート（判断は自動化せず確認に留める）・実装 | step 1〜6 |
| [`verify-gate`](../.claude/skills/verify-gate/SKILL.md) | ブランチ種別を判定し `verify` →（docs 変更時）`docs-check` →（feature/bugfix/hotfix のみ）`evaluator` を順に起動・集約 | step 7 |
| [`finish-task`](../.claude/skills/finish-task/SKILL.md) | `main` 最新化・マージ済みブランチ削除・（実装 PR に同梱できなかった場合の補完として）完了タスクの archive 移動（複数タスクまとめ可・docs ブランチ＋PR） | step 9 |

skill が呼ぶサブエージェントの**合否・設計判断は委譲しない**点は §5.1 / §5.2 と同じ。skill は正しい順序・条件での起動と結果集約に徹する。

**frontmatter の注意**: skill に指定できる `argument-hint` は引数の書式ヒントで、付けてよい。一方 **`allowed-tools` は「その skill の実行中に使えるツールの絞り込み」であって、コマンドの事前承認ではない**（公式リファレンスの例も `allowed-tools: Read, Grep, Glob # Restrict tool access`）。事前承認のつもりで git コマンドだけを並べると、skill が `Read` / `Write` / サブエージェント起動を失って手順の中核が実行できなくなる。**コマンドの事前承認は §5.7 の `permissions.allow`（settings.json）で行う**こと。

### 5.4 ルール層（path-scoped、`.claude/rules/`）

特定の種類のファイルを編集する瞬間にだけ思い出すべき遵守事項は、`.claude/rules/` 配下に **path-scoped rule** として置く。Claude Code はマッチするファイルを読んだ時にそのルールをコンテキストへ自動注入する（`paths` frontmatter の glob で対象を指定）。CLAUDE.md（常時ロード）と違い、関係するファイルを触る時だけ載るため文脈を節約できる。

- **薄いポインタに徹し、正本は再定義しない**: ルール本文に手順をコピーすると単一情報源が崩れる（§5.3 の skill と同じ drift 回避方針）。各 rule は対応する正本 docs を指し、編集時に外しやすい要点だけを再掲する。
- **順序ゲートの置き換えではなく補完**: path-scoped は「マッチするファイルを *読んだ* 後」に発火するため、新規領域では発火が遅れることがある。`/start-task`（docs 先・テスト先の順序）や `/verify-gate`（PR 前検証）を代替しない。

| rule | `paths` | 正本 | 効かせたい瞬間 |
|---|---|---|---|
| [`testing.md`](../.claude/rules/testing.md) | `tests/**`, `**/test_*.py` | [testing/policy.md](testing/policy.md) | テストを書く / 直す時（テストファースト・red 単独コミット禁止） |
| [`docs-upkeep.md`](../.claude/rules/docs-upkeep.md) | `docs/*.md`, `docs/**/*.md` | [docs-guide.md](docs-guide.md) | spec / arch / task を編集する時（index 追記・相互リンク・archive 手順の漏れ防止） |

### 5.5 設計レビュー（`design-review`）の発火条件

設計レビュー（step 4.5）は全タスクには回さない。単純タスクではノイズ・コストが過剰になる一方、「単純だから省く」を主エージェントの主観に委ねると `evaluator` を必須化したのと同じ自己評価バイアス（「不要」という判断自体がバイアス）に陥る。そこで**発火は客観的な構造トリガで機械的に判定**し、主エージェントの主観に委ねない。

**発火トリガ（いずれか 1 つでも該当 → 実施を既定とする）**

| トリガ | 理由（設計接続点が増える＝レビュー価値が高い） |
|---|---|
| 新モジュール追加（`yt_gui/{name}.py` → `arch/` 新規が必要） | 新しい構造の導入 |
| 新画面・ダイアログ（`spec/screens/` 追加） | UI 設計の分岐 |
| 新スレッド / シグナル経路・外部プロセス連携・同梱バイナリ追加 | アーキ接続点の増加（Signal/Slot 規約に関わる） |
| 複数モジュールにまたがる変更 | 境界設計の判断が発生 |
| investigate が「実装方針の候補が複数ある / docs が薄く前例なし」と報告 | 設計余地が大きい |
| Issue に `needs-design` ラベル or「設計判断」節がある | ユーザーの明示 |
| 外部サービスの API 契約に自前クライアントで直接依存する | 契約は上流都合で予告なく壊れる（#262: attestations API の破壊的変更）。公式クライアント・既製手段との比較が必要 |
| 失敗すると自己修復できない機能（自己更新・データマイグレーション等） | 不具合修正の配布経路自体が壊れるため要求信頼性が桁違いに高い（#276 の教訓） |
| 権限・実行環境差に敏感な操作（symlink / ACL / 保護フォルダ等）を含む依存・実装 | 開発環境（昇格・特定 OS）の検証が偽陰性になりやすい（#275）。[testing/policy.md](testing/policy.md) §7 の非昇格検証が必要になる |

**非発火例（省略してよい）**: 設定項目 1 個の追加・翻訳キーのみ・既存パターンに乗るだけの機能追加・局所的な bugfix・`refactor`（振る舞い不変で既存構造内）。

下 3 つのトリガ（Phase B 撤去・#262/#275/#276 の教訓）に該当する設計では、design-review への依頼時に**既製手段（公式 CLI・公式ライブラリの高レベル API・パッケージマネージャ配布等）を代替案として必ず比較対象に含める**こと。自前実装は「外部契約の追従責任」と「全ユーザー環境での動作責任」を自分で負うことを意味し、その妥当性自体が設計判断となる（経緯は [docs/research/app-update.md](research/app-update.md) の Phase B 撤去節）。

**判定ルール**

- まず [CLAUDE.md](../CLAUDE.md) の**設計レビューモード**（定義は §5.2）を確認する。`off` なら起動しない。`always` なら設計を伴う回で必ず起動する。`auto` のとき、以下のトリガ判定で決める。
- トリガ判定は investigate（step 3）が担い、報告に「設計レビュー推奨: yes/no ＋理由」を出す（主エージェントの自己申告に依存させない）。
- 1 つでも該当（推奨 yes）→ **実施を既定**とする。主エージェントは主観でスキップせず、省略する場合は**理由をユーザーに提示して承認を得る**（提示のみの自己判断スキップは禁止）。
- ユーザーはオン / オフ両方向でオーバーライドできる（推奨 no でも設計に不安があれば起動を要求してよい。最終判断はユーザー）。
- `design-review` は助言でありゲートではない。指摘の採否・設計方針の最終決定は主エージェント＋ユーザーが行う（§5.1）。

### 5.6 hooks 層（`.claude/hooks/`）

**プロンプトの指示に頼らず機構で効かせたいもの**は hook にする。CLAUDE.md や本ファイルに書いた約束はモデルが読み飛ばしうるが、hook は必ず走る。§5.3 の skill・§5.4 の rule が「思い出させる」層なのに対し、hooks は「守らせる / 手当てする」層に当たる。

| hook | イベント / matcher | 役割 | 正本 |
|---|---|---|---|
| [`session_task_status.py`](../.claude/hooks/session_task_status.py) | `SessionStart` | [task/index.md](task/index.md) の 2 つの表を `additionalContext` として注入する | [CLAUDE.md](../CLAUDE.md) タスク管理ルール |
| [`block_main_commit.py`](../.claude/hooks/block_main_commit.py) | `PreToolUse` / `Bash\|PowerShell` | `main` 上の `git commit` / `git push` をブロック（リモートブランチ削除は除く） | §1 |
| [`block_main_edit.py`](../.claude/hooks/block_main_edit.py) | `PreToolUse` / `Edit\|Write\|NotebookEdit` | `main` 上のリポジトリ内ファイルの編集をブロック | §1 |
| [`format_edited_file.py`](../.claude/hooks/format_edited_file.py) | `PostToolUse` / `Edit\|Write` | 編集した `yt_gui/` `tests/` 配下の `.py` を `ruff format` で整形する | [CLAUDE.md](../CLAUDE.md) の「Lint / Format / 型チェック」 |

`block_main_edit.py` が `block_main_commit.py` と別に必要なのは、commit をブロックしても**そこに至るまでの編集は素通り**するため。ブランチを切り忘れたことに気付くのが commit 直前になり、`git stash` などの巻き戻しが要る。編集の時点で止めればその手戻りが消える。

`format_edited_file.py` は、検証ゲート（§5 step 7）の `ruff format` で最後にまとめて整形すると整形だけの差分が実装コミットに混ざる問題への手当て。編集直後に同じ整形を掛けておけばその往復が消える。整形は verify ゲートでも走るため、ここでの失敗は「早めに整形できなかった」以上の意味を持たない。

共通の設計方針:

- **フェイルオープン**: 判定に迷うケース（stdin のパース失敗・パス解決不能・git やツールの実行失敗）は必ず「通す」に倒す。hook の不調で作業が止まる方が損失が大きい。ブロック系はサーバー側 branch protection（§1）が最後の砦。
- **正本を再定義しない**: hook は判定と注入に徹し、ルール本文は docs 側に置く（§5.3 の skill・§5.4 の rule と同じ drift 回避方針）。
- **標準ライブラリのみ**: hook は Claude Code から直接起動されるため、プロジェクトの依存解決に頼らない。起動子は `uv run --no-sync --project ${CLAUDE_PROJECT_DIR} python` に統一する（§1）。
- **反映タイミング**: hooks の登録（settings.json）はセッション開始時に読み込まれるため、変更後の実効確認は新しいセッションで行う。hook スクリプト本体は実行のたびに読まれるため即座に効く。
- **テスト**: hook のロジックは `tests/test_{hook 名}.py` で検証する（[testing/policy.md](testing/policy.md) §1）。`--cov=yt_gui` の範囲外につきカバレッジ計測対象外。

### 5.7 権限ルール（`.claude/settings.json` の `permissions`）

検証ゲート（§5 step 7）で毎回走る品質コマンドは `permissions.allow` に列挙し、都度確認を省く。`verify` が lint / 型 / テストの往復のたびに承認待ちで止まると、委譲の利点（主エージェントの文脈温存）が失われるため。

**allow に入れる**: [CLAUDE.md](../CLAUDE.md) の「Lint / Format / 型チェック」「テスト」節に載っている**検証系のコマンド**（`ruff check --fix` / `ruff format` のように**ソースを自動整形するものも含む**。ルールはプレフィックス一致でフラグを解釈しないため、`ruff check *` を許可した時点で `--fix` も通る。整形結果は diff で確認でき、失うものが無いため許容する）と、`gh` の**参照系**（`issue view` / `issue list` / `pr view` / `pr list` / `pr checks` / `pr diff`）。Claude Code の Bash / PowerShell **両ツール分**を登録する（サブエージェントは Bash を使う一方、主エージェントは Windows では PowerShell を使うため）。

**allow に入れない**（都度確認させる）:

| 対象 | 理由 |
|---|---|
| 依存のインストール・更新（`uv sync` / `uv add` / `uv remove`） | 依存ツリー・ロックファイルを書き換える |
| アプリの起動・ビルド（`python -m yt_gui` / `pyinstaller`） | 重い副作用（GUI プロセス起動・成果物生成）を伴う。実行は主エージェントが明示的に行う（[testing/policy.md](testing/policy.md)） |
| 同梱バイナリの取得（`scripts/download_binaries.py` 等） | ネットワーク取得とファイル配置を伴う |
| `git commit` / `git push` | main 判定 hook（§1）とサーバー側 branch protection の判断を素通りさせない |
| `gh issue create` / `gh pr create` / `gh api -X`（参照系以外） | 外部に影響する操作。起票・PR 作成はユーザー確認を経る |

**deny**: `git push --force` / `-f`（両ツール分）。deny は allow より先に評価され例外を作れないため、広い deny（`git push *` 等）は置かない。

> **deny の限界**: ルールはプレフィックス一致でフラグを解釈しないため、`git push origin main --force` のようにフラグを**後置**した形や `git push origin +main`（`+` による強制更新）は deny をすり抜ける。deny は事故の第一線であって最後の砦ではなく、`main` については §1 の hook とサーバー側 branch protection が担保する。

ルールの書式は Bash / PowerShell とも glob で、末尾 ` *` は語境界付きの前方一致（引数なしの実行にもマッチする）。追加・変更時は**上の表の分類（検証系は allow、副作用のあるものは都度確認）に沿っているか**を判断基準にする。個人的な例外を足したい場合は、コミットされない `.claude/settings.local.json` に置く。
