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
| `proxy_enabled` | `bool` | `False` | プロキシの有効化トグル |
| `proxy_scheme` | `str` | `"http"` | プロキシのプロトコル (`PROXY_SCHEMES` のいずれか) |
| `proxy_host` | `str` | `""` | プロキシのホスト名または IP |
| `proxy_port` | `str` | `""` | プロキシのポート（空欄時はプロトコル既定ポート） |
| `proxy_username` | `str` | `""` | プロキシ認証のユーザー名（任意） |
| `proxy_password` | `str` | `""` | プロキシ認証のパスワード（任意、平文保存） |

## 定数: `PROXY_SCHEMES`

`("http", "https", "socks4", "socks5", "socks5h")`。設定ダイアログのプロトコル選択肢として使用。

## 関数: `build_proxy_url(settings: Settings) -> str`

`Settings` の `proxy_*` フィールドから yt-dlp の `proxy` オプションに渡せる URL を組み立てる純粋関数。

- `proxy_enabled=False` または `proxy_host` が空のときは `""` を返す（呼び出し側で `proxy` オプションを付けない）
- ユーザー名・パスワードは `urllib.parse.quote(..., safe="")` でパーセントエンコード
- 戻り値は `scheme://[user[:password]@]host[:port]`

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
