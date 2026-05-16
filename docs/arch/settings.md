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
