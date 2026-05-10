"""
ビルド前にプラットフォーム向けのバイナリ (deno, ffmpeg) を自動取得するスクリプト。
pyinstaller yt.spec 実行時に自動的に呼び出される。手動実行も可能。
"""
import sys
import os
import platform
import zipfile
import tarfile
import shutil
import urllib.request
import stat

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(os.path.dirname(_SCRIPTS_DIR), 'bin')


def _make_executable(path):
    if sys.platform != 'win32':
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _download(url, dest):
    print(f'  -> {url}')
    urllib.request.urlretrieve(url, dest)


# ---------------------------------------------------------------------------
# deno
# ---------------------------------------------------------------------------

def _deno_asset():
    machine = platform.machine().lower()
    if sys.platform == 'win32':
        return 'deno-x86_64-pc-windows-msvc.zip', 'deno.exe'
    elif sys.platform == 'darwin':
        arch = 'aarch64' if machine == 'arm64' else 'x86_64'
        return f'deno-{arch}-apple-darwin.zip', 'deno'
    else:
        arch = 'aarch64' if machine in ('arm64', 'aarch64') else 'x86_64'
        return f'deno-{arch}-unknown-linux-gnu.zip', 'deno'


def download_deno(force=False):
    asset, binary = _deno_asset()
    os.makedirs(BIN_DIR, exist_ok=True)
    out_path = os.path.join(BIN_DIR, binary)

    if os.path.exists(out_path) and not force:
        print(f'[deno] {binary} は既に存在します。スキップします。')
        return

    url = f'https://github.com/denoland/deno/releases/latest/download/{asset}'
    tmp = os.path.join(BIN_DIR, '_deno_tmp.zip')
    print(f'[deno] ダウンロード中...')
    _download(url, tmp)

    with zipfile.ZipFile(tmp) as z:
        z.extract(binary, BIN_DIR)
    os.remove(tmp)
    _make_executable(out_path)
    print(f'[deno] 保存完了: {out_path}')


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------

def download_ffmpeg(force=False):
    machine = platform.machine().lower()
    ffmpeg_dir = os.path.join(BIN_DIR, 'ffmpeg')
    os.makedirs(ffmpeg_dir, exist_ok=True)

    _ext = '.exe' if sys.platform == 'win32' else ''
    ffmpeg_path = os.path.join(ffmpeg_dir, f'ffmpeg{_ext}')
    ffprobe_path = os.path.join(ffmpeg_dir, f'ffprobe{_ext}')

    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path) and not force:
        print('[ffmpeg] ffmpeg / ffprobe は既に存在します。スキップします。')
        return

    if sys.platform == 'win32':
        _download_ffmpeg_windows(ffmpeg_path, ffprobe_path)
    elif sys.platform == 'darwin':
        _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path)
    else:
        _download_ffmpeg_linux(machine, ffmpeg_dir, ffmpeg_path, ffprobe_path)

    print(f'[ffmpeg] 保存完了: {ffmpeg_dir}')


def _download_ffmpeg_windows(ffmpeg_path, ffprobe_path):
    url = ('https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/'
           'ffmpeg-master-latest-win64-gpl.zip')
    tmp = os.path.join(BIN_DIR, '_ffmpeg_tmp.zip')
    print('[ffmpeg] ダウンロード中 (Windows)...')
    _download(url, tmp)

    with zipfile.ZipFile(tmp) as z:
        for name, out in (('ffmpeg.exe', ffmpeg_path), ('ffprobe.exe', ffprobe_path)):
            entry = next(n for n in z.namelist() if n.endswith(f'/bin/{name}'))
            with open(out, 'wb') as f:
                f.write(z.read(entry))
    os.remove(tmp)


def _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path):
    # evermeet.cx は ffmpeg / ffprobe を別 ZIP で配布している
    for tool, out_path in (('ffmpeg', ffmpeg_path), ('ffprobe', ffprobe_path)):
        url = f'https://evermeet.cx/ffmpeg/getrelease/{tool}/zip'
        tmp = os.path.join(BIN_DIR, f'_{tool}_tmp.zip')
        print(f'[ffmpeg] {tool} ダウンロード中 (macOS)...')
        _download(url, tmp)
        with zipfile.ZipFile(tmp) as z:
            entry = next(n for n in z.namelist() if os.path.basename(n) == tool)
            z.extract(entry, ffmpeg_dir)
            extracted = os.path.join(ffmpeg_dir, entry)
            if extracted != out_path:
                os.replace(extracted, out_path)
        os.remove(tmp)
        _make_executable(out_path)


def _download_ffmpeg_linux(machine, ffmpeg_dir, ffmpeg_path, ffprobe_path):
    arch = 'arm64' if machine in ('arm64', 'aarch64') else 'amd64'
    url = f'https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-{arch}-static.tar.xz'
    tmp = os.path.join(BIN_DIR, '_ffmpeg_tmp.tar.xz')
    print(f'[ffmpeg] ダウンロード中 (Linux {arch})...')
    _download(url, tmp)

    # johnvansickle.com の tarball には ffmpeg と ffprobe が両方含まれる
    with tarfile.open(tmp, 'r:xz') as t:
        for binary, out_path in (('ffmpeg', ffmpeg_path), ('ffprobe', ffprobe_path)):
            member = next(
                (m for m in t.getmembers()
                 if os.path.basename(m.name) == binary and m.isfile()),
                None,
            )
            if member:
                src = t.extractfile(member)
                with open(out_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                _make_executable(out_path)
    os.remove(tmp)


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true', help='既存のバイナリを強制的に再ダウンロードする')
    args = parser.parse_args()

    download_deno(force=args.update)
    download_ffmpeg(force=args.update)
