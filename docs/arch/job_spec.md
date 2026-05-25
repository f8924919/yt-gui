# `job_spec.py`

> 関連仕様: [ダウンロード形式](../spec/features/download-formats.md) / [ダウンロード動作](../spec/features/download-behavior.md)

ダウンロードジョブの実行設定を表す DTO と、`format_id → 設定一式` の派生ロジックを **1 箇所に集約する pure function** を提供する。UI 依存ゼロ。

リファクタ前は同じラダー (format_id ごとの `format_spec` / `embed_thumbnail` / `audio_codec` / `mp3_bitrate` / `video_container` / `embed_metadata` / `embed_chapters` の決定) が `app.py` の `_add_url` / `_apply_edit` / `_enqueue_playlist` の 3 箇所に重複しており、微妙な挙動差 (例: 編集と追加で `mp3_bitrate` の有無が分岐) が発生していた。本モジュールはそれを `build_job_spec()` 1 関数に集約する。

## 提供するクラス・関数

| 名前 | 役割 |
|---|---|
| `JobSpec` (`@dataclass(frozen=True)`) | 1 ジョブの実行設定。`Downloader.download_video()` の入力 |
| `PanelSnapshot` (`@dataclass(frozen=True)`) | `OriginalFormatPanel.get_snapshot()` が返す UI 非依存スナップショット |
| `build_job_spec(format_id, settings, *, panel=None, mp3_thumb_check=False)` | format_id から JobSpec を組み立てる pure function |

### `JobSpec` の主要プロパティ

| プロパティ | 型 | 説明 |
|---|---|---|
| `format_id` | `str` | 形式 ID (`fmt_best_mp4` / `fmt_720p` / `fmt_mp3` / `fmt_original`) |
| `format_spec` | `str` | yt-dlp 形式セレクタ (常に解決済み)。downloader は fallback ロジックを持たない |
| `subtitle_opts` | `dict \| None` | 字幕オプション (`writesubtitles` / `embed` / `subtitleslangs` 等) |
| `embed_thumbnail` | `bool` | サムネ埋め込み |
| `embed_metadata` | `bool` | メタデータ埋め込み |
| `embed_chapters` | `bool` | チャプタ埋め込み |
| `audio_codec` | `str` | `mp3` / `flac` (audio_only / fmt_mp3 のときのみ有効) |
| `mp3_bitrate` | `str \| None` | mp3 ビットレート (mp3 抽出時のみ) |
| `video_container` | `str` | コンテナ。複数音声時は `mkv` へ昇格済み |
| `audio_only` | `bool` | 音声のみ出力 (fmt_mp3 または fmt_original + 音声のみ) |
| `remux_only` | `bool` | コンテナのみ変換 (再エンコ無し) |
| `orig_settings` | `dict \| None` | panel snapshot の raw dict (復元・nico_comments 取り出し用) |
| `is_multi_audio` | `bool` | 複数音声ストリーム結合モード (downloader 側の `allow_multiple_audio_streams` 制御) |
| `is_audio_extraction` (property) | `bool` | `audio_only or format_id == "fmt_mp3"` の派生プロパティ |

### `build_job_spec` の入力

| 引数 | 型 | 説明 |
|---|---|---|
| `format_id` | `str` | UI のフォーマットコンボから選ばれた ID |
| `settings` | `Settings` | アプリ設定 (解像度・コンテナ・音声形式・ビットレート) |
| `panel` | `PanelSnapshot \| None` | `fmt_original` のとき必須。`OriginalFormatPanel.get_snapshot()` の返り値 |
| `mp3_thumb_check` | `bool` | `fmt_mp3` のときのサムネ埋め込みチェック状態。他形式では無視 |

`fmt_original` 以外で `panel` を渡しても無視される。`fmt_original` で `panel=None` のときは `ValueError`。

### `PanelSnapshot` の構造

```python
@dataclass(frozen=True)
class PanelSnapshot:
    format_spec: str              # panel.get_format_spec() の結果
    subtitle_opts: dict | None    # panel.get_subtitle_opts()
    remux_only: bool
    audio_only: bool
    embed_thumbnail: bool
    embed_metadata: bool
    embed_chapters: bool
    has_multiple_audio: bool      # panel.has_multiple_audio_selected()
    raw_settings: dict            # panel.get_raw_settings() の dict (復元用)
```

## 振る舞いの不変条件

- **`fmt_original` で `panel.has_multiple_audio=True` かつ通常結合モード (audio_only / remux_only 共に False) のとき、`video_container` を `mkv` へ自動昇格する**。`is_multi_audio=True` も同時にセットされる。
- **`mp3_bitrate` は mp3 抽出時 (`is_audio_extraction and audio_codec == "mp3"`) のみセット**。それ以外は `None`。
- **`embed_thumbnail` は fmt_mp3 で `audio_codec != "mp3"` (= flac) のとき強制 False**。flac には埋め込めないため。
- **コンテナ昇格・「音声のみ × 複数音声 → 先頭のみ採用」の通知はこの関数の責務外**。UI 側 (`App._notify_*`) が `JobSpec` を見て emit する。

## 呼び出し側 (`app.py`)

| 呼び出し元 | 用途 |
|---|---|
| `App._add_url` | URL 追加時。fmt_original のときは panel snapshot を渡す。それ以外は `mp3_thumb_check` を渡す |
| `App._apply_edit` | 編集モードで適用ボタンを押したとき。同上 |
| `App._on_fetch_for_add_done` (playlist 経路) | プレイリスト追加時。`_add_url` で組み立てた JobSpec を全エントリで共有 |

`_QueueItem` は `JobSpec` を 1 フィールドとして埋め込み、`format_id` はプロパティ経由 (`item.job.format_id`) で取得する。

## downloader との関係

`Downloader.download_video(url, job, cookies_path, *, output_dir_override=None, cookies_browser=None, playlist_title=None, playlist_index=None)` は `JobSpec` を直接受け取る。詳細は [downloader.md](downloader.md)。

## テスト

`tests/test_job_spec.py` に 17 ケースのテーブルテスト。形式別の派生値と複数音声時の MKV 昇格・audio_only 時のビットレート抑制などを固定化する。
