# ダウンロード動作

[← 目次](../index.md)

> 関連実装: [yt_gui/downloader.py](../../arch/downloader.md)

## 概要

`Downloader` クラスが yt-dlp のラッパーとしてダウンロードを実行します。このドキュメントはダウンロードに関する動作仕様（ファイル名・プレイリスト・サムネイル埋め込み・字幕・Cookies）を記載します。

---

## ファイル名

### 基本テンプレート

yt-dlp の `outtmpl` に `%(title)s.%(ext)s` を指定します。拡張子は形式に応じて決まります。

| 形式 | 拡張子 |
|---|---|
| 最高画質 / 解像度指定 | 設定コンテナ（`.mp4` / `.mkv` / `.webm`） |
| MP3 | `.mp3` |
| FLAC | `.flac` |
| オリジナル形式（コンテナ結合） | 設定コンテナ |
| オリジナル形式（remux のみ） | 元のコンテナ |
| オリジナル形式（音声のみ） | `.mp3` または `.flac`（アプリ設定の音声形式に従う） |

### 重複回避

ダウンロード先に同名ファイルが既に存在する場合、上書きせず連番サフィックスを付与します。

```
タイトル.mp4        ← 既存
タイトル (1).mp4    ← 新規（自動リネーム）
タイトル (2).mp4    ← さらに既存なら
```

実装では、ダウンロード実行前に最終ファイルパスを計算して存在チェックを行い、`(n)` サフィックスを決定してから `outtmpl` を上書きします。

---

## プレイリスト

- プレイリスト URL を追加すると全エントリをキューに展開します
- ダウンロード先には **プレイリスト名のサブフォルダ** が自動作成されます
  - 例: `~/Downloads/プレイリスト名/動画タイトル.mp4`
- フォルダ名は以下のルールでサニタイズされます
  - `\ / : * ? " < > |` を `_` に置換
  - 100 文字で截断
  - 空になった場合は `"playlist"` を使用
- `yt_dlp` の `noplaylist: True` オプションを使用し、各エントリを個別ダウンロード

---

## サムネイル

### キュー表示用サムネイル（ツールチップ）

- キューアイテム追加時に `thumbnail_url` をバックグラウンドスレッドで取得
- `urllib.request` で取得し、base64 data URI にエンコードして `_thumbnail_cache` にキャッシュ
- ツールチップに 240×135px の `<img>` タグとして表示
- 取得失敗時は静かに無視（エラーを表示しない）

### ファイルへのサムネイル埋め込み

ダウンロードしたファイルにサムネイルを埋め込む機能です。

| 形式 | 埋め込み方法 | デフォルト |
|---|---|---|
| 最高画質 / 解像度指定 | `EmbedThumbnail` ポストプロセッサ（`writethumbnail: True` と組み合わせ） | ON |
| MP3 | `EmbedThumbnail` ポストプロセッサ（ID3 APIC タグ）| ユーザー選択（チェックボックス） |
| FLAC | サムネイル埋め込み不可 | — |
| オリジナル形式 | `EmbedThumbnail`（remux 時は無効）| ユーザー選択（チェックボックス） |

埋め込みに非対応のコンテナ（WebM）は自動スキップします。`_THUMBNAIL_EMBED_CONTAINERS` で対応コンテナを定義（`mp3`, `mkv`, `mka`, `ogg`, `opus`, `flac`, `m4a`, `mp4`, `m4v`, `mov`）。

---

## 字幕

オリジナル形式パネルで字幕を選択した場合に適用されます。

| 設定 | yt-dlp オプション |
|---|---|
| 手動字幕の選択 | `writesubtitles: True` |
| 自動生成字幕の選択 | `writeautomaticsub: True` |
| 言語コード | `subtitleslangs: [lang1, lang2, ...]` |
| フォーマット | `subtitlesformat: srt / vtt / best` |
| MP4 埋め込み | `FFmpegSubtitlesConvertor`（埋め込み前変換） + `FFmpegEmbedSubtitle` ポストプロセッサ |

字幕ファイルを個別に保存する場合（埋め込みなし）は、動画ファイルと同じフォルダに `.srt` / `.vtt` ファイルとして保存されます。

### JSON 字幕の自動変換

YouTube Live など `json3` 形式しか配信されない動画では、`FFmpegEmbedSubtitle` 単体だと `JSON subtitles cannot be embedded` のエラーで埋め込みに失敗します。これを避けるため、埋め込み有効時は `FFmpegSubtitlesConvertor` を埋め込み前に挟み、ユーザーが選んだフォーマット（`srt` / `vtt`）または `srt`（`best` 選択時のフォールバック）へ変換してから埋め込みます。

### JSON 専用字幕の扱い（`live_chat` / `comments`）

一部の抽出器は標準的な字幕フォーマットではない JSON のみを字幕として公開します。

| lang | 由来 | ラベル |
|---|---|---|
| `live_chat` | YouTube Live のチャットログ（`info["subtitles"]` / `info["automatic_captions"]` 双方に出現） | `live_chat – ライブチャット (埋め込み不可・サイドカー保存) [json]` |
| `comments` | ニコニコ動画コメント（`NiconicoIE._get_subtitles` が v1/threads JSON として出力） | `comments – ニコニコ動画コメント (埋め込み不可・サイドカー保存) [json]` |

これらは `FFmpegSubtitlesConvertor` / `FFmpegEmbedSubtitle` で変換も埋め込みもできないため、字幕リストには表示しつつ、埋め込みパスからは除外して JSON ファイルだけがサイドカーとして残るようにしています。

実装:

- 自動字幕ループでは `_JSON_ONLY_SUB_LANGS = {"live_chat", "comments"}` をスキップ（手動扱いの 1 エントリだけが UI に出る）
- 「MP4 に埋め込む」が ON でかつ `subtitleslangs` にいずれかの json 専用 lang が含まれるとき、`_StripJsonOnlySubsBeforeEmbedPP` を `FFmpegSubtitlesConvertor` の前に差し込み、`requested_subtitles` から該当 lang を取り除く（ファイルはダウンロード済みなのでディスクには残る）
- 埋め込み OFF のときは convert/embed PP 自体が走らないため、フィルタも不要

---

## メタデータ・チャプター

ダウンロード後、`FFmpegMetadata` ポストプロセッサで動画ファイルにメタデータ・チャプターを埋め込めます。

- **最高画質 / 解像度指定**: 常に ON
- **オリジナル形式**: パネルのチェックボックスで制御（デフォルト ON）

---

## Cookies

認証が必要な動画（会員限定など）のダウンロードに使用します。

### ファイル指定

設定の `cookies_path` が有効なファイルパスを指す場合、`cookies` オプションとして yt-dlp に渡します。

### ブラウザから取得

設定の `cookies_browser` が設定されている場合、`cookiesfrombrowser` オプションとして yt-dlp に渡します。ブラウザ設定がファイル設定より優先されます。

### Cookies ファイルが見つからない場合

ダウンロード実行時にファイルが存在しない場合は警告ダイアログを表示し、Cookies なしでダウンロードを続行します。

---

## yt-dlp 共通オプション

すべてのダウンロードに共通して適用されるオプションです。

| オプション | 値 |
|---|---|
| `js_runtimes` | deno のパスを指定 |
| `ffmpeg_location` | 同梱の ffmpeg パス |
| `remote_components` | `['ejs:github']` |
| `noplaylist` | `True`（個別エントリとして処理） |
| `color` | `'no_color'`（ANSI エスケープコードを抑制） |
| `logger` | `_YtdlpLogger`（ログコールバックが設定されている場合） |

---

## 依存バイナリのパス解決

`Downloader.__init__()` で以下の方法でパスを決定します。

- **PyInstaller バイナリ時**: `sys._MEIPASS` 直下（バンドル時は `bin/` 階層がフラット化される）
- **開発時**: プロジェクトルートの `bin/` 以下

| バイナリ | パス |
|---|---|
| deno | `{base}/deno[.exe]` |
| ffmpeg | `{base}/ffmpeg/ffmpeg[.exe]` |
| ffprobe | `{base}/ffmpeg/ffprobe[.exe]` |
