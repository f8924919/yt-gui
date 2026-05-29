# バージョンの単一ソース化 + UI 表示

## 背景

バージョン番号が `pyproject.toml`（`[project] version`）と `yt-gui.spec`（`CFBundleShortVersionString`）に独立してハードコードされており、更新時に手動同期が必要でずれるリスクがあった。またアプリ実行時にバージョンを確認する手段（UI 表示）が無かった。

## 対応内容

`pyproject.toml` の `version` を唯一のソースとし、以下に集約した。

1. **spec の単一ソース化**: `yt-gui.spec` が `tomllib` で `pyproject.toml` を読み取り、`CFBundleShortVersionString` に注入する。
2. **UI 表示**: `yt_gui.get_version()`（`importlib.metadata.version("yt-gui")`）を追加し、`App` のウィンドウタイトルを `"{app_title} v{version}"` 形式にした（`_window_title()` ヘルパで初期化・言語切替の両方に適用）。

### 付随変更

- `importlib.metadata` でバージョンを解決するため、`pyproject.toml` に `[build-system]`（hatchling）を追加し、`uv sync` で yt-gui 自身をパッケージとしてインストール（`*.dist-info` 生成）するようにした。
- PyInstaller バンドルでもメタデータを解決できるよう、`yt-gui.spec` の `datas` に `copy_metadata('yt-gui')` を追加。
- メタデータ未検出時は `get_version()` が `"unknown"` を返す（クラッシュ回避）。

## 対象ファイル

- `pyproject.toml` — `[build-system]` / `[tool.hatch.build.targets.wheel]` 追加
- `yt_gui/__init__.py` — `get_version()` 追加
- `yt_gui/app.py` — `_window_title()` 追加・2 箇所の `setWindowTitle` で使用
- `yt-gui.spec` — `tomllib` でバージョン読込・`copy_metadata` 同梱
- `docs/build.md` / `docs/arch/entry.md` — ドキュメント更新

## 各プラットフォームへの反映（追加対応）

`pyproject.toml` の `version` を全成果物に反映させた。

- **Windows `.exe`**: `yt-gui.spec` で `VSVersionInfo` を組み立て `EXE(version=...)` に渡す（`_version_tuple()` で `"0.1.0"` → `(0,1,0,0)` に変換、Windows ビルド時のみ）。
- **Linux AppImage**: `scripts/build_appimage.py` が `get_version()` を用い、出力名を `yt-gui-{version}-{arch}.AppImage` に変更。`VERSION` 環境変数も appimagetool に渡す。

### 検証メモ

- **Windows `.exe`**: 実機ビルドで `.exe` のファイルバージョンが `pyproject.toml` の値どおりに埋め込まれることを確認済み（2026-05-29）。
- **Linux AppImage**: サンドボックス（x86_64 Linux）で `/tmp` にリポジトリをコピーしフルビルドを実施し、以下を確認済み（2026-05-29）。
  - 出力名が `yt-gui-0.1.0-x86_64.AppImage`（`yt-gui-{version}-{arch}.AppImage`）になり、`pyproject.toml` の version と一致。
  - 生成物は ELF（static-pie, ~192MB）で、`--appimage-extract-and-run` により **FUSE 無し環境でも起動**（`QT_QPA_PLATFORM=offscreen` で GUI イベントループ起動までクラッシュ無しを確認）。
  - バンドル内に `copy_metadata('yt-gui')` 由来の `yt_gui-0.1.0.dist-info`（`Version: 0.1.0`）が同梱され、ランタイムの `get_version()` が解決可能。
  - ffmpeg / ffprobe / deno / danmaku2ass が `_internal/` に同梱。

#### サンドボックスでビルドするのに必要だった追加セットアップ

`/tmp` へコピー → `uv sync`（yt-gui 自身をパッケージ化）→ `uv run pyinstaller yt-gui.spec` の前提として:

- `apt-get install binutils`（PyInstaller が `objdump` を要求）
- `apt-get install file`（appimagetool が `file` コマンドを要求）
- ffmpeg: 取得元 `johnvansickle.com`（Linux）がサンドボックスのネットワークフィルタで **HTTP 403**。回避策として `apt-get install ffmpeg` で入れた `/usr/bin/ffmpeg`・`ffprobe` を `bin/ffmpeg/` に配置した（パイプライン検証目的のため実体は apt 版で代替）。
- deno / appimagetool は GitHub から取得可能（`download_binaries.py` / `build_appimage.py` がそのまま成功）。
- spec 内の `download_binaries.py` 呼び出しは `--yes` 非対応で GPL 同意プロンプトが EOF→N 扱いになるため、ffmpeg/deno/danmaku2ass は事前に配置しておく必要がある。
- 入れた OS パッケージ（binutils / file / ffmpeg）はサンドボックス再起動で消える（[Qt UI テスト調査メモ](../research/qt-ui-testing-feasibility.md) §5.3 と同事情）。CI に乗せる場合はワークフローで明示インストールが要る。
- 注: ディスプレイが無いため **GUI の目視確認は不可**。起動の可否（offscreen）までが限界。
