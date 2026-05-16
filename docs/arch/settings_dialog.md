# yt_gui/settings_dialog.py

> 関連仕様: [設定ダイアログ](../spec/screens/settings-dialog.md)

## クラス: `SettingsDialog(QDialog)`

モーダルの設定ダイアログ。`setFixedSize(480, 355)`。

## タブ構成（`QTabWidget`）

### 「一般」タブ

| 項目 | ウィジェット | 説明 |
|------|------------|------|
| 保存フォルダ | `QLineEdit` + `QFileDialog` | ダウンロード先パス |
| Cookies ソース | `QRadioButton` グループ | 使用しない / ファイルを指定 / ブラウザから取得 |
| Cookies ファイル | `QLineEdit` + `QFileDialog` | ファイル指定時のみ表示（`setVisible()`） |
| ブラウザ選択 | `QComboBox` | ブラウザ指定時のみ表示（`setVisible()`） |
| 言語 | `QComboBox` | 変更を即時反映（再起動不要） |

Cookies の排他表示: `_cookies_btn_group.buttonClicked` → `_on_cookies_source_changed()` で `setVisible()` を切り替え。保存時は非選択側のフィールドを空文字にリセット。

言語変更の即時反映: `accept()` 後に `App._retranslate_ui()` を呼び出す。

### 「画質・音質」タブ

| 項目 | ウィジェット | 選択肢 |
|------|------------|--------|
| 解像度上限 | `QComboBox` | 480p 〜 2160p |
| 映像コンテナ | `QComboBox` | MP4 / MKV / WebM（`VIDEO_CONTAINERS` と連動） |
| 音声形式 | `QComboBox` | MP3 / FLAC |
| MP3 ビットレート | `QComboBox` | 128 〜 320kbps（MP3 選択時のみ表示） |

## 保存フロー

1. 各ウィジェットの値を `Settings` に書き込む
2. `SettingsManager.save()` を呼ぶ
3. `self.accept()` でダイアログを閉じる
4. 呼び出し元（`App._open_settings()`）が `_retranslate_ui()` と `retranslate(video_container)` を呼ぶ
