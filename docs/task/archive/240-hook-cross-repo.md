# main 保護 hook のクロスリポジトリ誤ブロック修正

対応 Issue: [#240](https://github.com/f8924919/yt-gui/issues/240)

## 概要

hook がブランチ判定を hook 入力の `cwd` に対してのみ行うため、`cd <別リポジトリ>; git commit ...` が別リポジトリの feature ブランチ上でも誤ブロックされる。また `git -C <path> commit`（空白区切り）は `-C` のパース漏れでそもそも検出されない（フェイルオープンの穴）。

criteria-review の実機検証で Issue 起票時の前提（「`-C` で誤ブロック」）が誤りと判明し、真因（`cd` 未追跡）に合わせて受け入れ条件を書き直した（ユーザー確認済み）。

## 実装方針（ユーザー確認済みスコープ）

1. **`cd` 追跡**: 複合コマンドのセグメントを順に見て `cd <path>` で実効ディレクトリを更新し、git セグメントのブランチ判定は実効ディレクトリで行う。
2. **`-C <path>` パース**: git のグローバルオプションのうち引数を取る `-C` を正しく読み飛ばしてサブコマンドを検出し、ブランチ判定には実効ディレクトリへ `-C` を累積適用したパスを使う。
3. **スコープ外**: `--git-dir` / `--work-tree`・クォート付きパス（スペース含む）は追わない。パス解決失敗は一律フェイルオープン。
4. **品質ゲート**: `tests/test_block_main_commit.py` 新設（importlib 読込・一時 git リポジトリで検証）、mypy files に hook を追加、policy.md スコープ表に追記。

## 進捗メモ

- 2026-07-12: criteria-review で root cause 誤認を発見 → Issue #240 の受け入れ条件を全面改訂。docs 先行（git-workflow §1 検出方針・policy.md スコープ表）完了。
- 2026-07-12: 既存テスト `tests/test_block_main_commit.py` の存在を確認（起票時の「テストなし」認識は誤り。policy.md 未記載は実際の drift で今回解消）。Issue のテスト条件を「既存への追加」に補正。
- 2026-07-12: テスト先行（クロスリポジトリ 17 ケース追加・subprocess 起動方式を踏襲）→ 実装（`_blocked_violation`: cd 追跡＋実効ディレクトリ、`_git_subcommand`: `-C` 累積解決・`--git-dir`/`--work-tree` フェイルオープン）。mypy files に hook を追加。lint / format / mypy / 全テスト（473 passed）green。
