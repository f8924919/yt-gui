import importlib.metadata
import os
import sys


def get_version() -> str:
    """アプリのバージョン文字列を返す。

    pyproject.toml を唯一のソースとし、インストール済みパッケージのメタデータ
    （PyInstaller バンドル時は spec の copy_metadata で同梱）から取得する。
    メタデータが見つからない場合は "unknown" を返す。
    """
    try:
        return importlib.metadata.version("yt-gui")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def get_yt_dlp_version() -> str:
    """同梱 yt-dlp のバージョン文字列を返す。

    実行中の `yt_dlp.version.__version__`（PyInstaller では freeze 同梱版）を
    参照する。取得できない場合は "unknown" を返す。
    """
    try:
        from yt_dlp.version import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def get_resource_base() -> str:
    """バイナリ・アセットのベースディレクトリを返す。

    PyInstaller バンドル時は sys._MEIPASS、開発時はプロジェクトルートを返す。
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return str(meipass)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
