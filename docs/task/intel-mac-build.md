# feat(ci): Intel Mac (x86_64) 向けリリースビルドの追加

対応 Issue: #41

## 背景

リリース自動ビルド（`.github/workflows/release.yml`）の対象は Windows x64 / macOS arm64 / Linux x64 の 3 プラットフォームで、Intel Mac (x86_64) 向け配布物が無かった。Intel Mac ユーザー向けにネイティブ x86_64 ビルドを追加する。

## 調査: 追加に必要な変更は限定的

- **PyInstaller 本体**: `yt-gui.spec` の `target_arch=None` によりランナーのネイティブ arch でビルドされる。Intel ランナー上では x86_64 アプリが生成される。
- **deno**: `scripts/download_binaries.py` が `platform.machine()` で arch を判定し、`bin/pins.json` に `deno-x86_64-apple-darwin.zip` の sha256 が登録済み。
- **ffmpeg/ffprobe**: evermeet.cx は Intel x86_64 専用配布のため、Intel ランナーではネイティブで動作する（`ffmpeg-mac` ピン変更不要）。
- **danmaku2ass**: ランナー上でソースビルドするためネイティブ。

したがって主な変更は「ビルドマトリクスへの Intel ランナー追加」と「macOS パッケージ名の arch 動的化」に限られる。

## ランナー選定

`macos-13`（最後の標準 Intel ランナー）は退役済みのため、後継の標準 Intel イメージ **`macos-15-intel`** を採用する。public リポジトリでは標準ランナー扱いで利用可能。

## 実施内容

- `.github/workflows/release.yml`:
  - ビルドマトリクスに `macos-15-intel`（`macos_arch: x86_64`）を追加。既存 `macos-latest` には `macos_arch: arm64` を付与。
  - macOS パッケージステップの zip 名を `-macos-arm64.zip` ハードコードから `-macos-${{ matrix.macos_arch }}.zip` に変更。
  - artifact 名 `dist-${{ matrix.os }}` は OS ラベルが異なるため両 mac エントリで衝突しない。
- `docs/build.md`: OS マトリクス表に `macos-15-intel` 行を追加。arch 出し分けの仕組み、ffmpeg が arm64 では Rosetta 依存である旨（#42 で対応）を追記。

## 検証

- `release.yml` の YAML 構文を確認。
- リリース実動作はバージョン更新を伴う次回リリース時に確認（本 PR では発火しない）。
- arm64 成果物の命名（`-macos-arm64.zip`）・内容は従来どおり維持され回帰なし。

## 関連

- #42（arm64 リリースの ffmpeg を Apple Silicon ネイティブ化する／現状 Rosetta 依存）

## 対象ファイル

- `.github/workflows/release.yml`
- `docs/build.md`
- `docs/task/intel-mac-build.md`（本ファイル） / `docs/task/index.md`
