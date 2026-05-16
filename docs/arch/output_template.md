# yt_gui/output_template.py

> 関連仕様: [設定管理](../spec/settings.md) ・ [設定ダイアログ](../spec/screens/settings-dialog.md)

OUTPUT TEMPLATE 設定で利用する定数・検証ヘルパを集めたモジュール。

## 定数

| 名前 | 説明 |
|---|---|
| `DEFAULT_VIDEO_TEMPLATE` | 単独動画のデフォルトテンプレート `"%(title)s.%(ext)s"` |
| `DEFAULT_PLAYLIST_TEMPLATE` | プレイリストのデフォルト `"%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"` |
| `YTDLP_OUTPUT_TEMPLATE_DOC_URL` | yt-dlp 公式 OUTPUT TEMPLATE ドキュメントの URL |
| `TEMPLATE_FIELDS` | `(挿入文字列, i18n キーのサフィックス)` のタプル列。挿入メニュー・凡例の両方で使用 |
| `SAMPLE_INFO` | プレビュー描画用のサンプル `info_dict` |

## 関数

| 名前 | 戻り値 | 説明 |
|---|---|---|
| `render_preview(template) -> str \| None` | サンプルで展開した文字列 / `None` | `template % SAMPLE_INFO`。失敗時は `None` |
| `validate_template(template) -> str \| None` | エラー i18n キー / `None` | `%(ext)s` 必須・構文チェック。問題なければ `None` |

## 設計方針

- 「挿入」メニュー項目と「よく使うフィールド」凡例を同一データソース（`TEMPLATE_FIELDS`）から生成し一貫性を保つ
- 高度なフィールド（例: `%(release_date>%Y-%m-%d)s` など yt-dlp 拡張構文）は UI には載せず、公式ドキュメントリンクへ誘導する
