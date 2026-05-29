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

- Windows のバージョンリソースと AppImage ビルドは、実機/対応 OS ランナーでのみ最終確認可能。サンドボックスでは `_version_tuple()` の変換ロジックと spec のパースまでを確認。
