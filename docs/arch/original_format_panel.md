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
| 音声リスト | `_AudioListWidget`（`_ToggleListWidget` 派生、`ExtendedSelection`、最低 4 行表示）。multi-select 対応 |
| 字幕リスト | `QListWidget`（`ExtendedSelection`、最低4行表示） |
| 字幕フォーマットコンボ | 字幕出力形式 |
| サムネイル埋め込みチェック | |
| メタデータ埋め込みチェック | デフォルト ON |
| チャプター埋め込みチェック | デフォルト ON |
| 出力形式ラジオグループ | コンテナ結合 / remux のみ / 音声のみ の 3 択 |
| ニコニコ動画コメントグループ | `QGroupBox`（`comments` lang が字幕リストに含まれるときだけ可視化）。コメント ASS 変換チェック + 解像度/表示時間/不透明度/フォントサイズの SpinBox |

複合フォーマット（★印）選択時は音声リストを `set_included_mode()` で「映像に含まれます」1 行表示に切り替え、`setEnabled(False)` で操作不可にする。

## 内部クラス: `_AudioListWidget`

`_ToggleListWidget` を継承した音声選択用 multi-select リスト。`set_normal_mode()` / `set_included_mode()` の 2 状態を持ち、後者は複合フォーマット映像が選ばれているときに 1 行表示で無効化される。

排他ロジック (`_enforce_exclusivity`):

- 「自動」と他 (skip / 音声 ID) が同時選択されたら「自動」を解除
- 「ダウンロードしない」と音声 ID が同時選択されたら「ダウンロードしない」を解除

公開ヘルパ: `select_auto()` / `select_skip()` / `select_audio_rows(rows)` / `get_selection() -> (auto, skip, rows)` / `is_included_mode()`

## フォーマット取得結果の分岐

| 結果 | 表示 |
|------|------|
| 通常成功 | フォーマットを各コンボに展開し、`status_formats_loaded` |
| `extract_info` 例外（メッセージに `playlist` を含む） | `warn_fetch_formats_playlist`（プレイリスト誤入力向け） |
| `extract_info` 例外（その他） | `err_fetch_formats`（エラー詳細を表示） |
| 成功したが映像/音声フォーマット 0 件 | `warn_fetch_formats_no_formats`（URL 確認を促す中立メッセージ） |

## 公開 API

| メソッド | 戻り値 | 説明 |
|----------|--------|------|
| `get_format_spec()` | `str` | yt-dlp フォーマット文字列 |
| `get_subtitle_opts()` | `dict` | 字幕オプション |
| `get_remux_only()` | `bool` | リマックスのみフラグ |
| `get_audio_only()` | `bool` | 音声のみ出力フラグ |
| `is_audio_skipped()` | `bool` | 音声コンボが「ダウンロードしない」か |
| `get_embed_metadata()` | `bool` | メタデータ埋め込みフラグ |
| `get_embed_chapters()` | `bool` | チャプター埋め込みフラグ |
| `get_nico_comments_opts()` | `dict` | ニコニコ動画コメント → ASS 変換 / MKV 統合オプション（`convert_to_ass` / `embed_to_mkv` / `auto_resolution` / `resolution_w` / `resolution_h` / `duration_sec` / `opacity` / `font_size`）。`auto_resolution=True` のときは選択中の映像フォーマットの実解像度を `resolution_w/h` に詰めて返す |
| `get_raw_settings()` | `dict` | 現在の設定スナップショット（音声は `audio_ids: list[str]`、ニコニコ動画コメント設定は `nico_comments: dict` を含む） |
| `get_snapshot()` | `PanelSnapshot` | `build_job_spec` ([job_spec.md](job_spec.md)) に渡すための UI 非依存スナップショット。`get_format_spec` / `get_subtitle_opts` / 各 `get_embed_*` / `has_multiple_audio_selected` / `get_raw_settings` を 1 つの dataclass にまとめたもの |
| `restore_from_settings(settings: dict)` | — | 設定を復元する。旧キー `audio_id: str \| None` は後方互換のため受け入れる。`nico_comments` 欠如時はデフォルト値を採用 |
| `has_formats_loaded()` | `bool` | フォーマット取得済みかどうか |
| `get_fetched_title()` | `str` | 取得済みタイトル |
| `is_both_skipped()` | `bool` | 映像・音声ともスキップかどうか |
| `has_multiple_audio_selected()` | `bool` | 音声 ID が 2 件以上選択されているか（MKV 自動昇格の判定用） |
| `trigger_fetch()` | — | フォーマット取得を開始する |
| `reset()` | — | フォーマット取得結果と選択状態を初期状態に戻す（キュー追加成功時 / 編集モード終了時に呼び出される） |
| `retranslate(video_container: str, audio_label: str \| None = None)` | — | 表示文字列を現在の言語・コンテナ設定・音声ラベル（例: `MP3 192kbps`）に更新 |

## 編集モード復元の遅延適用

`_pending_restore: dict | None` で管理。ラジオ・チェックボックスは即時適用、映像/音声/字幕はフォーマット取得完了後に `_apply_pending_restore()` で適用する。

## `retranslate()` の対象

グループタイトル・ラベル・コンボ固定項目テキスト（`orig_output_mp4` などの `{container}` プレースホルダー含む）を更新する。
