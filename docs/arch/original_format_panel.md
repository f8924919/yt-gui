# yt_gui/original_format_panel.py

> 関連仕様: [オリジナル形式パネル](../spec/screens/original-format-panel.md)

## クラス: `OriginalFormatPanel(QGroupBox)`

「オリジナルの形式」選択時に表示される詳細設定パネル。

## シグナル（内部クラス `_PanelSignals(QObject)`）

| シグナル | 引数 | タイミング |
|----------|------|-----------|
| `formats_fetched` | `dict` | フォーマット取得成功時 |
| `fetch_failed` | `str, bool` | フォーマット取得失敗時 |

フォーマット取得はバックグラウンドスレッドで行い、シグナル経由でメインスレッドへ渡す。

## 内包ウィジェット

| ウィジェット | 説明 |
|------------|------|
| 映像コンボ | 映像フォーマット選択 |
| 音声コンボ | 音声フォーマット選択 |
| 字幕リスト | `QListWidget`（`ExtendedSelection`、最低4行表示） |
| 字幕フォーマットコンボ | 字幕出力形式 |
| サムネイル埋め込みチェック | |
| メタデータ埋め込みチェック | デフォルト ON |
| チャプター埋め込みチェック | デフォルト ON |
| 出力形式ラジオグループ | |

複合フォーマット（★印）選択時は音声コンボを `setEnabled(False)` で自動無効化。

## 公開 API

| メソッド | 戻り値 | 説明 |
|----------|--------|------|
| `get_format_spec()` | `str` | yt-dlp フォーマット文字列 |
| `get_subtitle_opts()` | `dict` | 字幕オプション |
| `get_remux_only()` | `bool` | リマックスのみフラグ |
| `get_embed_metadata()` | `bool` | メタデータ埋め込みフラグ |
| `get_embed_chapters()` | `bool` | チャプター埋め込みフラグ |
| `get_raw_settings()` | `dict` | 現在の設定スナップショット |
| `restore_from_settings(settings: dict)` | — | 設定を復元する |
| `has_formats_loaded()` | `bool` | フォーマット取得済みかどうか |
| `get_fetched_title()` | `str` | 取得済みタイトル |
| `is_both_skipped()` | `bool` | 映像・音声ともスキップかどうか |
| `trigger_fetch()` | — | フォーマット取得を開始する |
| `retranslate(video_container: str)` | — | 表示文字列を現在の言語・コンテナ設定に更新 |

## 編集モード復元の遅延適用

`_pending_restore: dict | None` で管理。ラジオ・チェックボックスは即時適用、映像/音声/字幕はフォーマット取得完了後に `_apply_pending_restore()` で適用する。

## `retranslate()` の対象

グループタイトル・ラベル・コンボ固定項目テキスト（`orig_output_mp4` などの `{container}` プレースホルダー含む）を更新する。
