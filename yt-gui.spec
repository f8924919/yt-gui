# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import struct
import subprocess

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

_bin_dir = os.path.join(SPECPATH, 'bin')
_png_path = os.path.join(SPECPATH, 'assets', 'icon.png')
_extra_binaries = [
    (os.path.join(_bin_dir, deno_bin), '.'),
    (os.path.join(_bin_dir, 'ffmpeg', ffmpeg_bin), 'ffmpeg'),
    (os.path.join(_bin_dir, 'ffmpeg', ffprobe_bin), 'ffmpeg'),
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
            'CFBundleShortVersionString': '0.1.0',
        },
    )
elif sys.platform == 'linux':
    # Linux では PyInstaller COLLECT 出力を AppImage 化する
    subprocess.run(
        [sys.executable, os.path.join(SPECPATH, 'scripts', 'build_appimage.py'),
         '--force'],
        check=True,
    )
