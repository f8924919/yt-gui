# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import subprocess

# ビルド前にプラットフォーム向けのバイナリを自動取得する
subprocess.run(
    [sys.executable, os.path.join(SPECPATH, 'download_binaries.py')],
    check=True,
)

# プラットフォームに応じたバイナリファイル名を決定
_ext = '.exe' if sys.platform == 'win32' else ''
deno_bin = f'deno{_ext}'
ffmpeg_bin = f'ffmpeg{_ext}'

a = Analysis(
    ['yt.py'],
    pathex=[],
    binaries=[
        (os.path.join(SPECPATH, deno_bin), '.'),
        (os.path.join(SPECPATH, 'ffmpeg', ffmpeg_bin), 'ffmpeg'),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt',
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
    name='yt',
)
