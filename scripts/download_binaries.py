"""
Script to fetch platform-specific binaries (deno, ffmpeg) before building.
Called automatically when running: pyinstaller yt-gui.spec
Can also be run manually.
"""
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPTS_DIR)
BIN_DIR = os.path.join(_PROJECT_DIR, 'bin')
# 同梱バイナリのライセンス本文・告知の保存先（バンドル時に licenses/ へ同梱される）
LICENSES_DIR = os.path.join(BIN_DIR, 'licenses')

# 配布アーカイブ内でライセンス本文とみなすファイル名（basename, 小文字比較）
_LICENSE_BASENAMES = frozenset({
    'license', 'license.txt', 'license.md',
    'copying', 'copying.txt',
    'gplv3.txt', 'gplv2.txt', 'gpl.txt',
})


def _make_executable(path):
    if sys.platform != 'win32':
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _download(url, dest):
    print(f'  -> {url}')
    urllib.request.urlretrieve(url, dest)


def _is_license_name(name: str) -> bool:
    """アーカイブ内エントリ名がライセンス本文ファイルかを basename で判定する。"""
    return os.path.basename(name).lower() in _LICENSE_BASENAMES


def _save_license_text(component: str, filename: str, data: bytes) -> None:
    """抽出したライセンス本文を bin/licenses/<component>/<filename> に保存する。"""
    dest_dir = os.path.join(LICENSES_DIR, component)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, os.path.basename(filename)), 'wb') as f:
        f.write(data)


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
        print(f'[deno] {binary} already exists. Skipping.')
        return

    url = f'https://github.com/denoland/deno/releases/latest/download/{asset}'
    tmp = os.path.join(BIN_DIR, '_deno_tmp.zip')
    print('[deno] Downloading...')
    _download(url, tmp)

    with zipfile.ZipFile(tmp) as z:
        z.extract(binary, BIN_DIR)
    os.remove(tmp)
    _make_executable(out_path)
    print(f'[deno] Saved: {out_path}')


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
        print('[ffmpeg] ffmpeg / ffprobe already exist. Skipping.')
        return

    if sys.platform == 'win32':
        _download_ffmpeg_windows(ffmpeg_path, ffprobe_path)
    elif sys.platform == 'darwin':
        _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path)
    else:
        _download_ffmpeg_linux(machine, ffmpeg_dir, ffmpeg_path, ffprobe_path)

    print(f'[ffmpeg] Saved: {ffmpeg_dir}')


def _resolve_btbn_ffmpeg_win64_gpl_url() -> str:
    """BtbN/FFmpeg-Builds の最新リリースから win64-gpl の autobuild zip URL を解決する。

    BtbN のアセット名は過去に何度か変わっている:

    - 固定名 `ffmpeg-master-latest-win64-gpl.zip`（現行）
    - コミットハッシュ付き `ffmpeg-N-{N}-g{hash}-win64-gpl.zip`（一時期）

    固定 URL 直打ちでは命名変更のたびに 404 になるため、Releases API でアセット名を
    引いて動的に URL を解決する。shared 版（`-shared`）と安定版（末尾 `-X.Y.zip`）は
    除外し、master autobuild の static GPL ビルドだけを拾う。
    """
    api = 'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest'
    req = urllib.request.Request(api, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    return _select_btbn_win64_gpl_asset(data.get('assets', []))


def _select_btbn_win64_gpl_asset(assets: list[dict]) -> str:
    """Releases API のアセット一覧から win64-gpl (static / master) の URL を選ぶ。

    現行の `master-latest` 固定名と過去のハッシュ付き名の両方を許容する。`-shared`
    と安定版 `nX.Y`（末尾 `-X.Y.zip`）は正規表現の末尾固定（`-win64-gpl.zip` で終わる
    もののみ）で自然に除外される。
    """
    pattern = re.compile(r'^ffmpeg-(?:master-latest|N-\d+-g[0-9a-f]+)-win64-gpl\.zip$')
    for asset in assets:
        name = asset.get('name', '')
        if pattern.match(name):
            return asset['browser_download_url']

    raise RuntimeError(
        'No matching ffmpeg win64-gpl asset found in '
        'BtbN/FFmpeg-Builds latest release. Asset naming may have changed again.'
    )


def _download_ffmpeg_windows(ffmpeg_path, ffprobe_path):
    url = _resolve_btbn_ffmpeg_win64_gpl_url()
    tmp = os.path.join(BIN_DIR, '_ffmpeg_tmp.zip')
    print('[ffmpeg] Downloading (Windows)...')
    _download(url, tmp)

    with zipfile.ZipFile(tmp) as z:
        for name, out in (('ffmpeg.exe', ffmpeg_path), ('ffprobe.exe', ffprobe_path)):
            entry = next(n for n in z.namelist() if n.endswith(f'/bin/{name}'))
            with open(out, 'wb') as f:
                f.write(z.read(entry))
        # BtbN ビルドはアーカイブ直下に LICENSE / COPYING 等を同梱する
        for entry in z.namelist():
            if not entry.endswith('/') and _is_license_name(entry):
                _save_license_text('ffmpeg', entry, z.read(entry))
    os.remove(tmp)


def _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path):
    # evermeet.cx distributes ffmpeg and ffprobe as separate ZIPs
    for tool, out_path in (('ffmpeg', ffmpeg_path), ('ffprobe', ffprobe_path)):
        url = f'https://evermeet.cx/ffmpeg/getrelease/{tool}/zip'
        tmp = os.path.join(BIN_DIR, f'_{tool}_tmp.zip')
        print(f'[ffmpeg] Downloading {tool} (macOS)...')
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
    print(f'[ffmpeg] Downloading (Linux {arch})...')
    _download(url, tmp)

    # johnvansickle.com tarball contains both ffmpeg and ffprobe
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
        # johnvansickle の tarball は LICENSE.txt / GPLv3.txt 等を同梱する
        for member in t.getmembers():
            if member.isfile() and _is_license_name(member.name):
                src = t.extractfile(member)
                if src is not None:
                    _save_license_text('ffmpeg', member.name, src.read())
    os.remove(tmp)


# ---------------------------------------------------------------------------
# danmaku2ass (ニコニコ動画コメント → ASS 字幕変換)
# ---------------------------------------------------------------------------
# 単一 Python スクリプト danmaku2ass.py を PyInstaller で onefile バイナリ化し
# bin/ 配下へ配置する。GPL-3.0 ライセンスのため、ffmpeg と同様に同意プロンプト
# を経由する。
# 再現性のため master 追従ではなくコミットハッシュで固定する。

DANMAKU2ASS_REPO = 'https://github.com/m13253/danmaku2ass.git'
DANMAKU2ASS_REF = 'ced881747670c2eb1c0dbd292c2a567f444b056a'  # 2024-08-28


def download_danmaku2ass(force=False):
    _ext = '.exe' if sys.platform == 'win32' else ''
    out_path = os.path.join(BIN_DIR, f'danmaku2ass{_ext}')
    os.makedirs(BIN_DIR, exist_ok=True)

    if os.path.exists(out_path) and not force:
        print(f'[danmaku2ass] {out_path} already exists. Skipping.')
        return

    tmpdir = tempfile.mkdtemp(prefix='danmaku2ass-build-')
    try:
        print('[danmaku2ass] Cloning source...')
        subprocess.run(
            ['git', 'clone', '--quiet', DANMAKU2ASS_REPO, tmpdir],
            check=True,
        )
        subprocess.run(
            ['git', '-C', tmpdir, 'checkout', '--quiet', DANMAKU2ASS_REF],
            check=True,
        )

        print('[danmaku2ass] Building with PyInstaller (onefile)...')
        work_dir = os.path.join(tmpdir, '_build')
        subprocess.run(
            [
                sys.executable, '-m', 'PyInstaller',
                '--onefile',
                '--name', 'danmaku2ass',
                '--distpath', BIN_DIR,
                '--workpath', work_dir,
                '--specpath', work_dir,
                '--noconfirm',
                '--log-level', 'WARN',
                os.path.join(tmpdir, 'danmaku2ass.py'),
            ],
            check=True,
        )
        _make_executable(out_path)
        print(f'[danmaku2ass] Saved: {out_path}')

        # clone したソースからライセンス本文を保存する
        for name in os.listdir(tmpdir):
            if _is_license_name(name) and os.path.isfile(os.path.join(tmpdir, name)):
                with open(os.path.join(tmpdir, name), 'rb') as f:
                    _save_license_text('danmaku2ass', name, f.read())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# サードパーティライセンス告知（属性表示 + 対応ソースの書面オファー）
# ---------------------------------------------------------------------------
# GPL / MIT の再配布義務に基づき、同梱する各コンポーネントの著作権・ライセンス・
# 対応ソース入手先を列挙したファイルを生成し、バンドルに同梱する。

COMPONENTS = [
    {
        'name': 'FFmpeg (ffmpeg, ffprobe)',
        'license': 'GPL（同梱ビルドは libx264/x265 等を含む GPL 構成）',
        'copyright': 'Copyright (c) the FFmpeg developers',
        'homepage': 'https://ffmpeg.org/',
        'source': 'https://ffmpeg.org/download.html#get-sources',
        'distribution': (
            'Windows: https://github.com/BtbN/FFmpeg-Builds (win64-gpl) / '
            'macOS: https://evermeet.cx/ffmpeg/ / '
            'Linux: https://johnvansickle.com/ffmpeg/'
        ),
        'note': (
            '同梱バイナリの正確なライセンス・ビルド構成は '
            '`ffmpeg -version` の出力で確認できる。'
        ),
    },
    {
        'name': 'danmaku2ass',
        'license': 'GPL-3.0',
        'copyright': 'Copyright (c) Star Brilliant and danmaku2ass contributors',
        'homepage': 'https://github.com/m13253/danmaku2ass',
        'source': f'{DANMAKU2ASS_REPO} (ref: {DANMAKU2ASS_REF})',
        'distribution': 'ソースから PyInstaller でビルドして同梱',
        'note': 'ニコニコ動画コメント JSON → ASS 字幕変換に使用。',
    },
    {
        'name': 'Deno',
        'license': 'MIT',
        'copyright': 'Copyright (c) the Deno authors',
        'homepage': 'https://deno.com/',
        'source': 'https://github.com/denoland/deno',
        'distribution': 'https://github.com/denoland/deno/releases',
        'note': 'yt-dlp の JavaScript ランタイムとして使用。',
    },
]


def write_third_party_notices(dest_dir: str = LICENSES_DIR) -> str:
    """同梱コンポーネントの属性表示・対応ソース入手先を Markdown で書き出す。

    GPL の「対応ソース提供」義務に対する書面のオファーを兼ねる。ネットワークに
    依存しない純粋関数として実装し、生成パスを返す。
    """
    os.makedirs(dest_dir, exist_ok=True)
    lines = [
        '# サードパーティライセンス',
        '',
        'yt-gui は以下の外部コンポーネントを同梱して配布しています。各ライセンスの',
        '条件に従い、著作権表示・ライセンス・対応ソースコードの入手先を以下に示します。',
        '',
        'GPL コンポーネントの対応ソースコードは、以下「対応ソース」の URL から'
        '入手できます。',
        '本ファイルは GPL が要求する対応ソース提供の書面によるオファーを兼ねます。',
        '各コンポーネントのライセンス全文は、本バンドル内の `licenses/` 配下',
        '（取得元アーカイブに同梱されていたもの）および本体の `LICENSE`（GPLv3）を'
        '参照してください。',
        '',
    ]
    for c in COMPONENTS:
        lines += [
            f'## {c["name"]}',
            '',
            f'- ライセンス: {c["license"]}',
            f'- 著作権表示: {c["copyright"]}',
            f'- 公式サイト: {c["homepage"]}',
            f'- 配布元: {c["distribution"]}',
            f'- 対応ソース: {c["source"]}',
            f'- 備考: {c["note"]}',
            '',
        ]
    content = '\n'.join(lines)
    out_path = os.path.join(dest_dir, 'THIRD-PARTY-NOTICES.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'[licenses] Wrote: {out_path}')
    return out_path


# ---------------------------------------------------------------------------

def _prompt_ffmpeg_consent() -> bool:
    """Show ffmpeg license notice and prompt for consent. Returns True if accepted."""
    print()
    print("=" * 60)
    print("ffmpeg License Notice")
    print("=" * 60)
    print("This script will download ffmpeg, which is licensed under")
    print("the GNU General Public License (GPL) v2 or later.")
    print()
    print("You must comply with the GPL license when distributing")
    print("any software that includes ffmpeg.")
    print()
    print("License details: https://ffmpeg.org/legal.html")
    print("=" * 60)
    try:
        answer = input(
            "Do you agree to download ffmpeg under the GPL license? [y/N] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ('y', 'yes')


def _prompt_danmaku2ass_consent() -> bool:
    """Show danmaku2ass license notice and prompt. Returns True if accepted."""
    print()
    print("=" * 60)
    print("danmaku2ass License Notice")
    print("=" * 60)
    print("This script will build danmaku2ass from source, which is")
    print("licensed under the GNU General Public License (GPL) v3.")
    print()
    print("danmaku2ass converts Niconico/Bilibili/AcFun comments to")
    print("ASS subtitle files (used by the Niconico comments feature).")
    print()
    print("Repository: https://github.com/m13253/danmaku2ass")
    print("=" * 60)
    try:
        answer = input(
            "Do you agree to build danmaku2ass under the GPL-3.0 license? [y/N] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ('y', 'yes')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--update', action='store_true', help='Force re-download of existing binaries'
    )
    parser.add_argument(
        '--yes', '-y', action='store_true',
        help='Skip all confirmation prompts (for CI/automated builds)'
    )
    args = parser.parse_args()

    download_deno(force=args.update)

    _ext = '.exe' if sys.platform == 'win32' else ''
    _ffmpeg_path = os.path.join(BIN_DIR, 'ffmpeg', f'ffmpeg{_ext}')
    _ffprobe_path = os.path.join(BIN_DIR, 'ffmpeg', f'ffprobe{_ext}')
    _needs_ffmpeg = (
        not (os.path.exists(_ffmpeg_path) and os.path.exists(_ffprobe_path))
        or args.update
    )

    if _needs_ffmpeg and not args.yes:
        if not _prompt_ffmpeg_consent():
            print('[ffmpeg] Download cancelled.')
            sys.exit(0)

    download_ffmpeg(force=args.update)

    _danmaku2ass_path = os.path.join(BIN_DIR, f'danmaku2ass{_ext}')
    _needs_danmaku2ass = not os.path.exists(_danmaku2ass_path) or args.update

    if _needs_danmaku2ass and not args.yes:
        if not _prompt_danmaku2ass_consent():
            print('[danmaku2ass] Build cancelled.')
            sys.exit(0)

    download_danmaku2ass(force=args.update)

    # 同梱コンポーネントのライセンス告知を生成（属性表示 + 対応ソースの書面オファー）
    write_third_party_notices()
