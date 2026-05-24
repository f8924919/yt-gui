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
| `proxy_url` | `str` | yt-dlp に渡すプロキシ URL（既定: `""` = 未使用）。`scheme://[user[:password]@]host[:port]` 形式 |
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
| `nico_comments_opts` | `None` | ニコニコ動画コメント → ASS 変換 / MKV 統合オプション（`convert_to_ass` / `embed_to_mkv` / `auto_resolution` / `resolution_w` / `resolution_h` / `duration_sec` / `opacity` / `font_size`）。`convert_to_ass=True` かつ字幕に `comments` lang が含まれる場合、ダウンロード完了後に danmaku2ass を subprocess 呼び出しして `{stem}.comments.ass` を生成する。さらに `embed_to_mkv=True` のときは ffmpeg で `{stem}.with-comments.mkv` を別ファイルとして生成する |

### 複数音声ストリーム対応

`format_spec` に含まれる `+` の個数が **2 個以上**（例: `bestvideo+251+140`、`bv*+251+140` 等）で、かつ音声抽出経路（`is_audio=True`）でない場合は、以下を自動付与する:

- `ydl_opts["allow_multiple_audio_streams"] = True`
- `video_container = "mkv"` に強制（`merge_output_format` も MKV になり、ファイル拡張子計算も `.mkv` に整合する）

サムネイル埋め込み判定の `_THUMBNAIL_EMBED_CONTAINERS` には既に `mkv` が含まれているため、サムネ埋め込み付きでも問題ない。

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
- **映像 (字幕埋め込み無し)**: FFmpegMetadata → EmbedThumbnail
- **映像 (字幕埋め込みあり)**: FFmpegMetadata → EmbedThumbnail → (json 専用字幕を含む場合 `_StripJsonOnlySubsBeforeEmbedPP`) → FFmpegSubtitlesConvertor → FFmpegEmbedSubtitle

字幕埋め込み時は `FFmpegSubtitlesConvertor` を先に挟む。これは `json3` しか配信されない動画で `FFmpegEmbedSubtitle` が `JSON subtitles cannot be embedded` で失敗するのを避けるため。変換先はユーザーが選んだフォーマット（`srt` / `vtt`）。`best` 選択時は `srt` をデフォルトに採用する。

`_JSON_ONLY_SUB_LANGS = {"live_chat", "comments"}` のいずれかがユーザー選択に含まれる場合は、convert/embed の前に `_StripJsonOnlySubsBeforeEmbedPP` を差し込んで `requested_subtitles` から該当 lang を取り除く。これにより、ライブチャット (YouTube) およびニコニコ動画コメント の JSON は通常の writesubtitles でディスクに保存された後、変換・埋め込み対象からは除外され、ffmpeg のエラーや警告が出ない。挿入は `add_post_processor()` 後に `_pps['post_process']` の先頭へ移動して実現している（yt-dlp に公開された prepend API が無いため）。

ニコニコ動画コメント (`comments` lang) は yt-dlp の `NiconicoIE._get_subtitles` が出力する v1/threads JSON。ライブチャットと同じ「json 専用・埋め込み不可」カテゴリとして同一の strip 機構で扱う。

### ニコニコ動画コメントの ASS 変換

`nico_comments_opts.convert_to_ass=True` かつ `subtitle_opts.subtitleslangs` に `comments` が含まれる場合、`extract_info(download=True)` 完了後に `_convert_nico_comments_to_ass(stem, opts)` を呼び出す。実装上の要点:

- yt-dlp が保存する `{stem}.comments.json` をベースに `{stem}.comments.ass` を生成する（`stem` は同名衝突回避の `(n)` サフィックスを含む実効ステム）
- subprocess で `bin/danmaku2ass[.exe] -o {ass} -s {W}x{H} -f NiconicoYtdlpJson2 -dm {sec} -fs {size} -a {opacity} {json}` を実行
- `-f NiconicoYtdlpJson2` は yt-dlp の `v1/threads` JSON 用パーサ（フェーズ 0 で検証済み）
- 失敗（バイナリ欠如・JSON 不在・サブプロセス非 0 終了）はいずれも `log_callback` に警告を流すのみで例外を投げない

### コメント ASS と動画の MKV 統合

`nico_comments_opts.embed_to_mkv=True` かつ ASS 変換が成功した場合、`_embed_nico_comments_into_mkv(stem, final_ext, opts)` を呼び出す。実装上の要点:

- ffmpeg を subprocess で実行: `-i {video} -i {ass} -map 0 -map 1 -c copy -c:s ass -metadata:s:s:0 title=ニコニコ動画コメント -metadata:s:s:0 language=jpn {out}`
- 再エンコードなし (stream copy) のため処理は高速
- 元動画は触らず、別ファイル `{stem}.with-comments.mkv` を生成（同名衝突時は `(n)` サフィックス）
- 「音声のみ」モード (`is_audio=True`) では本処理をスキップ（動画統合の対象外）
- 失敗（ffmpeg 欠如・入力ファイル欠如・サブプロセス非 0 終了）はいずれも非致命でログのみ

### バイナリパス解決

| バイナリ | パス |
|----------|------|
| ffmpeg | `bin/ffmpeg/ffmpeg[.exe]` |
| ffprobe | `bin/ffmpeg/ffprobe[.exe]` |
| deno | `bin/deno[.exe]` |
| danmaku2ass | `bin/danmaku2ass[.exe]` |

PyInstaller バンドル時は `sys._MEIPASS` 直下、開発時は `bin/` サブディレクトリ。danmaku2ass バイナリが欠如している場合は ASS 変換のみがスキップされ、JSON 保存・その他のダウンロードは通常通り動作する（非致命扱い）。

### Cookies

`cookies_path`（ファイルパス）と `cookies_browser`（ブラウザ名）の両方に対応。両方指定時はブラウザ優先。

### プロキシ

`self.proxy_url` が空でない場合、`_base_ydl_opts()` で `opts["proxy"] = self.proxy_url` を付与する。`fetch_title_or_entries` / `fetch_formats` / `download_video`（メタデータ抽出・実ダウンロード）の全 `YoutubeDL` 呼び出しが `_base_ydl_opts()` を経由するため、1 箇所の代入で全経路に反映される。

設定変更は `App._open_settings()` から `self.downloader.proxy_url = build_proxy_url(...)` で即時反映され、次のジョブから新しいプロキシが使われる。

### ロガー: `_YtdlpLogger`

yt-dlp の `logger` インタフェース実装。`[debug] ` プレフィックスのメッセージとダウンロード進捗行（`[download]  \d`）をスキップし、意味のあるログのみ `log_callback` へ渡す。
