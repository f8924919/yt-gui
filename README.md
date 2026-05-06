# yt-dlp GUI ダウンローダー

YouTube などの動画を GUI 操作でかんたんにダウンロードできる Windows / macOS 向けデスクトップアプリです。  
[yt-dlp](https://github.com/yt-dlp/yt-dlp) をバックエンドに使用し、MP4（最高画質 / 解像度指定）・MP3（音声のみ）・オリジナル形式（映像/音声トラックを個別指定）でのダウンロードに対応しています。

## 機能

- URL と形式を選んで **ダウンロードキューに追加** し、まとめて実行
  - **「追加」ボタン 1 つ** で単独 URL・再生リスト URL を自動判別してキューに登録。タイトルをバックグラウンドで取得してからキューに表示する
  - 実行中でも新しいアイテムをキューに追加できる
  - **一時停止 / 再開** に対応（現在処理中のダウンロードは最後まで続き、次のアイテムから停止）
  - 待機中・完了・エラーのアイテムをキューから削除可能
- 以下の形式を選択可能（解像度・ビットレートは設定画面で変更できます）
  | 表示名 | 内容 |
  |---|---|
  | 最高画質 (MP4に結合) | 最高品質の映像＋音声を MP4 にマージ |
  | *N*p (MP4に結合) | 指定解像度以下の映像＋音声を MP4 にマージ（デフォルト 720p） |
  | MP3 (音声のみ・*N*kbps) | 音声のみを MP3 として抽出（デフォルト 192kbps）。サムネイルの ID3 タグ埋め込みオプションあり |
  | オリジナルの形式 | 動画から取得した映像/音声トラックを個別に選択してダウンロード |

- **MP3 形式** 選択時は「サムネイルを埋め込む」チェックボックスが表示される。有効にすると動画のサムネイル画像を MP3 の ID3 タグ（APIC）に埋め込む（`mutagen` 使用）
- **オリジナルの形式** を選択すると詳細設定パネルが展開される
  1. 「形式を取得」ボタンで URL の動画情報を取得
  2. 利用可能な映像/音声/字幕トラックが一覧表示される。音声には言語コードも表示（例: `opus (webm) [251] – 129kbps [ja]`）
  3. 映像・音声それぞれに「自動 (最良を選択)」「**ダウンロードしない**」と個別フォーマットから選択可能。「ダウンロードしない」を使うと映像のみ / 音声のみのダウンロードが可能（両方同時にスキップは不可）
  4. 複合フォーマット（★印）を映像に選択した場合は音声選択が自動的に無効化される
  5. 字幕は複数言語を同時選択可能（Ctrl+クリック / Shift+クリック）。手動字幕・自動生成字幕に対応。字幕フォーマット（srt / vtt / best）と MP4 への埋め込みオプションあり
- **ファイル名の重複回避**: ダウンロード先に同名ファイルが既に存在する場合、`タイトル (1).mp4` のように連番サフィックスを付けて保存する（上書きしない）
- ダウンロード進捗をプログレスバーとステータスラベルでリアルタイム表示
- メニューバー（ファイル > 設定... / Ctrl+,）から設定画面を呼び出し可能
- 設定画面で以下を変更・保存できる
  - **一般タブ**: 保存フォルダ（未設定時は `~/Downloads`）・Cookies ファイルのパス・表示言語（日本語 / English）— 言語変更は再起動後に反映
  - **画質・音質タブ**: 解像度上限（480p / 720p / 1080p / 1440p / 2160p）・MP3ビットレート（128 / 192 / 256 / 320 kbps）— 「最高画質」と「オリジナルの形式」には影響しない
- 設定は OS 標準の設定ディレクトリに JSON で永続保存
  - Windows: `%APPDATA%\yt-gui\settings.json`
  - macOS: `~/Library/Application Support/yt-gui/settings.json`
  - Linux: `~/.config/yt-gui/settings.json`

## 必要環境

- Windows 10 / 11
- macOS 12 (Monterey) 以上
- Python 3.14 以上（開発時のみ）

ビルド済みバイナリ版には Python 不要です。

## セットアップ（開発環境）

### uv を使う場合（推奨）

```bash
uv sync
```

### pip を使う場合

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS / Linux

pip install -r requirements.txt
```

## 使い方

### 開発環境から起動

```bash
# uv
uv run python -m yt_gui

# pip（仮想環境を有効化済みの場合）
python -m yt_gui
```

### ビルドの作成

```bash
# uv
uv run pyinstaller yt-gui.spec

# pip（仮想環境を有効化済みの場合）
pyinstaller yt-gui.spec
```

ビルド成果物の出力先：

| プラットフォーム | 出力先 |
|---|---|
| Windows | `dist/yt-gui/yt-gui.exe` |
| macOS | `dist/yt-gui.app`（通常の .app バンドル） |

`bin/` 配下のバイナリ（deno, ffmpeg）はビルド時に自動ダウンロードされます。

## プロジェクト構成

```
yt-gui/
├── yt_gui/                    # アプリ本体（Python パッケージ）
│   ├── locales/               # 多言語対応 — 言語ごとの文字列辞書
│   │   ├── ja.py              # 日本語
│   │   └── en.py              # English
│   ├── __init__.py            # get_resource_base() ユーティリティ
│   ├── __main__.py            # エントリーポイント（python -m yt_gui 用）
│   ├── app.py                 # GUI クラス
│   ├── downloader.py          # ダウンローダークラス
│   ├── formats.py             # ダウンロード形式の定義・解像度/ビットレート選択肢
│   ├── i18n.py                # 翻訳関数 t() / set_language()
│   ├── settings.py            # Settings dataclass / SettingsManager
│   └── settings_dialog.py     # 設定ダイアログ（モーダル）
├── bin/                       # バイナリ（自動取得・.gitignore 対象）
│   ├── deno.exe
│   └── ffmpeg/
│       └── ffmpeg.exe
├── assets/
│   └── icon.png               # アプリアイコン（Windows: .ico、macOS: .icns に変換）
├── scripts/
│   └── download_binaries.py   # deno / ffmpeg を自動取得するスクリプト
├── main.py                    # PyInstaller 用エントリーポイント
├── yt-gui.spec                # PyInstaller ビルド設定
├── pyproject.toml             # プロジェクトメタデータ・依存関係
├── requirements.txt           # pip 用依存パッケージ一覧
└── cookies.txt                # デフォルト cookies ファイル（開発時参照用）
```

## アーキテクチャ

| モジュール | 責務 |
|---|---|
| `yt_gui/i18n.py` | `t(key)` で翻訳文字列を返す。`set_language()` で言語を切り替え |
| `yt_gui/locales/ja.py` / `en.py` | 各言語の文字列辞書。`fmt_720p` / `fmt_mp3` はテンプレート文字列（`{resolution}` / `{bitrate}` プレースホルダー）で、`App._build_format_display()` が設定値を埋めて表示名を生成する |
| `yt_gui/formats.py` | `FORMAT_SPECS` / `FORMAT_KEYS`（ダウンロード形式定義）と `VIDEO_RESOLUTIONS` / `MP3_BITRATES`（設定画面の選択肢）を定義 |
| `yt_gui/downloader.py` | yt-dlp のラッパー。`fetch_title_or_entries()` で単独/プレイリストを自動判別してタイトルを取得、`fetch_formats()` で映像/音声（言語タグ付き）/字幕一覧とタイトルを取得、`download_video()` でダウンロード実行。ダウンロード前に `prepare_filename()` で出力先ファイルの存在を確認し、重複時は `(N)` サフィックスを付与。`embed_thumbnail=True` 時は `writethumbnail` + `EmbedThumbnail` ポストプロセッサーで MP3 にサムネイルを埋め込む |
| `yt_gui/settings.py` | `Settings` dataclass（`cookies_path` / `download_path` / `language` / `video_resolution` / `mp3_bitrate`）と `SettingsManager`。設定を JSON ファイルに読み書き |
| `yt_gui/settings_dialog.py` | `SettingsDialog(tk.Toplevel)`。「一般」タブ（保存フォルダ・Cookies・言語）と「画質・音質」タブ（解像度上限・MP3ビットレート）を持つモーダル設定画面 |
| `yt_gui/app.py` | Tkinter GUI。「追加」ボタンが単独/プレイリストを自動判別しバックグラウンドでタイトルを取得してキューに追加する。キューアイテム（`_QueueItem`）には `format_spec`・`mp3_bitrate`・`mp3_thumbnail` を追加時にスナップショットし、設定変更が既存アイテムに影響しないようにする。オリジナル形式パネルでは映像/音声コンボに「ダウンロードしない」選択肢を追加し映像のみ/音声のみのダウンロードに対応。字幕は `Listbox(MULTIPLE)` で複数言語を同時選択可能。MP3 選択時はサムネイル埋め込みチェックボックスを表示 |
| `yt_gui/__main__.py` | `python -m yt_gui` のエントリーポイント |
| `main.py` | PyInstaller ビルド用のエントリーポイント |

パス解決は `get_resource_base()`（`yt_gui/__init__.py`）で一元管理しており、開発時とビルド済み exe の両方で動作します。

## バンドルするバイナリについて

ビルドには以下のファイルが同梱されます（`yt-gui.spec` で設定済み）。

| ファイル | 用途 |
|---|---|
| `deno` / `deno.exe` | yt-dlp の JavaScript ランタイム |
| `ffmpeg/ffmpeg` / `ffmpeg/ffmpeg.exe` | 動画結合・MP3 変換 |
| `assets/icon.png` | アプリアイコン |

`bin/` 配下のバイナリは `scripts/download_binaries.py` で取得できます（`pyinstaller yt-gui.spec` 実行時に自動呼び出し）。`--update` フラグを渡すと既存ファイルを強制的に再ダウンロードします。

```bash
python scripts/download_binaries.py --update
```

Cookies ファイルはビルド成果物に含まれません。アプリ起動後、設定画面（ファイル > 設定...）からパスを指定してください。
