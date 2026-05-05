# yt-dlp GUI ダウンローダー

YouTube などの動画を GUI 操作でかんたんにダウンロードできる Windows / macOS 向けデスクトップアプリです。  
[yt-dlp](https://github.com/yt-dlp/yt-dlp) をバックエンドに使用し、MP4（最高画質 / 720p）または MP3（音声のみ）でのダウンロードに対応しています。

## 機能

- 動画 URL を入力するだけでダウンロード開始
- 以下の形式を選択可能
  | 表示名 | 内容 |
  |---|---|
  | 最高画質 (MP4に結合) | 最高品質の映像＋音声を MP4 にマージ |
  | 720p (MP4に結合) | 720p 以下の映像＋音声を MP4 にマージ |
  | MP3 (音声のみ・192kbps) | 音声のみを 192kbps の MP3 として抽出 |
  | オリジナルの形式 | yt-dlp のデフォルト形式でそのままダウンロード |
- ダウンロード進捗をプログレスバーとステータスラベルでリアルタイム表示
- メニューバー（ファイル > 設定... / Ctrl+,）から設定画面を呼び出し可能
- 設定画面で以下を変更・保存できる
  - 保存フォルダ（未設定時は `~/Downloads`）
  - Cookies ファイルのパス
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
uv run pyinstaller yt.spec

# pip（仮想環境を有効化済みの場合）
pyinstaller yt.spec
```

ビルド成果物は `dist/yt/` に出力されます。`bin/` 配下のバイナリ（deno, ffmpeg）はビルド時に自動ダウンロードされます。

## プロジェクト構成

```
yt-gui/
├── yt_gui/                    # アプリ本体（Python パッケージ）
│   ├── __init__.py            # get_resource_base() ユーティリティ
│   ├── __main__.py            # エントリーポイント（python -m yt_gui 用）
│   ├── app.py                 # GUI クラス
│   ├── downloader.py          # ダウンローダークラス
│   ├── formats.py             # ダウンロード形式の定義
│   ├── settings.py            # Settings dataclass / SettingsManager
│   └── settings_dialog.py     # 設定ダイアログ（モーダル）
├── bin/                       # バイナリ（自動取得・.gitignore 対象）
│   ├── deno.exe
│   └── ffmpeg/
│       └── ffmpeg.exe
├── assets/
│   └── icon.png               # アプリアイコン（ビルド時に .ico へ変換）
├── scripts/
│   └── download_binaries.py   # deno / ffmpeg を自動取得するスクリプト
├── main.py                    # PyInstaller 用エントリーポイント
├── yt.spec                    # PyInstaller ビルド設定
├── pyproject.toml             # プロジェクトメタデータ・依存関係
├── requirements.txt           # pip 用依存パッケージ一覧
└── cookies.txt                # デフォルト cookies ファイル（開発時参照用）
```

## アーキテクチャ

| モジュール | 責務 |
|---|---|
| `yt_gui/formats.py` | ダウンロード形式の定義（`FORMAT_OPTIONS` 定数） |
| `yt_gui/downloader.py` | yt-dlp のラッパー。進捗を `_progress_hook` 経由で GUI に通知 |
| `yt_gui/settings.py` | `Settings` dataclass と `SettingsManager`。設定を JSON ファイルに読み書き |
| `yt_gui/settings_dialog.py` | `SettingsDialog(tk.Toplevel)`。タブ構成のモーダル設定画面 |
| `yt_gui/app.py` | Tkinter GUI。メニューバーを持ち、ダウンロードを別スレッドで実行 |
| `yt_gui/__main__.py` | `python -m yt_gui` のエントリーポイント |
| `main.py` | PyInstaller ビルド用のエントリーポイント |

パス解決は `get_resource_base()`（`yt_gui/__init__.py`）で一元管理しており、開発時とビルド済み exe の両方で動作します。

## バンドルするバイナリについて

exe ビルドには以下のファイルが同梱されます（`yt.spec` で設定済み）。

| ファイル | 用途 |
|---|---|
| `deno.exe` | yt-dlp の JavaScript ランタイム |
| `ffmpeg/ffmpeg.exe` | 動画結合・MP3 変換 |
| `assets/icon.png` | アプリアイコン |

`bin/` 配下のバイナリは `scripts/download_binaries.py` で取得できます（`pyinstaller yt.spec` 実行時に自動呼び出し）。

Cookies ファイルはビルド成果物に含まれません。アプリ起動後、設定画面（ファイル > 設定...）からパスを指定してください。
