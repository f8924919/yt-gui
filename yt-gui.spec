# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import struct
import subprocess
import tomllib

from PyInstaller.utils.hooks import copy_metadata

# バージョンは pyproject.toml を唯一のソースとして読み取る
with open(os.path.join(SPECPATH, 'pyproject.toml'), 'rb') as _f:
    _app_version = tomllib.load(_f)['project']['version']

# ビルド前にプラットフォーム向けのバイナリを自動取得する
subprocess.run(
    [sys.executable, os.path.join(SPECPATH, 'scripts', 'download_binaries.py')],
    check=True,
)

# プラットフォームに応じたバイナリファイル名を決定
_ext = '.exe' if sys.platform == 'win32' else ''
deno_bin = f'deno{_ext}'
ffmpeg_bin = f'ffmpeg{_ext}'
ffprobe_bin = f'ffprobe{_ext}'
danmaku2ass_bin = f'danmaku2ass{_ext}'

_bin_dir = os.path.join(SPECPATH, 'bin')
_png_path = os.path.join(SPECPATH, 'assets', 'icon.png')
_extra_binaries = [
    (os.path.join(_bin_dir, deno_bin), '.'),
    (os.path.join(_bin_dir, 'ffmpeg', ffmpeg_bin), 'ffmpeg'),
    (os.path.join(_bin_dir, 'ffmpeg', ffprobe_bin), 'ffmpeg'),
    (os.path.join(_bin_dir, danmaku2ass_bin), '.'),
]


def _png_to_ico(png_path: str) -> str:
    """PNG ファイルから ICO ファイルを生成してパスを返す。"""
    with open(png_path, 'rb') as f:
        png_data = f.read()

    width = struct.unpack('>I', png_data[16:20])[0]
    height = struct.unpack('>I', png_data[20:24])[0]
    w = 0 if width >= 256 else width
    h = 0 if height >= 256 else height

    ico_header = struct.pack('<HHH', 0, 1, 1)
    entry_offset = 6 + 16
    ico_entry = struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(png_data), entry_offset)

    ico_path = png_path.replace('.png', '_generated.ico')
    with open(ico_path, 'wb') as f:
        f.write(ico_header + ico_entry + png_data)
    return ico_path


def _png_to_icns(png_path: str) -> str:
    """PNG から .icns を生成して返す（macOS 専用）"""
    import tempfile, shutil
    iconset_dir = tempfile.mkdtemp(suffix='.iconset')
    try:
        sizes = [16, 32, 64, 128, 256, 512]
        for s in sizes:
            subprocess.run(['sips', '-z', str(s), str(s), png_path,
                            '--out', os.path.join(iconset_dir, f'icon_{s}x{s}.png')],
                           check=True, capture_output=True)
            subprocess.run(['sips', '-z', str(s*2), str(s*2), png_path,
                            '--out', os.path.join(iconset_dir, f'icon_{s}x{s}@2x.png')],
                           check=True, capture_output=True)
        icns_path = png_path.replace('.png', '_generated.icns')
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', icns_path],
                       check=True, capture_output=True)
        return icns_path
    finally:
        shutil.rmtree(iconset_dir, ignore_errors=True)


if sys.platform == 'darwin':
    _icon_path = _png_to_icns(_png_path) if os.path.isfile(_png_path) else None
elif sys.platform == 'win32':
    _icon_path = _png_to_ico(_png_path) if os.path.isfile(_png_path) else None
else:
    _icon_path = None

_extra_datas = [(_png_path, 'assets')] if os.path.isfile(_png_path) else []
# importlib.metadata.version("yt-gui") をバンドル実行時にも解決できるよう
# パッケージのメタデータ（dist-info）を同梱する
_extra_datas += copy_metadata('yt-gui')

# GPL/MIT 同梱バイナリのライセンス・著作権・対応ソース告知をバンドルに含める。
# download_binaries.py が bin/licenses/ に抽出・生成済み（上の subprocess 実行で更新される）。
_license_src = os.path.join(SPECPATH, 'LICENSE')
if os.path.isfile(_license_src):
    _extra_datas.append((_license_src, 'licenses'))
_licenses_dir = os.path.join(_bin_dir, 'licenses')
if os.path.isdir(_licenses_dir):
    for _root, _dirs, _files in os.walk(_licenses_dir):
        _rel = os.path.relpath(_root, _licenses_dir)
        _dest = 'licenses' if _rel == '.' else os.path.join('licenses', _rel)
        for _fn in _files:
            _extra_datas.append((os.path.join(_root, _fn), _dest))


def _version_tuple(version: str) -> tuple:
    """"0.1.0" → (0, 1, 0, 0)。Windows バージョンリソースは 4 整数を要求する。"""
    parts = []
    for token in version.split('.'):
        digits = ''.join(c for c in token if c.isdigit())  # 1rc2 等の接尾辞を除去
        parts.append(int(digits) if digits else 0)
    parts = (parts + [0, 0, 0, 0])[:4]
    return tuple(parts)


def _build_win_version_info(version: str):
    """Windows .exe のバージョンリソース（VSVersionInfo）を組み立てる。"""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    vt = _version_tuple(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=vt, prodvers=vt),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', 'yt-gui'),
                    StringStruct('FileDescription', 'yt-dlp GUI Downloader'),
                    StringStruct('FileVersion', version),
                    StringStruct('InternalName', 'yt-gui'),
                    StringStruct('OriginalFilename', 'yt-gui.exe'),
                    StringStruct('ProductName', 'yt-gui'),
                    StringStruct('ProductVersion', version),
                ]),
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ],
    )


# Windows ビルド時のみ .exe にバージョンリソースを埋め込む
_win_version = _build_win_version_info(_app_version) if sys.platform == 'win32' else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=_extra_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-gui',
    icon=_icon_path,
    version=_win_version,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt-gui',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='yt-gui.app',
        icon=_icon_path,
        bundle_identifier='com.example.yt-gui',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': _app_version,
        },
    )
elif sys.platform == 'linux':
    # Linux では PyInstaller COLLECT 出力を AppImage 化する
    subprocess.run(
        [sys.executable, os.path.join(SPECPATH, 'scripts', 'build_appimage.py'),
         '--force'],
        check=True,
    )
