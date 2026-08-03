# #284 update-binaries.yml が作成する PR で必須 CI が発火せずマージできない

- Issue: [#284](https://github.com/f8924919/yt-gui/issues/284)
- ブランチ: `bugfix/284-pin-update-pr-ci`
- 関連 docs: [build.md](../../build.md)「同梱バイナリのピン自動更新」

## 背景

既定の `GITHUB_TOKEN` による PR 作成は他のワークフローを起動しない（再帰実行防止の仕様）。`update-binaries.yml` が `peter-evans/create-pull-request@v8` を既定トークンのまま使っているため、自動起票された PR で `test.yml` / `codeql.yml` が発火せず、`main` の必須チェック（`test` / `test-windows`）が満たされずマージできない。実運用では毎回 close → reopen で CI を通していた（#283・#290）。

## 方針

Issue の**案 A（fine-grained PAT）**を採用（ユーザー決定）。

- secret `PIN_UPDATE_TOKEN`（fine-grained PAT / Contents・Pull requests の write のみ）を `create-pull-request` の `token:` に渡す
- **secret 未設定時はフォールバック＋警告**（ユーザー決定）。`${{ secrets.PIN_UPDATE_TOKEN || github.token }}` で `GITHUB_TOKEN` に落とし、PR 作成自体は継続する。上流更新の検知・sha256 検証まで止めるとサプライチェーン検証の恩恵ごと失われるため。ただし静かに #284 の症状へ戻らないよう、`::warning::` と **PR 本文冒頭の注記**で可視化する
- `permissions:` ブロックは残す（checkout とフォールバック経路の `GITHUB_TOKEN` が使う）
- 未設定判定は job の `env.HAS_PIN_UPDATE_TOKEN`（**真偽値**）を経由する。`secrets` はステップの `if` で参照できない一方、PAT の値そのものを job `env` に置くと `uv sync` や外部 HTTP を行う `refresh_pins.py` を含む全ステップの環境に載るため（evaluator 指摘）

### 検討して採らなかった案

- **明示的に失敗させる**: 失効に必ず気づける反面、PAT が切れている間 `bin/pins.json` の更新検知そのものが止まる。フォールバック＋警告で「気づける」条件は満たせるため不採用。
- **案 B（GitHub App トークン）**: 期限管理が不要だが初期セットアップが重い。PAT の失効運用が負担になった時点で移行する（build.md に記載）。
- **`test.yml` に `workflow_dispatch` 追加**: 手動起動 run のチェックは PR にステータスとして紐付かず、必須チェックを満たせない（Issue 記載）。

## 完了の二段階クローズ（ユーザー決定）

PAT 発行はリポジトリオーナーの手作業で Claude が代行できないため、確認タイミングで分ける。

- **実装 PR のマージ = 実装完了**: yml 変更・docs 更新・回帰テスト（Issue 受け入れ条件 A）
- **Issue クローズ = 実地確認まで完了**: PAT 発行・secret 登録後、`workflow_dispatch` で CI 発火を確認し run URL を Issue にコメント（同 B）

## テスト

workflow yml を検証する pytest は既存になかったため新規に追加した（`tests/test_update_binaries_workflow.py`・dev 依存に `pyyaml` を追加。[testing/policy.md](../../testing/policy.md) §1 のスコープ表にも記載）。`update-binaries.yml` をパースし、`token:` の PAT 参照とフォールバック・警告ステップの `if` 条件・PR 本文への注記を検証する。

検証力はミューテーションで実測した（`token:` 行削除・`||` 削除・警告ステップ削除・注記ブロックのみ削除・`if` 削除・`if` 反転・job `env` 削除・`env` を PAT の値に変更・警告ステップを PR 作成の後ろへ移動、の 9 変異すべてを検出）。

evaluator の指摘で 2 度直している。初版は「PR 本文への注記」テストが `--summary-out` の指定にも一致する文字列を見ていて恒真で、注記ブロックを丸ごと削っても素通りしていた（判定を警告ステップの `run` 内に限定して解消）。次版は job `env` の間接層が無検証で、`env` 定義が消えると `if` が常に偽になり警告が二度と出ないまま #284 の症状へ静かに戻る穴が残っていた（`env` とステップ順序のテストを追加して解消）。

## メモ

- `peter-evans/create-pull-request` の `token` 入力の既定値は `${{ github.token }}`（上流 `action.yml` で確認済み）。よって `||` フォールバックは既定の挙動と同じものへ落ちる。
- 同じ問題を抱えるワークフローは `update-binaries.yml` のみ（`release.yml` / `codeql.yml` は PR を作らない。dependabot は別仕組み）。
