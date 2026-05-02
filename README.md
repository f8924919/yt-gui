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
- cookies.txt によるログイン済みセッションのサポート
- ダウンロード先は `~/Downloads` フォルダ（固定）

## 必要環境

- Windows 10 / 11
- macOS 12 (Monterey) 以上
- Python 3.14 以上（開発時のみ）

ビルド済みバイナリ版には Python 不要です。

## セットアップ（開発環境）

### uv を使う場合（推奨）

```bash
# 依存パッケージのインストール（仮想環境は自動作成）
uv sync
```

### pip を使う場合

```bash
# 仮想環境の作成・有効化
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS / Linux

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 使い方

### 開発環境から起動

```bash
# uv
uv run python yt.py

# pip（仮想環境を有効化済みの場合）
python yt.py
```

### ビルドの作成

```bash
# uv
uv run pyinstaller yt.spec

# pip（仮想環境を有効化済みの場合）
pyinstaller yt.spec
```

ビルド成果物は `dist/yt/` に出力されます。

## プロジェクト構成

```
yt-gui/
├── yt.py                  # アプリ本体（GUIおよびダウンローダー）
├── yt.spec                # PyInstaller ビルド設定
├── pyproject.toml         # プロジェクトメタデータ・依存関係
├── requirements.txt       # pip 用依存パッケージ一覧
├── cookies.txt            # デフォルト cookies ファイル（変更可）
├── deno.exe               # yt-dlp 用 JavaScript ランタイム
└── ffmpeg/
    └── ffmpeg.exe         # 動画結合・音声変換用
```

## アーキテクチャ

`yt.py` の単一ファイル構成で、2 つのクラスに責務を分離しています。

- **`Downloader`** — yt-dlp のラッパークラス。`download_video(url, format_key, cookies_path)` でダウンロードを実行し、`_progress_hook` コールバック経由で GUI へ進捗を通知する。
- **`App(tk.Tk)`** — Tkinter GUI クラス。ダウンロード処理は `threading.Thread` で別スレッド実行し、GUI がフリーズしないようにしている。完了後は `self.after(100, ...)` でメインスレッドに戻って UI をリセット。

## バンドルするバイナリについて

exe ビルドには以下のバイナリが同梱されます（`yt.spec` で設定済み）。

| ファイル | 用途 |
|---|---|
| `deno.exe` | yt-dlp の JavaScript ランタイム |
| `ffmpeg/ffmpeg.exe` | 動画結合・MP3 変換 |
| `cookies.txt` | デフォルト cookies（GUI で変更可能） |

バイナリは `download_binaries.py` スクリプトで取得できます。
