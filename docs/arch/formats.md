# yt_gui/formats.py

> 関連仕様: [ダウンロード形式](../spec/features/download-formats.md)

フォーマット仕様の定数と、yt-dlp フォーマット文字列を生成するユーティリティ。

## 定数

| 定数 | 型 | 内容 |
|------|----|------|
| `FORMAT_SPECS` | `dict[str, tuple[str, bool]]` | 内部キー → `(yt-dlp フォーマット文字列, 音声のみフラグ)` |
| `FORMAT_KEYS` | `list[str]` | UI 表示順のキーリスト |
| `VIDEO_RESOLUTIONS` | `tuple[str, ...]` | `"480"` 〜 `"2160"` |
| `MP3_BITRATES` | `tuple[str, ...]` | `"128"` 〜 `"320"` |
| `AUDIO_FORMATS` | `tuple[str, ...]` | `("mp3", "flac")` |
| `VIDEO_CONTAINERS` | `tuple[str, ...]` | `("mp4", "mkv", "webm")` |

## 関数

### `build_best_spec(container: str) -> str`

コンテナ別の「最高画質」yt-dlp フォーマット文字列を返す。

### `build_720p_spec(resolution: str, container: str) -> str`

解像度上限つきのフォーマット文字列を返す。

## コンテナ別フォーマット文字列の方針

| コンテナ | フォーマット制約 |
|----------|----------------|
| MP4 | `[ext=mp4]+[ext=m4a]` を指定 |
| MKV | コーデック無制限 |
| WebM | `[ext=webm]` 制約 |
