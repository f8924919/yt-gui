# ダウンロード形式

[← 目次](../index.md)

> 関連実装: [yt_gui/formats.py](../../arch/formats.md) ・ [yt_gui/downloader.py](../../arch/downloader.md)

## 概要

ダウンロード形式は `formats.py` で定義されます。各形式は内部キー（`FORMAT_KEYS`）と yt-dlp フォーマット文字列（`FORMAT_SPECS`）を持ちます。

---

## 形式一覧

| 内部キー | 表示名（テンプレート） | 音声のみ | 説明 |
|---|---|---|---|
| `fmt_best_mp4` | `最高画質 ({container}に結合)` | No | 最高品質の映像＋音声をコンテナにマージ |
| `fmt_720p` | `{resolution}p ({container}に結合)` | No | 指定解像度以下の映像＋音声をコンテナにマージ |
| `fmt_mp3` | `MP3 (音声のみ・{bitrate}kbps)` または `FLAC (音声のみ)` | Yes | 音声のみを MP3/FLAC として抽出 |
| `fmt_original` | `オリジナルの形式` | No | 映像/音声トラックを個別選択してダウンロード |

表示名のプレースホルダー（`{container}` 等）は設定値で埋めて表示します（`App._build_format_display()` が担当）。

---

## フォーマット文字列生成

### 最高画質（`fmt_best_mp4`）— `build_best_spec(container)`

| コンテナ | フォーマット文字列 |
|---|---|
| `mp4` | `bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best` |
| `mkv` | `bestvideo+bestaudio/best` |
| `webm` | `bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best` |

### 解像度指定（`fmt_720p`）— `build_720p_spec(resolution, container)`

| コンテナ | フォーマット文字列 |
|---|---|
| `mp4` | `bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={resolution}]+bestaudio/best` |
| `mkv` | `bestvideo[height<={resolution}]+bestaudio/best` |
| `webm` | `bestvideo[height<={resolution}][ext=webm]+bestaudio[ext=webm]/bestvideo[height<={resolution}]+bestaudio/best` |

`{resolution}` は設定値（480 / 720 / 1080 / 1440 / 2160）。

### 音声のみ（`fmt_mp3`）

- フォーマット文字列: `bestaudio/best`
- ポストプロセッサで `FFmpegExtractAudio` を適用し `mp3` または `flac` に変換
- MP3 ビットレートはアイテムの `mp3_bitrate` で個別指定

### オリジナル形式（`fmt_original`）

- フォーマット文字列はパネルの選択状態から動的生成（`OriginalFormatPanel.get_format_spec()` が担当）
- 生成ロジックの詳細は [オリジナル形式パネル — フォーマット文字列生成ロジック](../screens/original-format-panel.md#フォーマット文字列生成ロジック) を参照
- 出力形式ラジオで「音声のみ」を選んだ場合は `Downloader.download_video()` の `audio_only=True` 経路に乗り、`fmt_mp3` と同じ `FFmpegExtractAudio` ポストプロセッサで MP3 / FLAC に変換する。音声形式・MP3 ビットレートはアプリ設定 (`audio_format` / `mp3_bitrate`) を流用する。

---

## 設定値の選択肢

`formats.py` で定義されています。

| 定数 | 値 |
|---|---|
| `VIDEO_RESOLUTIONS` | `("480", "720", "1080", "1440", "2160")` |
| `MP3_BITRATES` | `("128", "192", "256", "320")` |
| `AUDIO_FORMATS` | `("mp3", "flac")` |
| `VIDEO_CONTAINERS` | `("mp4", "mkv", "webm")` |

---

## デフォルト値

| 設定 | デフォルト |
|---|---|
| 解像度上限 | 720p |
| 映像コンテナ | MP4 |
| 音声形式 | MP3 |
| MP3 ビットレート | 192 kbps |

---

## 音声形式と表示名の切り替え

`fmt_mp3` キーは音声形式の設定に応じて表示名を切り替えます。

| 音声形式設定 | 表示名 |
|---|---|
| `mp3` | `MP3 (音声のみ・192kbps)` |
| `flac` | `FLAC (音声のみ)` |

MP3 サムネイル埋め込みチェックボックスは、音声形式が `mp3` のときのみ表示されます（FLAC では非表示）。
