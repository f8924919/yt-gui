# ビルドとバンドルバイナリ

PyInstaller でスタンドアロンバイナリをビルドする際の構成と、同梱する外部バイナリの取り扱いを記載。

## ビルドコマンド

```bash
uv run pyinstaller yt-gui.spec
```

ビルド成果物は `dist/yt-gui/` に出力される（macOS は `dist/yt-gui.app/`）。

## 同梱するバイナリ

| バイナリ | パス | 用途 |
|---|---|---|
| deno | `bin/deno[.exe]` | yt-dlp の JavaScript ランタイム（`js_runtimes` オプションで指定） |
| ffmpeg | `bin/ffmpeg/ffmpeg[.exe]` | 動画結合・音声変換（`ffmpeg_location` で指定） |
| ffprobe | `bin/ffmpeg/ffprobe[.exe]` | 動画メタデータ取得（`ffmpeg_location` から自動検索される） |

`yt-gui.spec` の `binaries` 設定でこれらをバイナリに同梱する。

## バイナリの自動取得

`scripts/download_binaries.py` で deno / ffmpeg / ffprobe を自動取得し `bin/` 配下に配置する。`yt-gui.spec` のビルド時に自動呼び出しされる。

```bash
# 既存ファイルがあればスキップ
python scripts/download_binaries.py

# 既存ファイルを強制的に再ダウンロード
python scripts/download_binaries.py --update
```

## yt-gui.spec の構成

- PySide6 向けに設定済み。`pyinstaller-hooks-contrib` が PySide6 プラグイン・データを自動検出するため追加設定は最小限。
- macOS 向けビルドでは `BUNDLE` ブロックで `.app` バンドルを自動生成する。
- アイコンは `assets/icon.png` から PNG → ICO（Windows）/ ICNS（macOS）への自動変換に対応。

## Cookies ファイル

Cookies ファイルはビルド成果物には**含めない**。GUI の設定画面でユーザーが任意に指定する運用。

実行時に Cookies フィールドのパスが指すファイルが存在しない場合は警告ダイアログを表示し、Cookies なしでダウンロードを続行する。
