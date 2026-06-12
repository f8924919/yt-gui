# リファクタリング全体計画

[← タスク一覧](index.md)

> 前提: [docs/research/refactoring-analysis.md](../../research/refactoring-analysis.md) で洗い出した 12 候補 (A〜L) を、依存関係と投資効果でフェーズ分割した実行計画。

## 背景

ニコニコ動画コメント機能（フェーズ 1–3, 2026-05-24 完了）追加後の `yt_gui/` 4,087 行に対し、調査メモで以下が明らかになった。

- 約 87% (3,640 行) が `app.py` / `original_format_panel.py` / `downloader.py` の 3 ファイルに集中
- 「`format_id` → 設定派生」のラダーが 3 箇所重複、13–16 個の引数バケツが 5 関数横断で受け渡される
- 上記 3 ファイルはテスト 0 件で、機能追加のたびに後方互換 default が混入し始めている

調査メモの推奨に従い、**A: `JobSpec` 集約 / B: `build_job_spec` 集約 / C: テスト先行** をワンセットで最初に着手し、それを安全網として残りの中・低優先度項目に進む。

## ゴール

- 4,087 行の構造を維持可能な状態に整える
- 振る舞いは変えない（既存仕様 `docs/spec/features/*.md` と 1:1 対応のまま）
- リファクタの過程で `app.py` / `downloader.py` / `original_format_panel.py` に**最低限のテスト網**を入れる

## 完了条件

- 下記フェーズ 1〜7 のすべてが「完了」になっていること
- `docs/research/refactoring-analysis.md` の候補 A〜L すべてが対応するフェーズに紐づき、未対応として残っていないこと
- `uv run ruff check yt_gui/` / `uv run ruff format --check yt_gui/` / `uv run mypy yt_gui/` / `uv run pytest` がすべて通過すること

## フェーズ構成

| フェーズ | タスク | 対応候補 | 優先度 | 状態 |
|---|---|---|---|---|
| 1 | [refactor-job-spec.md](refactor-job-spec.md) | A, B, C | 高 | 完了 (2026-05-25) |
| 2 | [refactor-app-split.md](refactor-app-split.md) | D | 中 | 完了 (2026-05-25) |
| 3 | [refactor-nico-comments-group.md](refactor-nico-comments-group.md) | E | 中 | 完了 (2026-05-26) |
| 4 | [refactor-thread-signal-helper.md](refactor-thread-signal-helper.md) | F | 中 | 完了 (2026-05-26) |
| 5 | [refactor-i18n-combo-sentinel.md](refactor-i18n-combo-sentinel.md) | G, H | 中 | 完了 (2026-05-26) |
| 6 | [refactor-downloader-split.md](refactor-downloader-split.md) | I, J | 中 | 完了 (2026-05-26) |
| 7 | [refactor-misc-cleanup.md](refactor-misc-cleanup.md) | K, L | 低 | 完了 (2026-05-26) |

## 進行ルール

1. **フェーズは原則順番に進める**。フェーズ 1 (C のテスト) はそれ以降すべての安全網になるため最優先。
2. **1 フェーズ = 1 PR**。 振る舞い変更が無いこと (`uv run pytest` 全通過) を必ず確認してからマージ。
3. **ブランチ命名**: `refactor/{phase-slug}` (例: `refactor/job-spec`, `refactor/app-split`)。
4. **docs 連動**: 各フェーズの完了時に対応する `docs/arch/*.md` を必ず更新する ([docs-guide.md §4](../../docs-guide.md) に従う)。
5. **振る舞いは変えない**。仕様変更が必要だと感じた場合は本リファクタから切り離し、別タスクとして起票する。
6. **フェーズ完了時の手順**:
   - 該当タスクファイルの「ステータス」を `完了 (YYYY-MM-DD)` に更新
   - [`index.md`](index.md) の該当行を `完了` + 更新日に変更
   - 本ファイルの「フェーズ構成」表の状態列を更新

## 関連ドキュメント

- [docs/research/refactoring-analysis.md](../../research/refactoring-analysis.md) — 調査メモ（採否未決の検討メモ）
- [docs/arch/index.md](../../arch/index.md) — モジュール構成
- [docs/testing/policy.md](../../testing/policy.md) — テスト方針

## ステータス

完了 (2026-05-25 開始 / 2026-05-26 全フェーズ完了)
