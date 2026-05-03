import os
import sys


def get_resource_base() -> str:
    """バイナリ・アセットのベースディレクトリを返す。

    PyInstaller バンドル時は sys._MEIPASS、開発時はプロジェクトルートを返す。
    """
    if getattr(sys, '_MEIPASS', None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
