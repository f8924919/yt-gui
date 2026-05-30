# Qt UI テスト: App 周辺の UI ロジックのテスト

対応 Issue: #23

親: Qt UI テスト導入 (3) [archive/qt-ui-test-harness.md](archive/qt-ui-test-harness.md)（#20 / PR #21）

## 背景

research メモ §6 の優先候補のうち、`App` 周辺の UI ロジック 2 件を対象に追加する。

- `_QueueTree` のコンテキストメニュー「形式を変更」の対象判定（`waiting` のみ・編集モード中でない）
- `_refresh_format_labels` の言語追従（`format_combo` 再構築）

## つまずき: モーダル `QMenu.exec` はモック不可

当初 `contextMenuEvent` を直接駆動し `QMenu.exec` を monkeypatch する方針だったが、**PySide6 では生成済みインスタンスの `menu.exec()` がネイティブ呼び出しで、`QMenu.exec` のクラス属性上書きを無視する**ため offscreen でハングした（`QMessageBox.warning` はクラス静的メソッドなので差し替えが効くが、インスタンスメソッドの `exec` は別）。プローブで確認済み。

→ 対応: 活性判定と発火判定で共用していたゲーティングを純粋ヘルパ `_QueueTree._edit_targets(items)` に抽出（DRY ＋ テスト可能化の小さなリファクタ）。`contextMenuEvent` の挙動は不変（`setEnabled(bool(targets))` / `emit(targets)`）。

## 実施内容

- `yt_gui/app.py`: `_QueueTree._edit_targets(items) -> list[_QueueItem]` を抽出。編集モード中または `waiting` 無しなら空リスト。
- `tests/test_app.py`（新規, `@pytest.mark.qt`）:
  - `_edit_targets`: 非編集時に waiting 部分集合を返す / 編集中は空 / waiting 無しは空
  - `_refresh_format_labels`: ja→en で `format_combo` のテキストが再構築され `_build_format_display()` と一致し ja と異なる
  - `app` fixture は HOME を tmp に向け、`Downloader.missing_dependencies` を空にして構築（policy §2.5 の決定性確保）
- docs: `docs/arch/app.md`（`_edit_targets` の説明）、`docs/testing/policy.md` §1（`app.py` を限定付き `△` に格上げ）・§3（テストファイル追記）。

## coverage omit の判断

`app.py` は大きく、本タスクのテストは一部のみ。`original_format_panel` と同様、`omit` は据え置き（段階導入・急落回避）。

## 検証結果（ローカル）

- `tests/test_app.py` 4 passed / 全体 **90 passed**。
- `ruff` / `ruff format`（yt_gui/ + tests/）・`mypy yt_gui/` pass。

## 注意（環境）

- テスト中にハングするプロセスが残ると後続の `uv run pytest` まで巻き込まれて全体がハングしたように見える（offscreen Qt の資源競合）。切り分け時は `pkill -f pytest` で残プロセスを止めてから再実行する。

## 対象ファイル

- `yt_gui/app.py`・`tests/test_app.py`（新規）・`docs/arch/app.md`・`docs/testing/policy.md`・`docs/task/app-ui-logic-tests.md`（本ファイル） / `docs/task/index.md`

## 次アクション

1. コミット → push → `gh pr create --base main`（`Closes #23`）。
2. ユーザー承認後マージ。マージ後、本タスクを archive へ移動。
3. 残: #24（Actions Node24 化）、original_format_panel / app の広範テスト + omit 解除判断。
