# yt_gui/settings_dialog.py

> 関連仕様: [設定ダイアログ](../spec/screens/settings-dialog.md)

## クラス: `SettingsDialog(QDialog)`

モーダルの設定ダイアログ。`setFixedSize(520, 520)`。

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

### 「ファイル名」タブ

OUTPUT TEMPLATE 設定を編集する。

| 項目 | ウィジェット | 説明 |
|------|------------|------|
| 単独動画 | `QLineEdit` + `QToolButton` | テンプレート入力。挿入ボタンで変数挿入 |
| 単独動画プレビュー | `QLabel` | `output_template.render_preview()` を `textChanged` で呼び出し更新 |
| プレイリスト | `QLineEdit` + `QToolButton` | 同上 |
| プレイリストプレビュー | `QLabel` | 同上 |
| デフォルトに戻す | `QPushButton` | 両入力欄を `DEFAULT_*_TEMPLATE` にリセット |
| よく使うフィールド凡例 | `QLabel` 群 | `TEMPLATE_FIELDS` から生成 |
| 公式ドキュメントを開く | `QPushButton` | `QDesktopServices.openUrl` で yt-dlp の README を表示 |

挿入メニューと凡例は同じ `TEMPLATE_FIELDS`（`yt_gui/output_template.py`）から生成する。

### 「ダウンロード」タブ

ダウンロード挙動の設定をまとめるタブ（`_build_download_tab`）。

| 項目 | ウィジェット | 説明 |
|------|------------|------|
| 並列フラグメント数 | `QSpinBox` | 範囲 `CONCURRENT_FRAGMENTS_MIN`〜`CONCURRENT_FRAGMENTS_MAX`（= 1〜16、`yt_gui/settings.py`）。`Downloader.concurrent_fragments` に反映 |
| 速度制限 | `QDoubleSpinBox`（`_rate_limit_spin`）＋ `QComboBox`（`_rate_limit_unit_combo`） | 値は 0〜`RATE_LIMIT_VALUE_MAX`、単位は `RATE_LIMIT_UNITS`（KB/s / MB/s）。`0` = 無制限。`build_rate_limit()` で bytes/sec に換算し `Downloader.rate_limit` に反映 |

読み込み時は並列フラグメント数の永続値を範囲内にクランプして `setValue()` する（範囲外の手書き JSON に対する防御）。速度制限値も同様にクランプする。保存時は単位コンボの現在インデックスから `RATE_LIMIT_UNITS` の内部値を書き込む。

### 「SponsorBlock」タブ

SponsorBlock の処理方法・対象カテゴリを設定するタブ（`_build_sponsorblock_tab`）。

| 項目 | ウィジェット | 説明 |
|------|------------|------|
| 処理方法 | `QRadioButton` グループ（`_sb_btn_group`） | 使用しない / 印を付ける（mark）/ 除去する（remove） |
| 対象カテゴリ | `QCheckBox` 群（`_sb_category_checks: dict[str, QCheckBox]`） | `SPONSORBLOCK_CATEGORIES`（`yt_gui/settings.py`）から生成 |

- グレーアウト連動: `_sb_btn_group.buttonClicked` → `_on_sponsorblock_mode_changed()` で「使用しない」選択時にカテゴリラベルとチェックボックス群を `setEnabled(False)`。
- 保存時は mark / remove / 無効を `sponsorblock_mode` に、チェック済みカテゴリのリストを `sponsorblock_categories` に書き込む。

### 「プロキシ」タブ

| 項目 | ウィジェット | 説明 |
|------|------------|------|
| プロキシを有効にする | `QCheckBox` | OFF のとき他項目をグレーアウト（`_on_proxy_toggled`） |
| プロトコル | `QComboBox` | `PROXY_SCHEMES`（http / https / socks4 / socks5 / socks5h） |
| ホスト | `QLineEdit` | プロキシのホスト名 / IP |
| ポート | `QLineEdit` + `QIntValidator(1, 65535)` | 空欄可 |
| ユーザー名 / パスワード | `QLineEdit` | パスワードは `EchoMode.Password` |

## 保存フロー

1. 「ファイル名」タブのテンプレートを `validate_template()` で検証。エラー時は警告ダイアログを表示し、該当タブに切り替えてダイアログを閉じない
2. 各ウィジェットの値を `Settings` に書き込む
3. `SettingsManager.save()` を呼ぶ
4. `self.accept()` でダイアログを閉じる
5. 呼び出し元（`App._open_settings()`）が `_retranslate_ui()` と `retranslate(video_container)` を呼ぶ
