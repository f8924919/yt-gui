"""
Build a Linux AppImage from the PyInstaller COLLECT output.

Called automatically from yt-gui.spec as a post-build step on Linux.
Can also be run manually after `pyinstaller yt-gui.spec`.
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
BIN_DIR = os.path.join(_PROJECT_ROOT, "bin")
DIST_DIR = os.path.join(_PROJECT_ROOT, "dist")
ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")

APP_NAME = "yt-gui"
APP_DISPLAY_NAME = "yt-gui"
APP_COMMENT = "PySide6-based yt-dlp GUI downloader"


def _app_version() -> str:
    """アプリのバージョン（pyproject.toml が単一ソース）を返す。"""
    try:
        from yt_gui import get_version

        return get_version()
    except Exception:
        return "unknown"


def _arch_name() -> str:
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "aarch64"
    return "x86_64"


def _make_executable(path: str) -> None:
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _download_appimagetool() -> str:
    arch = _arch_name()
    out_path = os.path.join(BIN_DIR, f"appimagetool-{arch}.AppImage")
    if os.path.exists(out_path):
        return out_path
    os.makedirs(BIN_DIR, exist_ok=True)
    url = (
        "https://github.com/AppImage/appimagetool/releases/download/"
        f"continuous/appimagetool-{arch}.AppImage"
    )
    print(f"[appimage] Downloading appimagetool: {url}")
    urllib.request.urlretrieve(url, out_path)
    _make_executable(out_path)
    return out_path


def _write_desktop_file(path: str) -> None:
    content = (
        "[Desktop Entry]\n"
        f"Name={APP_DISPLAY_NAME}\n"
        f"Exec={APP_NAME}\n"
        f"Icon={APP_NAME}\n"
        "Type=Application\n"
        "Categories=AudioVideo;Network;\n"
        f"Comment={APP_COMMENT}\n"
        "Terminal=false\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, 0o644)


def _write_apprun(path: str) -> None:
    content = (
        "#!/bin/sh\n"
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        f'exec "$HERE/usr/{APP_NAME}" "$@"\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    _make_executable(path)


def _build_appdir(collect_dir: str, appdir: str) -> None:
    if os.path.exists(appdir):
        shutil.rmtree(appdir)
    os.makedirs(appdir)

    # PyInstaller COLLECT 出力一式を usr/ 配下にコピー
    # （実行ファイルと _internal/ を一体で配置する必要があるため階層は維持）
    usr_dir = os.path.join(appdir, "usr")
    shutil.copytree(collect_dir, usr_dir)

    # アイコン（AppDir 直下に置くと appimagetool が .DirIcon として採用）
    icon_src = os.path.join(ASSETS_DIR, "icon.png")
    if os.path.isfile(icon_src):
        shutil.copy(icon_src, os.path.join(appdir, f"{APP_NAME}.png"))
        # XDG hicolor テーマ用の標準パスにも配置
        hicolor_dir = os.path.join(
            appdir, "usr", "share", "icons", "hicolor", "256x256", "apps"
        )
        os.makedirs(hicolor_dir, exist_ok=True)
        shutil.copy(icon_src, os.path.join(hicolor_dir, f"{APP_NAME}.png"))

    _write_desktop_file(os.path.join(appdir, f"{APP_NAME}.desktop"))
    _write_apprun(os.path.join(appdir, "AppRun"))


def build_appimage(force: bool = False) -> str:
    if sys.platform != "linux":
        raise RuntimeError("AppImage build is only supported on Linux.")

    collect_dir = os.path.join(DIST_DIR, APP_NAME)
    if not os.path.isdir(collect_dir):
        raise FileNotFoundError(
            f"PyInstaller COLLECT directory not found: {collect_dir}\n"
            "Run `pyinstaller yt-gui.spec` first."
        )

    arch = _arch_name()
    version = _app_version()
    appdir = os.path.join(DIST_DIR, f"{APP_NAME}.AppDir")
    out_path = os.path.join(DIST_DIR, f"{APP_NAME}-{version}-{arch}.AppImage")

    if os.path.exists(out_path) and not force:
        print(f"[appimage] {out_path} already exists. Skipping.")
        return out_path

    print("[appimage] Preparing AppDir...")
    _build_appdir(collect_dir, appdir)

    appimagetool = _download_appimagetool()
    env = os.environ.copy()
    env.setdefault("ARCH", arch)
    # appimagetool は VERSION を更新情報に埋め込む
    env.setdefault("VERSION", version)

    print("[appimage] Running appimagetool...")
    # --appimage-extract-and-run: FUSE が無い環境（CI/コンテナ等）でも動かすため
    subprocess.run(
        [appimagetool, "--appimage-extract-and-run", appdir, out_path],
        check=True,
        env=env,
    )
    print(f"[appimage] Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing AppImage",
    )
    args = parser.parse_args()

    if sys.platform != "linux":
        print("[appimage] Skipping: only Linux is supported.")
        sys.exit(0)

    build_appimage(force=args.force)
