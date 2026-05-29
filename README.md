# yt-dlp GUI ダウンローダー

YouTube などの動画を GUI 操作でダウンロードできるデスクトップアプリです。Windows / macOS / Linux (AppImage) に対応し、[yt-dlp](https://github.com/yt-dlp/yt-dlp) をバックエンドに使用します。

## 主な機能

- **ダウンロードキュー** — URL と形式を選んでキューに追加し、まとめて実行。一時停止 / 再開・キューアイテムの右クリック編集・タイトルとサムネイル付きツールチップに対応
- **再生リスト一括追加** — プレイリスト URL を入力すると個別の動画を自動展開してサブフォルダ付きでまとめて保存
- **複数のダウンロード形式** — 最高画質結合 / 解像度指定 / MP3・FLAC (音声のみ) / オリジナル形式 を選択可能
- **オリジナル形式の詳細指定** — 動画から実際の映像・音声・字幕トラックを取得して個別に選択。**音声は multi-select 対応**で、複数音声トラックを 1 つの MKV にマージできる
- **字幕の選択 / 埋め込み** — 手動 / 自動生成字幕の multi-select、SRT / VTT / best、動画ファイルへの埋め込み
- **メタデータ / チャプター / サムネイル埋め込み** — 出力ファイルにそのまま含める
- **OUTPUT TEMPLATE** — yt-dlp のテンプレート構文で保存ファイル名・フォルダ構成をカスタマイズ（単独動画 / プレイリスト別）
- **Cookies 対応** — Cookies ファイル指定またはブラウザからの自動抽出
- **多言語 UI** — 日本語 / English を即時切替
- **動作ログ** — yt-dlp の処理メッセージ・進捗・エラーをタイムスタンプ付きで確認可能

## 動作環境

- Windows 10 / 11
- macOS 12 (Monterey) 以上
- Linux (AppImage 経由)
- Python 3.14 以上（開発環境のみ）

ビルド済みバイナリ版には Python は不要です。

## 開発環境のセットアップと起動

```bash
uv sync
uv run python -m yt_gui
```

## ビルド

```bash
uv run pyinstaller yt-gui.spec
```

| プラットフォーム | 出力先 |
|---|---|
| Windows | `dist/yt-gui/yt-gui.exe` |
| macOS | `dist/yt-gui.app` |
| Linux | `dist/yt-gui/yt-gui` + `dist/yt-gui-{arch}.AppImage` |

同梱バイナリ（deno / ffmpeg / ffprobe / danmaku2ass）は `yt-gui.spec` 実行時に `scripts/download_binaries.py` が自動取得します。詳細は [docs/build.md](docs/build.md) を参照してください。

## ライセンス

本体は GPL-3.0（[LICENSE](LICENSE)）です。配布バイナリには以下の外部コンポーネントを同梱しています。

| コンポーネント | ライセンス | 対応ソース |
|---|---|---|
| ffmpeg / ffprobe | GPL（GPL ビルド） | https://ffmpeg.org/download.html |
| danmaku2ass | GPL-3.0 | https://github.com/m13253/danmaku2ass |
| deno | MIT | https://github.com/denoland/deno |

各コンポーネントのライセンス全文・著作権表示・対応ソース入手先は、リリース成果物を展開した `licenses/` 配下（`THIRD-PARTY-NOTICES.md` ほか）に同梱しています。`THIRD-PARTY-NOTICES.md` は GPL が要求する対応ソース提供の書面によるオファーを兼ねます。

## 設定の保存先

| プラットフォーム | パス |
|---|---|
| Windows | `%APPDATA%\yt-gui\settings.json` |
| macOS | `~/Library/Application Support/yt-gui/settings.json` |
| Linux | `~/.config/yt-gui/settings.json` |

Cookies ファイルはビルド成果物には**含まれません**。必要な場合はアプリ起動後に設定画面（ファイル > 設定...）からパスを指定してください。

## 詳細ドキュメント

仕様・アーキテクチャ・ビルド手順の詳細は [docs/](docs/) を参照してください。

| ドキュメント | 内容 |
|---|---|
| [docs/spec/](docs/spec/) | 動作仕様・画面仕様 |
| [docs/arch/](docs/arch/) | モジュール実装の詳細 |
| [docs/build.md](docs/build.md) | PyInstaller ビルドと同梱バイナリ |
