# Qt UI テスト導入 (3): pytest-qt 導入とハーネス・初回 UI テスト

対応 Issue: #20

関連: (1) [archive/qt-ui-test-ci.md](archive/qt-ui-test-ci.md)（#17/#18）・(2) [archive/qt-ui-test-policy.md](archive/qt-ui-test-policy.md)（PR #19）

## 背景

(1) CI 新設・(2) テスト方針格上げが完了。本タスクで `pytest-qt` を実際に導入し、テストハーネスと最初の Qt UI テストを追加する。スコープは **テスト基盤 + `threading_utils` + `queue_controller`（編集モード）** に絞り、`original_format_panel` 等は後続。

## 実施内容

### テスト基盤

- `pytest-qt>=4.5.0` を dev 依存に追加。
- `pyproject.toml` に `qt` マーカーを登録（`--strict-markers` 対応）。
- `[tool.coverage.run] omit` から `queue_controller.py` ・ `threading_utils.py` を除外解除。
- `tests/conftest.py`:
  - `QT_QPA_PLATFORM=offscreen` を `os.environ.setdefault` で固定。
  - `_silence_qt_modal_dialogs`（autouse・`qt` マーカー時のみ・遅延 import）でモーダル `QMessageBox` を no-op 化。
- Qt 非導入環境での skip は各 qt テストモジュール冒頭の `pytest.importorskip("PySide6")` / `pytest.importorskip("pytestqt")` で実現（import 失敗より前にモジュール単位 skip。コレクションフックは import 失敗後に走り単独では不十分なため採用しない）。

### テスト

- `tests/test_threading_utils.py`: `run_in_thread` の成功時 `on_done`→`on_finished`、例外時 `on_failed`→`on_finished` のコールバック順序（`qtbot.waitUntil`）。対応 arch: threading_utils.md。
- `tests/test_queue_controller.py`: `enter_edit_mode`（waiting→editing・`edit_mode_entered`・全 waiting でないと False）/ `apply_edit`（format 差し替え・waiting 復帰・`edit_mode_exited`）/ `cancel_edit`（job 不変で waiting 復帰）。対応 spec: features/queue.md 編集モード。

### docs

- `docs/testing/policy.md` §2.5（skip 機構を importorskip と明記）・§3（ディレクトリ図にテストファイル追記）。

## 検証結果（ローカル）

- `uv run pytest` → 80 passed（既存 74 + 新規 6）。
- `uv run pytest -m "not qt"` → 74 passed, 6 deselected（Qt マーカー分離の確認）。
- `ruff check` / `ruff format --check`（yt_gui/ + tests/）pass、`mypy yt_gui/` pass。
- カバレッジ: `threading_utils.py` 100% / `queue_controller.py` 62%（編集モード部分）/ TOTAL 79%（一括解除による急落なし）。

## 対象ファイル

- `pyproject.toml`・`tests/conftest.py`・`tests/test_threading_utils.py`（新規）・`tests/test_queue_controller.py`（新規）・`docs/testing/policy.md`

## 次アクション

1. コミット → push → `gh pr create --base main`（`Closes #20`）。
2. ユーザー承認後マージ。マージ後、本タスクを「完了」へ更新し archive へ移動。
3. 後続: `original_format_panel` 排他ロジック、§6 残り候補（`_QueueTree` コンテキストメニュー、`_open_settings`/`_refresh_format_labels` 等）を別 Issue 化。
