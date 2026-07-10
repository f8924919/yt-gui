"""
Script to fetch platform-specific binaries (deno, ffmpeg) before building.
Called automatically when running: pyinstaller yt-gui.spec
Can also be run manually.
"""

import hashlib
import json
import os
import platform
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
BIN_DIR = os.path.join(_PROJECT_DIR, "bin")
# 同梱バイナリのピン留め台帳（バージョン・URL・sha256）。取得物をこの sha256 で検証。
PINS_PATH = os.path.join(BIN_DIR, "pins.json")
# 同梱バイナリのライセンス本文・告知の保存先（バンドル時に licenses/ へ同梱される）
LICENSES_DIR = os.path.join(BIN_DIR, "licenses")

# 配布アーカイブ内でライセンス本文とみなすファイル名（basename, 小文字比較）
_LICENSE_BASENAMES = frozenset(
    {
        "license",
        "license.txt",
        "license.md",
        "copying",
        "copying.txt",
        "gplv3.txt",
        "gplv2.txt",
        "gpl.txt",
    }
)


def _make_executable(path):
    if sys.platform != "win32":
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _download(url, dest):
    print(f"  -> {url}")
    urllib.request.urlretrieve(url, dest)


def _load_pins() -> dict:
    """ピン留め台帳 bin/pins.json を読み込む。"""
    with open(PINS_PATH, encoding="utf-8") as f:
        return dict(json.load(f))


def _sha256_of(path: str) -> str:
    """ファイルの sha256 を 16 進文字列で返す。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_sha256(path: str, expected: str, label: str) -> None:
    """取得物の sha256 を台帳の期待値と照合する。

    不一致・期待値未設定のときは取得物を削除して `RuntimeError` を送出し中断する
    （改ざんまたは上流更新を検知。サイレントに続行しない）。
    """
    if not expected:
        raise RuntimeError(
            f"[{label}] bin/pins.json に sha256 が未設定です。ネット接続環境で取得物の "
            f"sha256 を上流チェックサム／署名で確認のうえ台帳へ登録してください。"
        )
    actual = _sha256_of(path)
    if actual.lower() != expected.lower():
        os.remove(path)
        raise RuntimeError(
            f"[{label}] sha256 不一致のため中断します。\n"
            f"  期待: {expected}\n  実際: {actual}\n"
            f"取得物が台帳と異なります（改ざん、または上流が更新された可能性）。"
        )


def _download_verified(url: str, dest: str, expected: str, label: str) -> None:
    """ダウンロード後に sha256 を検証する。不一致なら例外を送出して中断する。"""
    _download(url, dest)
    _verify_sha256(dest, expected, label)


def _is_license_name(name: str) -> bool:
    """アーカイブ内エントリ名がライセンス本文ファイルかを basename で判定する。"""
    return os.path.basename(name).lower() in _LICENSE_BASENAMES


def _save_license_text(component: str, filename: str, data: bytes) -> None:
    """抽出したライセンス本文を bin/licenses/<component>/<filename> に保存する。"""
    dest_dir = os.path.join(LICENSES_DIR, component)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, os.path.basename(filename)), "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# deno
# ---------------------------------------------------------------------------


def _deno_asset():
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "deno-x86_64-pc-windows-msvc.zip", "deno.exe"
    elif sys.platform == "darwin":
        arch = "aarch64" if machine == "arm64" else "x86_64"
        return f"deno-{arch}-apple-darwin.zip", "deno"
    else:
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"deno-{arch}-unknown-linux-gnu.zip", "deno"


def download_deno(force=False):
    asset, binary = _deno_asset()
    os.makedirs(BIN_DIR, exist_ok=True)
    out_path = os.path.join(BIN_DIR, binary)

    if os.path.exists(out_path) and not force:
        print(f"[deno] {binary} already exists. Skipping.")
        return

    pins = _load_pins()["deno"]
    url = f"{pins['base_url']}/{asset}"
    expected = pins["assets"].get(asset)
    tmp = os.path.join(BIN_DIR, "_deno_tmp.zip")
    print(f"[deno] Downloading {pins['version']}...")
    _download_verified(url, tmp, expected, f"deno {asset}")

    with zipfile.ZipFile(tmp) as z:
        z.extract(binary, BIN_DIR)
    os.remove(tmp)
    _make_executable(out_path)
    print(f"[deno] Saved: {out_path}")


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------


def download_ffmpeg(force=False):
    machine = platform.machine().lower()
    ffmpeg_dir = os.path.join(BIN_DIR, "ffmpeg")
    os.makedirs(ffmpeg_dir, exist_ok=True)

    _ext = ".exe" if sys.platform == "win32" else ""
    ffmpeg_path = os.path.join(ffmpeg_dir, f"ffmpeg{_ext}")
    ffprobe_path = os.path.join(ffmpeg_dir, f"ffprobe{_ext}")

    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path) and not force:
        print("[ffmpeg] ffmpeg / ffprobe already exist. Skipping.")
        return

    if sys.platform == "win32":
        _download_ffmpeg_windows(ffmpeg_path, ffprobe_path)
    elif sys.platform == "darwin":
        _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path)
    else:
        _download_ffmpeg_linux(machine, ffmpeg_dir, ffmpeg_path, ffprobe_path)

    print(f"[ffmpeg] Saved: {ffmpeg_dir}")


def _download_ffmpeg_windows(ffmpeg_path, ffprobe_path):
    pins = _load_pins()["ffmpeg-win"]
    tmp = os.path.join(BIN_DIR, "_ffmpeg_tmp.zip")
    print(f"[ffmpeg] Downloading (Windows {pins['version']})...")
    _download_verified(pins["url"], tmp, pins["sha256"], "ffmpeg-win")

    with zipfile.ZipFile(tmp) as z:
        for name, out in (("ffmpeg.exe", ffmpeg_path), ("ffprobe.exe", ffprobe_path)):
            entry = next(n for n in z.namelist() if n.endswith(f"/bin/{name}"))
            with open(out, "wb") as f:
                f.write(z.read(entry))
        # BtbN ビルドはアーカイブ直下に LICENSE / COPYING 等を同梱する
        for entry in z.namelist():
            if not entry.endswith("/") and _is_license_name(entry):
                _save_license_text("ffmpeg", entry, z.read(entry))
    os.remove(tmp)


def _download_ffmpeg_macos(ffmpeg_dir, ffmpeg_path, ffprobe_path):
    # macOS は arch 別に取得元が異なる（pins.json の ffmpeg-mac.<arch>）:
    #   x86_64 = evermeet.cx（zip の sha256 を検証）
    #   arm64  = osxexperts.net（公開値が展開後バイナリの sha256 のため展開後に検証）
    # いずれも ffmpeg / ffprobe を個別 ZIP で配布する。
    machine = platform.machine().lower()
    arch = "arm64" if machine == "arm64" else "x86_64"
    pins = _load_pins()["ffmpeg-mac"][arch]
    verify_mode = pins.get("verify", "zip")
    for tool, out_path in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)):
        url = pins[tool]["url"]
        expected = pins[tool]["sha256"]
        label = f"ffmpeg-mac {arch} {tool}"
        tmp = os.path.join(BIN_DIR, f"_{tool}_tmp.zip")
        print(f"[ffmpeg] Downloading {tool} (macOS {arch} {pins['version']})...")
        # zip 検証なら DL 時に、binary 検証なら展開後に sha256 を照合する
        if verify_mode == "zip":
            _download_verified(url, tmp, expected, label)
        else:
            _download(url, tmp)
        with zipfile.ZipFile(tmp) as z:
            # __MACOSX/._<tool>（AppleDouble）を除外して実体エントリを選ぶ
            entry = next(
                n
                for n in z.namelist()
                if os.path.basename(n) == tool
                and not os.path.basename(n).startswith("._")
            )
            z.extract(entry, ffmpeg_dir)
            extracted = os.path.join(ffmpeg_dir, entry)
            if extracted != out_path:
                os.replace(extracted, out_path)
        os.remove(tmp)
        if verify_mode == "binary":
            _verify_sha256(out_path, expected, label)
        _make_executable(out_path)


def _download_ffmpeg_linux(machine, ffmpeg_dir, ffmpeg_path, ffprobe_path):
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    pins = _load_pins()["ffmpeg-linux"]
    entry = pins["assets"][arch]
    tmp = os.path.join(BIN_DIR, "_ffmpeg_tmp.tar.xz")
    print(f"[ffmpeg] Downloading (Linux {arch} {pins['version']})...")
    _download_verified(entry["url"], tmp, entry["sha256"], f"ffmpeg-linux {arch}")

    # johnvansickle.com tarball contains both ffmpeg and ffprobe
    with tarfile.open(tmp, "r:xz") as t:
        for binary, out_path in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)):
            member = next(
                (
                    m
                    for m in t.getmembers()
                    if os.path.basename(m.name) == binary and m.isfile()
                ),
                None,
            )
            if member:
                src = t.extractfile(member)
                assert src is not None  # isfile() 済みメンバーなので None にならない
                with open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                _make_executable(out_path)
        # johnvansickle の tarball は LICENSE.txt / GPLv3.txt 等を同梱する
        for member in t.getmembers():
            if member.isfile() and _is_license_name(member.name):
                src = t.extractfile(member)
                if src is not None:
                    _save_license_text("ffmpeg", member.name, src.read())
    os.remove(tmp)


# ---------------------------------------------------------------------------
# danmaku2ass (ニコニコ動画コメント → ASS 字幕変換)
# ---------------------------------------------------------------------------
# 単一 Python スクリプト danmaku2ass.py を PyInstaller で onefile バイナリ化し
# bin/ 配下へ配置する。GPL-3.0 ライセンスのため、ffmpeg と同様に同意プロンプト
# を経由する。
# 再現性のため master 追従ではなくコミットハッシュで固定する（pins.json が単一ソース）。
# git のコミット SHA は内容アドレスのため、sha256 検証の対象外とする。

_danmaku2ass_pin = _load_pins()["danmaku2ass"]
DANMAKU2ASS_REPO = _danmaku2ass_pin["repo"]
DANMAKU2ASS_REF = _danmaku2ass_pin["ref"]


def download_danmaku2ass(force=False):
    _ext = ".exe" if sys.platform == "win32" else ""
    out_path = os.path.join(BIN_DIR, f"danmaku2ass{_ext}")
    os.makedirs(BIN_DIR, exist_ok=True)

    if os.path.exists(out_path) and not force:
        print(f"[danmaku2ass] {out_path} already exists. Skipping.")
        return

    tmpdir = tempfile.mkdtemp(prefix="danmaku2ass-build-")
    try:
        print("[danmaku2ass] Cloning source...")
        subprocess.run(
            ["git", "clone", "--quiet", DANMAKU2ASS_REPO, tmpdir],
            check=True,
        )
        subprocess.run(
            ["git", "-C", tmpdir, "checkout", "--quiet", DANMAKU2ASS_REF],
            check=True,
        )

        print("[danmaku2ass] Building with PyInstaller (onefile)...")
        work_dir = os.path.join(tmpdir, "_build")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--onefile",
                "--name",
                "danmaku2ass",
                "--distpath",
                BIN_DIR,
                "--workpath",
                work_dir,
                "--specpath",
                work_dir,
                "--noconfirm",
                "--log-level",
                "WARN",
                os.path.join(tmpdir, "danmaku2ass.py"),
            ],
            check=True,
        )
        _make_executable(out_path)
        print(f"[danmaku2ass] Saved: {out_path}")

        # clone したソースからライセンス本文を保存する
        for name in os.listdir(tmpdir):
            if _is_license_name(name) and os.path.isfile(os.path.join(tmpdir, name)):
                with open(os.path.join(tmpdir, name), "rb") as f:
                    _save_license_text("danmaku2ass", name, f.read())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# サードパーティライセンス告知（属性表示 + 対応ソースの書面オファー）
# ---------------------------------------------------------------------------
# GPL / MIT の再配布義務に基づき、同梱する各コンポーネントの著作権・ライセンス・
# 対応ソース入手先を列挙したファイルを生成し、バンドルに同梱する。

COMPONENTS = [
    {
        "name": "FFmpeg (ffmpeg, ffprobe)",
        "license": "GPL（同梱ビルドは libx264/x265 等を含む GPL 構成）",
        "copyright": "Copyright (c) the FFmpeg developers",
        "homepage": "https://ffmpeg.org/",
        "source": "https://ffmpeg.org/download.html#get-sources",
        "distribution": (
            "Windows: https://github.com/BtbN/FFmpeg-Builds (win64-gpl) / "
            "macOS x86_64: https://evermeet.cx/ffmpeg/ / "
            "macOS arm64: https://www.osxexperts.net/ / "
            "Linux: https://johnvansickle.com/ffmpeg/"
        ),
        "note": (
            "同梱バイナリの正確なライセンス・ビルド構成は "
            "`ffmpeg -version` の出力で確認できる。"
        ),
    },
    {
        "name": "danmaku2ass",
        "license": "GPL-3.0",
        "copyright": "Copyright (c) Star Brilliant and danmaku2ass contributors",
        "homepage": "https://github.com/m13253/danmaku2ass",
        "source": f"{DANMAKU2ASS_REPO} (ref: {DANMAKU2ASS_REF})",
        "distribution": "ソースから PyInstaller でビルドして同梱",
        "note": "ニコニコ動画コメント JSON → ASS 字幕変換に使用。",
    },
    {
        "name": "Deno",
        "license": "MIT",
        "copyright": "Copyright (c) the Deno authors",
        "homepage": "https://deno.com/",
        "source": "https://github.com/denoland/deno",
        "distribution": "https://github.com/denoland/deno/releases",
        "note": "yt-dlp の JavaScript ランタイムとして使用。",
    },
]


def write_third_party_notices(dest_dir: str = LICENSES_DIR) -> str:
    """同梱コンポーネントの属性表示・対応ソース入手先を Markdown で書き出す。

    GPL の「対応ソース提供」義務に対する書面のオファーを兼ねる。ネットワークに
    依存しない純粋関数として実装し、生成パスを返す。
    """
    os.makedirs(dest_dir, exist_ok=True)
    lines = [
        "# サードパーティライセンス",
        "",
        "yt-gui は以下の外部コンポーネントを同梱して配布しています。各ライセンスの",
        "条件に従い、著作権表示・ライセンス・対応ソースコードの入手先を以下に示します。",
        "",
        "GPL コンポーネントの対応ソースコードは、以下「対応ソース」の URL から"
        "入手できます。",
        "本ファイルは GPL が要求する対応ソース提供の書面によるオファーを兼ねます。",
        "各コンポーネントのライセンス全文は、本バンドル内の `licenses/` 配下",
        "（取得元アーカイブに同梱されていたもの）および本体の `LICENSE`（GPLv3）を"
        "参照してください。",
        "",
    ]
    for c in COMPONENTS:
        lines += [
            f"## {c['name']}",
            "",
            f"- ライセンス: {c['license']}",
            f"- 著作権表示: {c['copyright']}",
            f"- 公式サイト: {c['homepage']}",
            f"- 配布元: {c['distribution']}",
            f"- 対応ソース: {c['source']}",
            f"- 備考: {c['note']}",
            "",
        ]
    content = "\n".join(lines)
    out_path = os.path.join(dest_dir, "THIRD-PARTY-NOTICES.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[licenses] Wrote: {out_path}")
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
        answer = (
            input("Do you agree to download ffmpeg under the GPL license? [y/N] ")
            .strip()
            .lower()
        )
    except EOFError, KeyboardInterrupt:
        print()
        return False
    return answer in ("y", "yes")


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
        answer = (
            input("Do you agree to build danmaku2ass under the GPL-3.0 license? [y/N] ")
            .strip()
            .lower()
        )
    except EOFError, KeyboardInterrupt:
        print()
        return False
    return answer in ("y", "yes")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update", action="store_true", help="Force re-download of existing binaries"
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip all confirmation prompts (for CI/automated builds)",
    )
    args = parser.parse_args()

    download_deno(force=args.update)

    _ext = ".exe" if sys.platform == "win32" else ""
    _ffmpeg_path = os.path.join(BIN_DIR, "ffmpeg", f"ffmpeg{_ext}")
    _ffprobe_path = os.path.join(BIN_DIR, "ffmpeg", f"ffprobe{_ext}")
    _needs_ffmpeg = (
        not (os.path.exists(_ffmpeg_path) and os.path.exists(_ffprobe_path))
        or args.update
    )

    if _needs_ffmpeg and not args.yes and not _prompt_ffmpeg_consent():
        print("[ffmpeg] Download cancelled.")
        sys.exit(0)

    download_ffmpeg(force=args.update)

    _danmaku2ass_path = os.path.join(BIN_DIR, f"danmaku2ass{_ext}")
    _needs_danmaku2ass = not os.path.exists(_danmaku2ass_path) or args.update

    if _needs_danmaku2ass and not args.yes and not _prompt_danmaku2ass_consent():
        print("[danmaku2ass] Build cancelled.")
        sys.exit(0)

    download_danmaku2ass(force=args.update)

    # 同梱コンポーネントのライセンス告知を生成（属性表示 + 対応ソースの書面オファー）
    write_third_party_notices()
