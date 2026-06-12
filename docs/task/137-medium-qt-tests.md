# 優先度中のQt UIテスト追加（ファイル選択・アーカイブトグル・ログダイアログ）

- Issue: [#137](https://github.com/f8924919/yt-gui/issues/137)
- ブランチ: `feature/137-medium-qt-tests`
- ステータス: 進行中
- 更新日: 2026-06-12

## 目的

#132（PR #133）でスコープ外とした優先度「中」のうち、本体コード変更なし（手段A相当）でテスト可能な3対象を追加し、回帰検出範囲を広げる。右クリックメニューは `_edit_targets` で被覆済み＋本体リファクタを要するため対象外（ユーザー確認済み）。

## スコープ

| # | 対象 | ファイル | 検証 |
|---|---|---|---|
| 1 | `_browse_download`/`_browse_cookies`/`_browse_archive` | `tests/test_settings_dialog.py` | `QFileDialog` 静的メソッドを固定値に差し替え→対応フィールドへ反映、空文字でフィールド不変 |
| 2 | `_on_archive_toggled` | `tests/test_settings_dialog.py` | チェック ON/OFF で `_archive_path_edit`/`_archive_browse_btn`/`_archive_clear_btn` の `isEnabled()` 連動 |
| 3 | `_open_log_dialog` / `_on_log_dialog_close` | `tests/test_app.py` | 初回生成+`load`+`show`、表示中の再呼び出しで新規生成せず `raise_`/`activateWindow`、close で `_log_dialog=None` |
| 4 | `LogDialog.load`/`append` | `tests/test_log_dialog.py`（新規） | エントリが `_text.toPlainText()` に反映される表示往復 |

## 設計メモ（investigate #137 の裏取り）

- **ファイル選択**: `_browse_download`→`getExistingDirectory`（単値 str）→`_download_edit`（`settings_dialog.py:674`）。`_browse_cookies`→`getOpenFileName`（タプル `path,_`）→`_cookies_edit`（:679）。`_browse_archive`→`getSaveFileName`（タプル）→`_archive_path_edit`（:498）。
- **アーカイブトグル**: `_on_archive_toggled`（`settings_dialog.py:491-496`）は `enabled = _archive_check.isChecked()` を3ボタンに反映。コンストラクタ末尾（:473）で初期呼び出し済み。
- **ログ開閉**: `_log_dialog` 初期 `None`（`app.py:230`）、`_log_entries` 初期 `[]`（:229）。`_open_log_dialog`（:1131）は visible なら raise/activate で return、否なら `LogDialog(self, on_close=_on_log_dialog_close)`→`load`→`show`。`_on_log_dialog_close`（:1140）は `_log_dialog=None`。
- **LogDialog**: 表示は `self._text`（`QPlainTextEdit`、`log_dialog.py:25`）。`load`=`setPlainText`、`append`=`appendPlainText`。取得は `dialog._text.toPlainText()`。`LogDialog(None, on_close=cb)` で app 無しに単体構築可。
- **テスト作法**: `test_settings_dialog.py` の `_make_dialog`/`_make_dialog_with_manager`（:30-41）、`test_app.py` の `app` fixture（:75-82）を再利用。新規 `test_log_dialog.py` 冒頭は `importorskip` + `pytestmark = pytest.mark.qt`。

## 対応 spec / arch

- [設定ダイアログ](../spec/screens/settings-dialog.md) / [arch](../arch/settings_dialog.md)
- [ログダイアログ](../spec/screens/log-dialog.md) / [arch](../arch/log_dialog.md)
- [メインウィンドウ](../spec/screens/main-window.md) / [arch](../arch/app.md)

## docs 更新

- `docs/testing/policy.md` §1 で `log_dialog.py` を ×→△、`settings_dialog.py` 記述に `_browse_*`/`_on_archive_toggled` を追記。§3 ツリーに `test_log_dialog.py` を追加。

## 留意

- coverage `omit` 解除は #134 と同方針で本タスクでは据え置き（CI 変更なし）。`log_dialog.py` も omit 解除は後続。

## スコープ外

- 右クリックメニュー構築テスト（`_edit_targets` で被覆済み・要本体リファクタ）
- スクリーンショット/ビジュアル回帰（手段C・xvfb）
