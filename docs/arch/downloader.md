# yt_gui/downloader.py

> 関連仕様: [ダウンロード動作](../spec/features/download-behavior.md) ・ [ダウンロード形式](../spec/features/download-formats.md)

yt-dlp のラッパー。バックグラウンドスレッドから呼び出される。

## クラス: `Downloader`

### コンストラクタ引数

| 引数 | 型 | 説明 |
|------|----|------|
| `output_dir` | `str` | デフォルト出力先 |
| `video_resolution` | `str` | 解像度上限（例: `"720"`） |
| `mp3_bitrate` | `str` | MP3 ビットレート（例: `"192"`） |
| `output_template_video` | `str` | 単独動画用 outtmpl（既定: `"%(title)s.%(ext)s"`） |
| `output_template_playlist` | `str` | プレイリスト用 outtmpl（既定: `"%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"`） |
| `status_callback` | `Callable` | ダウンロード進捗を受け取るコールバック |
| `log_callback` | `Callable` | ログ文字列を受け取るコールバック |

### 主要メソッド

#### `fetch_title_or_entries(url, ...) -> dict`

URL 種別を判別して返す。

```python
# 単一動画
{'type': 'single', 'url': str, 'title': str, 'thumbnail_url': str | None}

# プレイリスト
{'type': 'playlist', 'entries': [{'url': str, 'title': str, 'thumbnail_url': str | None}, ...], 'title': str}
```

#### `fetch_formats(url, ...) -> dict`

フォーマット一覧を返す。キー: `"title"` / `"video"` / `"audio"` / `"subtitles"`。

`info["formats"]` の各エントリを `vcodec` / `acodec` で分類して映像/音声リストに振り分ける。両方が `None` (= 抽出器がコーデック情報を埋めなかった直接 URL の形式、例: xvideos の `flv` / `urllow` / `urlhigh`) の場合は **muxed メディア** とみなし、映像リストへ `has_audio=True` で登録する（音声コンボでは「映像に含まれます」表示になる）。これにより、コーデック情報を返さない抽出器でもオリジナル形式の選択肢が空にならない。

#### `download_video(url, format_id, ...) -> None`

ダウンロードを実行する。主要オプション:

| 引数 | デフォルト | 説明 |
|------|-----------|------|
| `audio_codec` | `"mp3"` | 音声コーデック |
| `video_container` | `"mp4"` | 映像コンテナ |
| `embed_metadata` | `False` | メタデータ埋め込み |
| `embed_chapters` | `False` | チャプター埋め込み |
| `remux_only` | `False` | リマックスのみ（再エンコードなし） |
| `playlist_title` | `None` | プレイリスト名（指定時はプレイリスト用テンプレートを採用し `extra_info` 経由で `%(playlist_title)s` を解決） |
| `playlist_index` | `None` | プレイリスト内番号（`%(playlist_index)s` の解決に使用） |

## 内部詳細

### サムネイル埋め込み対応コンテナ

`_THUMBNAIL_EMBED_CONTAINERS`: mp3, mkv, mka, ogg, opus, flac, m4a, mp4, m4v, mov  
WebM は非対応のため自動スキップ。

### 同名ファイルの衝突回避

同名ファイルが存在する場合は `(n)` サフィックスを付けて保存（MP4/MKV/WebM 全コンテナ対応）。

### OUTPUT TEMPLATE の適用

`outtmpl` は `os.path.join(out_dir, template)` で組み立てる。プレイリスト要素のダウンロード時は `extract_info(url, extra_info={...})` でプレイリスト名・番号を yt-dlp の `info_dict` に注入し、`%(playlist_title)s` / `%(playlist_index)s` を解決する。テンプレートがサブフォルダ（`/`）を含む場合は yt-dlp が自動でディレクトリを作成する。

### ポストプロセッサの順序

- **音声**: FFmpegExtractAudio → FFmpegMetadata → EmbedThumbnail
- **映像**: FFmpegMetadata → EmbedThumbnail → FFmpegEmbedSubtitle

### バイナリパス解決

| バイナリ | パス |
|----------|------|
| ffmpeg | `bin/ffmpeg/ffmpeg[.exe]` |
| ffprobe | `bin/ffmpeg/ffprobe[.exe]` |
| deno | `bin/deno[.exe]` |

PyInstaller バンドル時は `sys._MEIPASS` 直下、開発時は `bin/` サブディレクトリ。

### Cookies

`cookies_path`（ファイルパス）と `cookies_browser`（ブラウザ名）の両方に対応。両方指定時はブラウザ優先。

### ロガー: `_YtdlpLogger`

yt-dlp の `logger` インタフェース実装。`[debug] ` プレフィックスのメッセージとダウンロード進捗行（`[download]  \d`）をスキップし、意味のあるログのみ `log_callback` へ渡す。
