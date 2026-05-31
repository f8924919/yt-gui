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
| `concurrent_fragments` | `int` | 並列フラグメント DL 数（既定: `1` = 単一フラグメント）。`>1` のときだけ `concurrent_fragment_downloads` を渡す |
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

#### `missing_dependencies() -> list[str]`

同梱バイナリ (`ffmpeg` / `ffprobe` / `deno`) のうち存在しないものの名前を返す。空リストなら全部揃っている。`app.py` の起動時依存チェックがこれを使う（private 属性 `_ffmpeg_path` 等への直接アクセスは廃止）。

#### `download_video(url, job, cookies_path=None, *, output_dir_override=None, cookies_browser=None, playlist_title=None, playlist_index=None) -> None`

ダウンロードを実行する。実行設定は `JobSpec` ([job_spec.md](job_spec.md)) に集約済みで、`format_spec` / `audio_codec` / `video_container` / `embed_*` / `remux_only` / `audio_only` / `mp3_bitrate` / `subtitle_opts` / `is_multi_audio` などはすべて `job` 経由で受け取る。downloader 側では format_id ごとの fallback ロジックは持たない。

内部は 3 ヘルパに分割されている:

| ヘルパ | 責務 |
|---|---|
| `_build_ydl_opts(job, *, out_dir, is_playlist, cookies_path, cookies_browser)` | `JobSpec` から `ydl_opts` dict を組み立てる純粋関数。`_append_audio_postprocessors` / `_append_video_postprocessors` / `_append_subtitle_options` の 3 サブヘルパに分岐 |
| `_resolve_unique_path(ydl_opts, url, job, *, extra_info)` | 同名ファイル衝突を避けるため `(stem, final_ext)` を予測し、必要なら `outtmpl` を ` (N)` 付きに上書きする |
| `_run_download(ydl_opts, url, job, *, extra_info)` | `YoutubeDL` 起動とダウンロード実行。json 専用字幕の strip PP 順序操作もここに集約 |

`_build_ydl_opts` は副作用がないため [`tests/test_downloader.py`](../testing/index.md) で表ベースの単体テストを行う。

主要引数:

| 引数 | 型 | 説明 |
|------|----|------|
| `url` | `str` | ダウンロード対象 URL |
| `job` | `JobSpec` | 実行設定 ([job_spec.md](job_spec.md)) |
| `cookies_path` | `str \| None` | cookies.txt のパス |
| `cookies_browser` | `str \| None` | ブラウザ名 (指定時は cookies_path より優先) |
| `output_dir_override` | `str \| None` | デフォルト出力先を上書きする場合に指定 |
| `playlist_title` | `str \| None` | プレイリスト名（指定時はプレイリスト用テンプレートを採用し `extra_info` 経由で `%(playlist_title)s` を解決） |
| `playlist_index` | `int \| None` | プレイリスト内番号（`%(playlist_index)s` の解決に使用） |

ニコニコ動画コメント関連オプションは `job.orig_settings["nico_comments"]` から読み出す。

### 複数音声ストリーム対応

`job.is_multi_audio=True` のとき以下を自動付与する:

- `ydl_opts["allow_multiple_audio_streams"] = True`
- `job.video_container` は `build_job_spec` 側で既に `mkv` へ昇格済み (`merge_output_format` も MKV になり、ファイル拡張子計算も `.mkv` に整合する)

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

- ffmpeg を subprocess で実行: `-i {video} -i {ass} -map 0 -map 1 -c copy -c:s ass -metadata:s:s:0 title={t("nico_group_title")} -metadata:s:s:0 language=jpn {out}`
- 字幕トラック名は UI 言語に追従させるため `t("nico_group_title")` を用いる（`language=jpn` はコメント本文の言語コードなので固定）
- 処理中のログ出力（生成完了・スキップ・失敗）はすべて i18n キー経由（`status_danmaku2ass_created` / `warn_nico_ass_skip_no_json` / `warn_nico_mkv_skip_missing` / `warn_nico_mkv_skip_no_ffmpeg` / `warn_nico_mkv_failed` 等）
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

### 並列フラグメントダウンロード

`self.concurrent_fragments` が `> 1` のとき、`_build_ydl_opts` で `ydl_opts["concurrent_fragment_downloads"] = N` を付与する（yt-dlp CLI の `--concurrent-fragments` / `-N` 相当）。`N=1` は yt-dlp 既定と同じなので opt は渡さない。フラグメント分割される動画（DASH / HLS）でのみ高速化に寄与し、プログレッシブ単一ファイルには影響しない。`_base_ydl_opts` ではなくダウンロード側 (`_build_ydl_opts`) に置くため、メタデータ取得 (`fetch_*`) には付与されない。

設定変更は `App._open_settings()` から `self.downloader.concurrent_fragments = ...` で即時反映され、次のジョブから反映される（既存キューアイテムのスナップショットには含めない）。

### ロガー: `_YtdlpLogger`

yt-dlp の `logger` インタフェース実装。`[debug] ` プレフィックスのメッセージとダウンロード進捗行（`[download]  \d`）をスキップし、意味のあるログのみ `log_callback` へ渡す。
