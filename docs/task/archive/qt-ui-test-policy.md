# Qt UI テスト導入 (2): テスト方針の格上げ・spec 整合

関連: Qt UI テスト導入 (1) [archive/qt-ui-test-ci.md](qt-ui-test-ci.md)（Issue #17 / PR #18 マージ済み）

ドキュメントのみの変更のため、運用ルール §4 に従い Issue を伴わない `docs/` ブランチ（`docs/test-policy-qt-ui-scope`）で実施。

## 背景

Qt UI テスト導入の前提として、`docs/testing/policy.md` が **「Qt UI = ×」「E2E / UI スモーク = ×」** と明記しており、このまま UI テストを追加すると方針と矛盾する。本タスクで policy を実態に合わせて格上げし、対象とする振る舞いと `docs/spec/` の対応を整理する。実テスト・`pytest-qt` 導入は後続 (3)。

## 実施内容

### policy.md の更新

- **§1 スコープ表**: `Qt UI = ×` の単一行を分割。
  - `queue_controller.py`（編集モード状態機械）・`original_format_panel.py`（トラック選択の排他/論理状態）→ `△`
  - `threading_utils.py`（コールバック順序）→ `△`
  - `app.py` / `settings_dialog.py` / `log_dialog.py`（ウィンドウ統合）→ `×` 据え置き
  - `△` は UI に閉じた振る舞い限定・`pytest-qt` + `offscreen` 必須である旨を注記。
  - **段階導入の注記**: 方針は `△` に格上げするが、`pytest-qt` 導入と `omit` 解除は後続。テストが無いモジュールは当面 `omit` に残し、テスト追加と同時に該当モジュールのみ外す（カバレッジ急落の回避）。
- **§2.1 仕様駆動**: 対応 spec が無いインフラヘルパ（`threading_utils.py`）は例外として `docs/arch/` リンクで代替可とする一文を追加。Qt UI 状態機械は queue.md / original-format-panel.md に対応づける旨を明記。
- **§2.4 粒度表**: `E2E / UI スモーク = ×` を「Qt UI 単体（`qtbot` + `offscreen`）= △」と「E2E = ×」に分離。
- **§2.5（新設）**: Qt UI テストの実行要件（offscreen・`@pytest.mark.qt` 分離・`QMessageBox`/`missing_dependencies` 副作用抑制・イベントループ/スレッド後始末）を方針として明文化。具体実装は (3)。
- **§6**: Qt UI を「未導入」→「方針格上げ済み／実装は後続」、Downloader を「一部導入済み」に更新。

### docs/testing/index.md

- (1) で CI 実行節を追加済み。本タスクでの追加変更なし。

### spec 整合（確認結果）

対象振る舞いは既存 spec でカバー済みのため、**spec の新規追記は不要**と判断。

- 編集モードの状態遷移（`waiting` ↔ `editing`、適用/キャンセル、複数選択時のオリジナル形式グレーアウト）: [spec/features/queue.md](../../spec/features/queue.md) 「編集モード」節。
- トラック選択の排他（AUTO / SKIP / 音声 ID の相互解除）: [spec/screens/original-format-panel.md](../../spec/screens/original-format-panel.md) 「排他ロジック」節。
- `edit_mode_entered` / `edit_mode_exited` 等のシグナル名は実装詳細のため [arch/queue_controller.md](../../arch/queue_controller.md) 側に対応（spec はステータス遷移という観測可能な振る舞いで対応づく）。
- `threading_utils.run_in_thread`: 対応 spec なし → [arch/threading_utils.md](../../arch/threading_utils.md) に対応（§2.1 の例外）。

## 対象ファイル

- `docs/testing/policy.md`（§1 / §2.1 / §2.4 / §2.5新設 / §6）
- `docs/task/qt-ui-test-policy.md`（本ファイル・新規） / `docs/task/index.md`（更新）
- `docs/task/qt-ui-test-ci.md` → `archive/` へ移動（(1) の完了処理） / `docs/task/archive/index.md`（追記）

## 次アクション

1. コミット → push → `gh pr create --base main`（docs 変更のため `Closes` なし、(1) PR #18 を参照）。
2. ユーザー承認後マージ。マージ後、本タスクを「完了」へ更新し archive へ移動。
3. 後続 (3): `pytest-qt` 導入・`conftest.py`（offscreen 固定・`QMessageBox`/`missing_dependencies` 抑制・`qt` マーカー登録）・§6 優先候補の UI テスト本体・該当モジュールの `omit` 解除。Issue 化して着手。
