# yt_gui/__main__.py / yt_gui/__init__.py

## `__main__.py` — エントリーポイント

`QApplication` を起動し `App`（QMainWindow）を表示する。致命的エラーは `QMessageBox.critical()` で表示。

起動コマンド:

```bash
uv run python -m yt_gui
```

## `__init__.py` — リソースパス解決

### `get_resource_base() -> str`

| 実行環境 | 戻り値 |
|----------|--------|
| PyInstaller バンドル時 | `sys._MEIPASS`（展開された一時ディレクトリ） |
| 開発時 | プロジェクトルートディレクトリ |

`downloader.py` が ffmpeg・deno のバイナリパスを解決する際に使用する。

### `get_version() -> str`

`importlib.metadata.version("yt-gui")` でアプリのバージョン（`pyproject.toml` の `[project] version` が単一ソース）を返す。メタデータが見つからない場合は `"unknown"`。`app.py` がウィンドウタイトルに付与する。バージョン管理の全体像は [docs/build.md](../build.md) を参照。
