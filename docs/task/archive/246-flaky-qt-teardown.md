# #246 CI の Qt ウィジェット遅延破棄フレーク SIGABRT 対策

- Issue: https://github.com/f8924919/yt-gui/issues/246
- ブランチ: `bugfix/246-flaky-qt-teardown`
- ステータス: 完了（2026-07-12）

## 背景

#245 マージ後の main の Test（ubuntu / Python 3.14）で、先行テストのウィジェット遅延破棄（DeferredDelete）が後続テストのイベントループ中に実行され、glibc の free 異常（SIGABRT）でクラッシュ。再実行で pass する非決定的フレーク。

## 方針（決定済み）

1. **主対策**: conftest の autouse フィクスチャ（qt マーカー限定）の teardown で `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` を呼び、遅延破棄をテスト内で消化する。pytest-qt の close/deleteLater は teardown フック（fixture finalizer より前）で走るため、fixture teardown は必ずその後になる（順序保証は pytest-qt のフック構造による）。
2. **補助対策**: `_bind_header_column` が `headerItem()` の参照をクロージャで保持するのをやめ、適用時に都度取得する。

## 調査で得た正本情報

- pytest-qt: `plugin.py:195-211` の `pytest_runtest_teardown`（wrapper, trylast）で `_process_events()` → `_close_widgets()` → `_process_events()` → yield（fixture finalizer 群）→ `_process_events()`。**DeferredDelete の明示 flush はない**。
- `qtbot.addWidget` は weakref 登録のみ（`qtbot.py:204-222`）、クリーンアップは `w.close()` → `w.deleteLater()`（`qtbot.py:797-810`）。
- テスト内のウィジェット生成はすべて `qtbot.addWidget` 経由。`exec()` で開かれる子ダイアログは親の破棄カスケード依存。
- `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` は PySide6 で利用可能。
- `qapp` は session スコープで共有 → 積み残しが次テストへ漏れる土台。

## 進捗

- [x] Issue 起票（#246）
- [x] ブランチ作成
- [x] 調査（investigate）
- [x] 受け入れ条件レビュー（criteria-review → flush 機構の決定論的テスト追加・コメント要件の具体化・qt マーカー必須注記を採用し Issue 更新）
- [x] docs 先行（testing/policy.md §2.5・arch/app.md）
- [x] 設計レビュー（design-review → flush 1 回呼び切り・helper は conftest 内・主/補助のコミット分離を採用）
- [x] テスト先行（tests/test_conftest.py: deleteLater → flush → destroyed の決定論的検証 3 本）
- [x] 実装 → green（ruff / format / mypy / pytest 480 件）
- [x] verify-gate → PR

## 実装サマリ

- 主対策（コミット 1/2）: conftest に `flush_deferred_deletes` ヘルパ＋autouse フィクスチャ `_flush_qt_deferred_deletes`（qt マーカー限定）。teardown で `sendPostedEvents(None, DeferredDelete)` を 1 回呼び、遅延破棄をテスト境界内で消化。順序保証の根拠（pytest-qt のフック構造）はコードコメントに明記。
- 補助対策（コミット 2/2）: `_bind_header_column(col, key)` 化。ヘッダー項目参照をクロージャで保持せず `headerItem()` を都度取得。
