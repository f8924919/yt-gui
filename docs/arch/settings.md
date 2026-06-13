# yt_gui/settings.py

> 関連仕様: [設定管理](../spec/settings.md)

設定の読み書きを担当。

## クラス: `Settings`（dataclass）

| フィールド | 型 | デフォルト | 説明 |
|------------|----|-----------|------|
| `cookies_path` | `str` | `""` | Cookies ファイルのパス |
| `cookies_browser` | `str` | `""` | Cookies を取得するブラウザ名（空 = 未使用） |
| `download_path` | `str` | `""` | 保存先（空のとき `~/Downloads`） |
| `language` | `str` | `"ja"` | UI 言語コード |
| `video_resolution` | `str` | `"720"` | 解像度上限 |
| `mp3_bitrate` | `str` | `"192"` | MP3 ビットレート |
| `audio_format` | `str` | `"mp3"` | 音声形式（`"mp3"` または `"flac"`） |
| `video_container` | `str` | `"mp4"` | 映像コンテナ（`"mp4"` / `"mkv"` / `"webm"`） |
| `output_template_video` | `str` | `"%(title)s.%(ext)s"` | 単独動画の OUTPUT TEMPLATE |
| `output_template_playlist` | `str` | `"%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"` | プレイリストの OUTPUT TEMPLATE |
| `concurrent_fragments` | `int` | `1` | 並列フラグメント DL 数（`CONCURRENT_FRAGMENTS_MIN`〜`MAX`） |
| `rate_limit_value` | `float` | `0.0` | 速度制限値（`0` = 無制限） |
| `rate_limit_unit` | `str` | `"M"` | 速度制限の単位（`RATE_LIMIT_UNITS` のいずれか） |
| `proxy_enabled` | `bool` | `False` | プロキシの有効化トグル |
| `proxy_scheme` | `str` | `"http"` | プロキシのプロトコル (`PROXY_SCHEMES` のいずれか) |
| `proxy_host` | `str` | `""` | プロキシのホスト名または IP |
| `proxy_port` | `str` | `""` | プロキシのポート（空欄時はプロトコル既定ポート） |
| `proxy_username` | `str` | `""` | プロキシ認証のユーザー名（任意） |
| `proxy_password` | `str` | `""` | プロキシ認証のパスワード（任意、平文保存） |
| `download_archive_enabled` | `bool` | `False` | ダウンロードアーカイブの有効化トグル |
| `download_archive_path` | `str` | `""` | アーカイブ記録ファイルのパス（空 = 設定ディレクトリの `download_archive.txt`） |
| `extension_enabled` | `bool` | `False` | ブラウザ拡張連携のローカル受信サーバー有効化トグル |
| `extension_port` | `int` | `8718` | 受信ポート（`EXTENSION_SERVER_DEFAULT_PORT`） |
| `extension_token` | `str` | `""` | 拡張と共有する認証トークン（`generate_extension_token()` で生成、有効化時に発行） |

## 定数: `EXTENSION_SERVER_DEFAULT_PORT` / `EXTENSION_SERVER_PORT_FALLBACKS`

ブラウザ拡張連携のローカル受信サーバーの既定ポート `8718` とフォールバック `(8719, 8720)`。`ExtensionServer.start()` がこの順でバインドを試す（[extension_server.md](extension_server.md)）。

## 関数: `generate_extension_token() -> str`

`secrets.token_urlsafe(32)` で URL セーフな共有トークンを生成する。設定ダイアログでブラウザ連携を有効化したときに発行する。

## 定数: `PROXY_SCHEMES`

`("http", "https", "socks4", "socks5", "socks5h")`。設定ダイアログのプロトコル選択肢として使用。

## 定数: `RATE_LIMIT_UNITS` / `RATE_LIMIT_VALUE_MAX`

`RATE_LIMIT_UNITS = ("K", "M")` は速度制限の単位（`"K"` = KB/s、`"M"` = MB/s）。`RATE_LIMIT_VALUE_MAX` はスピンボックスの上限値。換算は 2 進接頭辞（`"K"` = ×1024、`"M"` = ×1024×1024）。

## 関数: `build_rate_limit(settings: Settings) -> float`

`rate_limit_value` / `rate_limit_unit` を yt-dlp の `ratelimit`（bytes/sec の float）に換算する純粋関数。

- `rate_limit_value` が 0 以下のときは `0.0` を返す（呼び出し側で `ratelimit` オプションを付けない = 無制限）
- 未知の単位は `"M"` 相当（×1024×1024）にフォールバック

## 関数: `build_proxy_url(settings: Settings) -> str`

`Settings` の `proxy_*` フィールドから yt-dlp の `proxy` オプションに渡せる URL を組み立てる純粋関数。

- `proxy_enabled=False` または `proxy_host` が空のときは `""` を返す（呼び出し側で `proxy` オプションを付けない）
- ユーザー名・パスワードは `urllib.parse.quote(..., safe="")` でパーセントエンコード
- 戻り値は `scheme://[user[:password]@]host[:port]`

## ダウンロードアーカイブ関連の関数

| 関数 | 説明 |
|---|---|
| `default_download_archive_path() -> str` | 既定のアーカイブファイルパス（設定ディレクトリ直下の `download_archive.txt`） |
| `resolve_download_archive_path(settings) -> str` | yt-dlp の `download_archive` に渡す実効パス。`download_archive_enabled=False` のとき `""`（無効）、有効かつパス空欄なら既定パス |
| `count_download_archive_entries(path) -> int` | アーカイブファイルの記録件数（非空行数）。ファイル不在・読み込み失敗時は `0`（非致命） |

動作仕様は[ダウンロードアーカイブ](../spec/features/download-behavior.md#ダウンロードアーカイブ)、opt 付与・スキップ検出・プレフィルタは [downloader](downloader.md#ダウンロードアーカイブ)を参照。

## クラス: `SettingsManager`

### メソッド

| メソッド | 説明 |
|----------|------|
| `load() -> Settings` | JSON を読み込んで返す。ファイル不在・破損時はデフォルト値で返す |
| `save(settings: Settings) -> None` | JSON に書き込む |

## 保存先

| OS | パス |
|----|------|
| Windows | `%APPDATA%\yt-gui\settings.json` |
| macOS | `~/Library/Application Support/yt-gui/settings.json` |
| Linux | `$XDG_CONFIG_HOME/yt-gui/settings.json`（未設定時は `~/.config/yt-gui/`） |

> yt-dlp プラグインフォルダ（`%APPDATA%\yt-dlp\plugins\`）とは別系統のパスであることに注意。
