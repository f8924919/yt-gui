# yt_gui/log_dialog.py

> 関連仕様: [ログダイアログ](../spec/screens/log-dialog.md)

## クラス: `LogDialog(QDialog)`

非モーダルのログ表示ダイアログ。

## ウィジェット

- `QPlainTextEdit`（`setReadOnly(True)`、ダーク背景・等幅フォント）

## 主要メソッド

| メソッド | 説明 |
|----------|------|
| `load(entries)` | 既存ログを一括ロード |
| `append(text)` | 逐次追記 |

## 自動スクロールの条件

`verticalScrollBar().value() == verticalScrollBar().maximum()` のときのみ最下部に追従。上にスクロール中は追従しない。

## クリアボタンの動作

テキストエリアのみ消去する。`App._log_entries`（ソースデータ）は変更しない。

## クローズ時の処理

`on_close` コールバックで `App._log_dialog` を `None` にリセットする（次回開くときに新インスタンスを生成するため）。
