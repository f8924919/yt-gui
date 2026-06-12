# Qt UI テスト: original_format_panel の音声トラック排他ロジックのテスト

対応 Issue: #22

親: Qt UI テスト導入 (3) [archive/qt-ui-test-harness.md](qt-ui-test-harness.md)（#20 / PR #21）

## 背景

(3) で整備したハーネス（`pytest-qt` + offscreen + `qt` マーカー + `importorskip`）を使い、`original_format_panel.py` の `_AudioListWidget` の排他ロジックを固定する。

## 実施内容

- `tests/test_original_format_panel.py`（新規, `@pytest.mark.qt`）を追加。
- fixture はパネル本体（`original_format_panel.py` L524-529）と同じ手順で構築（`_AudioListWidget()` → `setSelectionMode(ExtendedSelection)` → `set_normal_mode(...)`）。`ExtendedSelection` を後付けする点が肝で、これが無いと既定の SingleSelection になり multi-select 排他の挙動が再現できない。
- 検証:
  - `set_normal_mode` が AUTO/SKIP 行に sentinel、音声行に format_id を `UserRole` で付与（論理状態の分離）
  - 公開ヘルパ `select_auto` / `select_skip` / `select_audio_rows` の排他（spec 排他ロジック表）
  - `_enforce_exclusivity`（`itemSelectionChanged` 経由）: 「自動」+音声 → 自動解除 / 「skip」+音声 → skip 解除（arch L53-54）

## 検証結果（ローカル）

- `tests/test_original_format_panel.py` 6 passed。`uv run pytest` 全体 86 passed。
- `ruff check` / `ruff format --check`（yt_gui/ + tests/）・`mypy yt_gui/` pass。

## coverage omit の判断

`original_format_panel.py` は約 1226 行で、本タスクで検証するのは排他ロジック（約 90 行）のみ。`[tool.coverage.run] omit` から外すとファイル単体が約 7% となり TOTAL を不当に引き下げる。policy.md の段階導入（急落回避）の趣旨に従い、**本タスクでは omit 据え置き**とする。映像コンボや出力モードなど広範な UI ロジックをテストする後続タスクで、まとめて omit 解除を判断する。

## 対象ファイル

- `tests/test_original_format_panel.py`（新規）
- `docs/task/original-format-panel-tests.md`（本ファイル） / `docs/task/index.md`

## 次アクション

1. コミット → push → `gh pr create --base main`（`Closes #22`）。
2. ユーザー承認後マージ。マージ後、本タスクを archive へ移動。
3. 後続: #23（App 周辺 UI ロジック）、映像コンボ/出力モードを含む original_format_panel 広範テスト + omit 解除。
