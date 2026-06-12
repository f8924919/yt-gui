# モーダル駆動(手段B)のQt UIテスト追加

- Issue: [#132](https://github.com/f8924919/yt-gui/issues/132)
- PR: [#133](https://github.com/f8924919/yt-gui/pull/133)（マージ済み）
- ブランチ: `feature/132-modal-driven-qt-tests`
- ステータス: 完了
- 後続: coverage omit 解除は [#134](https://github.com/f8924919/yt-gui/issues/134) へ分離
- 更新日: 2026-06-12

## 目的

`docs/research/qt-ui-testing-feasibility.md` §8 の「手段B（offscreen + `QTimer` でモーダルを能動的に閉じる）」に基づき、既存テストが届いていない **`exec()` / `QMessageBox.question` / `QFileDialog` を通る経路**を、開く→操作→状態変化まで通しで検証する。UI 品質の継続的なリグレッション検出。追加依存・CI 変更なし（offscreen のまま）。

## スコープ（優先度「高」3対象 = 4テスト群）

| # | 対象 | ファイル | 検証 |
|---|---|---|---|
| 1 | `SettingsDialog._clear_archive` | `tests/test_settings_dialog.py` | `question`→Yes で実ファイル(`tmp_path`)削除＋件数更新＋`information`、No で中断、削除失敗で `warning` |
| 2 | `SettingsDialog._save` 検証分岐 | `tests/test_settings_dialog.py` | テンプレ/プロキシ不正→`warning`＋該当タブへ `setCurrentIndex`（`manager.save` 未呼び出し）、正常→`accept`＋`save` 往復 |
| 3 | `App._open_original_dialog` 追加フロー | `tests/test_app.py` | ダイアログ生成→`add_requested`→`queue.enqueue_single` で1件追加（`exec()` は介さずシグナル直接 emit 推奨） |
| 4 | `App._open_settings` 設定反映ループ | `tests/test_app.py` | `exec` no-op 化＋事前 `save` で `downloader` 各属性へ転写・言語変更で `_retranslate_ui` |

## 設計メモ（investigate #132 の裏取り）

- **SettingsDialog 構築**: `manager = MagicMock(); manager.load.return_value = Settings(...)` を `SettingsDialog(None, manager)` に渡す（`tests/test_settings_dialog.py:26-31`）。`manager.save.called` / `call_args` で保存を検証。
- **App 構築**: `app` fixture（`tests/test_app.py:75-82`）が `HOME=tmp_path`・`Downloader.missing_dependencies` を空返しにモック。設定注入は `app._settings_manager.save(...)` か `app._settings_manager = MagicMock()`。
- **question の Yes 分岐**: autouse `_silence_qt_modal_dialogs` は `question` を `Ok`（=No 扱い）にするため、Yes はテスト内 `monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)` で上書き。
- **タブ index**: `_template_tab_index`（`settings_dialog.py:100`）/ `_proxy_tab_index`（:114）はインスタンス変数を参照（数値ハードコード禁止）。
- **_clear_archive 参照**: `_effective_archive_path`（`settings_dialog.py:477`）・`count_download_archive_entries`（`settings.py:122`）・`default_download_archive_path`（`settings.py:105`）。
- **追加フロー**: `add_requested` は `app.py:802` で `_on_dialog_add_requested`（:832）に接続→`queue.enqueue_single`（`queue_controller.py:141`）。`has_formats_loaded()` を True にして即時 enqueue 経路へ誘導（False は `_start_add_thread` 非同期）。
- **_open_settings**: `SettingsDialog` を内部生成するため差し替え不可→`SettingsDialog.exec` を monkeypatch no-op 化。転写属性は `app.py:1089-1103`。

## 対応 spec

- [設定ダイアログ](../../spec/screens/settings-dialog.md)（削除確認・保存検証・反映）
- [オリジナル形式ダイアログ](../../spec/screens/original-format-dialog.md)（追加フロー）
- [ダウンロードキュー](../../spec/features/queue.md)（追加）

## docs 更新

- `docs/testing/policy.md` §1 スコープ表: `settings_dialog.py` を ×→△、`app.py` 行にモーダル経路（手段B）を追記。§2.5 に手段B駆動の作法を追記。

## スコープ外（別 Issue 候補）

- file picker 反映（`_browse_*`）・ログダイアログ・右クリックメニュー構築（手段A相当・優先度中）
- スクリーンショット/ビジュアル回帰・ネイティブダイアログ（手段C・xvfb）
