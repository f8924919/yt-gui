# Linux 向け AppImage 自動生成

## 背景

現状、`yt-gui.spec` での PyInstaller ビルドは Windows / macOS では配布しやすい単一成果物（`.exe` / `.app`）を出力するが、Linux では `dist/yt-gui/` ディレクトリ一式のみ。Linux ユーザーに配布する際は AppImage 形式が最も汎用的なため、ビルド時に自動で `.AppImage` を生成できるようにする。

## ゴール

- `uv run pyinstaller yt-gui.spec` を Linux 上で実行すると、`dist/yt-gui/` に加えて `dist/yt-gui-{arch}.AppImage` が生成される
- Windows / macOS では従来通り（AppImage 生成はスキップ）
- `appimagetool` は `bin/` 配下に自動取得（既存の deno/ffmpeg と同様）

## 完了条件

- `scripts/build_appimage.py` を追加
- `yt-gui.spec` に Linux 向けの後処理を追加
- `docs/build.md` に Linux AppImage の項目を追記
- `docs/task/index.md` を更新

## 関連ファイル

- [yt-gui.spec](../../../yt-gui.spec)
- [scripts/build_appimage.py](../../../scripts/build_appimage.py)
- [docs/build.md](../../build.md)
