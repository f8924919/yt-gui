# -*- mode: python ; coding: utf-8 -*-
import sys
import os
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

_cookies_path = os.path.join(SPECPATH, 'cookies.txt')
_bin_dir = os.path.join(SPECPATH, 'bin')
_extra_binaries = [(os.path.join(_bin_dir, deno_bin), '.'), (os.path.join(_bin_dir, 'ffmpeg', ffmpeg_bin), 'ffmpeg')]
if os.path.isfile(_cookies_path):
    _extra_binaries.append((_cookies_path, '.'))

# Tcl/Tk データを明示的に収集する（PyInstaller の自動検出が失敗する場合の保険）
def _collect_tcltk_datas():
    try:
        import tkinter
        import _tkinter
        tcl = tkinter.Tcl()
        tcl_data_dir = tcl.eval("info library")
        tk_ver = _tkinter.TK_VERSION  # e.g. "8.6" or "9.0"
        tk_data_dir = os.path.join(os.path.dirname(tcl_data_dir), f"tk{tk_ver}")
        result = []
        if os.path.isdir(tcl_data_dir):
            result.append((tcl_data_dir, '_tcl_data'))
        if os.path.isdir(tk_data_dir):
            result.append((tk_data_dir, '_tk_data'))
        return result
    except Exception as e:
        print(f"[WARNING] Tcl/Tk data collection failed: {e}")
        return []

_tcltk_datas = _collect_tcltk_datas()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=_tcltk_datas,
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
