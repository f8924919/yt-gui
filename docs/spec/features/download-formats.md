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
- 音声は multi-select 対応。複数選択時は `+` で連結した format 文字列 (例: `bestvideo+251+140`) が生成され、`Downloader` 側で `allow_multiple_audio_streams: True` と `merge_output_format: "mkv"` が自動付与される
- 出力形式ラジオで「音声のみ」を選んだ場合は `Downloader.download_video()` の `audio_only=True` 経路に乗り、`fmt_mp3` と同じ `FFmpegExtractAudio` ポストプロセッサで MP3 / FLAC に変換する。音声形式・MP3 ビットレートはアプリ設定 (`audio_format` / `mp3_bitrate`) を流用する。音声のみモードでは複数音声選択を許容するが**先頭の 1 件のみ使用**（フェーズ 1 制約）
- 出力形式ラジオで「H.264 MP4 に再変換（互換性優先）」を選んだ場合は `JobSpec.recode_video=True` となり、`FFmpegVideoConvertor`（`--recode-video mp4` 相当）で映像を H.264 / 音声を AAC に**再エンコード**して常に MP4 を出力する。コーデックは `postprocessor_args` の `videoconvertor` キーで `-c:v libx264 -c:a aac` を明示し、互換性を保証する。配信元コンテナに関わらず再エンコードを確実に走らせるため、中間コンテナを `mkv` に固定してから MP4 へ変換する（詳細は [downloader.md](../../arch/downloader.md#映像の再エンコードh264-mp4互換性優先) を参照）。複数音声を選択した場合は MP4 が複数音声トラックを保持できるため、各トラックを AAC へ再エンコードしたうえで保持する（先頭のみへの制限はしない）

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

---

## アイテム単位の形式上書き（ブラウザ拡張連携）

通常、解像度・コンテナ・音声形式・MP3 ビットレートはアプリのグローバル設定から決まります。ただし[ブラウザ拡張連携](browser-extension.md#形式指定オブジェクトformat)から形式を指定して追加した場合は、**そのキューアイテムにのみ**以下を上書き適用します（グローバル設定は変更しない）。

| 拡張の `kind` | アイテムに反映する形式 | 上書きするパラメータ |
|---|---|---|
| `best` | `fmt_best_mp4` | なし（コンテナはアプリ設定） |
| `resolution` | `fmt_720p` | `resolution` |
| `audio` | `fmt_mp3` | `audio_format`(mp3/flac) ・ `mp3_bitrate` |

`audio_format` は従来グローバル設定のみでしたが、拡張からの `kind: audio` 指定時に限りアイテム単位の上書きを許容します。値は許可値（[設定値の選択肢](#設定値の選択肢)）へクランプし、コンテナは拡張から指定できません。実装は [`resolve_extension_format`](../../arch/formats.md) と [`build_job_spec`](../../arch/job_spec.md)（実効 `Settings` を `dataclasses.replace` で生成）が担います。
