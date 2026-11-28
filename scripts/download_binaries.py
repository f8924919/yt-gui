"""
Script to fetch platform-specific binaries (deno, ffmpeg) before building.
Called automatically when running: pyinstaller yt-gui.spec
Can also be run manually.
"""

import datetime
import email.utils
import hashlib
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
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


# CI ランナーで urlretrieve（既定 UA・timeout なし）のみ取得破損が観測された
# ため、refresh_pins.py と同イディオム（urlopen チャンク書き込み・timeout・
# UA ヘッダー）に揃える（#265）。
_DOWNLOAD_TIMEOUT_SEC = 300
_DOWNLOAD_UA = "yt-gui-build (+https://github.com/f8924919/yt-gui)"


def _download(url, dest):
    """URL を dest へ取得し、応答の Content-Length（不明なら None）を返す。"""
    print(f"  -> {url}")
    req = urllib.request.Request(url, headers={"User-Agent": _DOWNLOAD_UA})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SEC) as resp:
        length = resp.headers.get("Content-Length")
        with open(dest, "wb") as f:
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                f.write(chunk)
    return int(length) if length else None


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


class PinConfigError(RuntimeError):
    """bin/pins.json の設定エラー（sha256 未設定など）。

    取り直しても直らないので、取得のリトライは即時に中断する。
    """


def _verify_sha256(path: str, expected: str, label: str) -> None:
    """取得物の sha256 を台帳の期待値と照合する。

    不一致のときは取得物を削除して `RuntimeError` を、期待値未設定のときは
    `PinConfigError` を送出し中断する（改ざんまたは上流更新を検知。サイレントに
    続行しない）。
    """
    if not expected:
        raise PinConfigError(
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


# --- 取得のリトライ（#265、#413） ------------------------------------------
# 仕様: docs/build.md「ピン留めと sha256 検証」のリトライの段落。
# 429 / 503 は配布元の回数制限・過負荷なので、既定の長い待ちと Retry-After の
# 長いほうだけ待ち（1 回は上限で切る）、取得の回数も増やす。それ以外の失敗は
# 短い指数バックオフ。2 種類の失敗は別々に数え、それぞれの上限で止まる。
_THROTTLE_STATUSES = frozenset({429, 503})
_THROTTLE_WAITS_SEC = (30.0, 60.0, 120.0, 120.0)
_THROTTLE_MAX_WAIT_SEC = 120.0
# 429 / 503 のときの取得の最大回数（待ちの列の長さから導く）
_THROTTLE_ATTEMPTS = len(_THROTTLE_WAITS_SEC) + 1


def _is_throttle(exc: BaseException) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code in _THROTTLE_STATUSES


def _retry_after_sec(exc: BaseException, now) -> float | None:
    """`Retry-After`（秒数・HTTP 日付）を秒に換算する。読めなければ `None`。

    例外処理の中で呼ぶので、どんな入力でも例外を出さない。秒数は数字だけ
    （RFC 9110 の delay-seconds）を受け付け、日付はタイムゾーンが無ければ
    UTC とみなす。0 以下・過去の日付は `None`。
    """
    try:
        if not isinstance(exc, urllib.error.HTTPError) or exc.headers is None:
            return None
        value = exc.headers.get("Retry-After")
        if value is None:
            return None
        value = str(value).strip()
        if re.fullmatch(r"[0-9]+", value):
            seconds = float(int(value))
        else:
            when = email.utils.parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.UTC)
            seconds = float(math.ceil(when.timestamp() - now()))
        return seconds if seconds > 0 else None
    except ValueError, TypeError, OverflowError, AttributeError:
        return None


def _retry_after_raw(exc: BaseException) -> str:
    """診断用の `Retry-After` の生の値（印字できる ASCII だけ・40 文字まで）。"""
    try:
        if isinstance(exc, urllib.error.HTTPError) and exc.headers is not None:
            value = exc.headers.get("Retry-After")
            if value is not None:
                return re.sub(r"[^\x20-\x7e]", "", str(value))[:40]
    except Exception:  # 診断用。失敗しても元の例外を隠さない
        pass
    return "なし"


def _download_retrying(
    url: str,
    dest: str,
    label: str,
    *,
    check=None,
    retries: int = 3,
    backoff_initial_sec: float = 2.0,
    sleep=None,
    now=None,
) -> None:
    """`url` を `dest` へ取得し、`check()`（あれば）を通す。失敗は待って取り直す。

    - `PinConfigError`（台帳の設定エラー）は取り直さず即時に送出する。
    - 429 / 503 は `_THROTTLE_ATTEMPTS` 回まで取得し、既定の待ちと Retry-After の
      長いほう（`_THROTTLE_MAX_WAIT_SEC` で切る）だけ待つ。
    - それ以外の失敗（他の HTTP エラー・接続失敗・timeout・`check` の失敗）は
      `retries` 回まで取得し、`backoff_initial_sec` からの指数バックオフで待つ。

    取り尽くしたら、最後の状態と待った秒の合計を出してから最後の例外を送出する。
    毎試行の失敗時に、取得破損の切り分け用診断（取得バイト数・応答の
    Content-Length・ファイル先頭 16 バイト hex・HTTP の状態・Retry-After・
    次に待つ秒数）を出力する。
    """
    sleep = sleep or time.sleep
    now = now or time.time
    throttled = 0
    others = 0
    waited = 0.0
    attempt = 0
    while True:
        attempt += 1
        # 前試行の部分ファイルを掃除してから再取得する。
        if os.path.exists(dest):
            os.remove(dest)
        content_length = None
        size: object = "なし"
        head = "なし"
        try:
            content_length = _download(url, dest)
            # 診断情報は照合前に取得する（_verify_sha256 は不一致時に削除する）。
            if os.path.exists(dest):
                size = os.path.getsize(dest)
                with open(dest, "rb") as f:
                    head = f.read(16).hex()
            if check is not None:
                check()
            return
        except PinConfigError:
            raise  # 台帳の設定エラー: 取り直しても直らない
        except Exception as exc:
            status = exc.code if isinstance(exc, urllib.error.HTTPError) else "なし"
            raw = _retry_after_raw(exc)
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            if _is_throttle(exc):
                throttled += 1
                give_up = throttled >= _THROTTLE_ATTEMPTS
                wait = 0.0
                if not give_up:
                    hinted = _retry_after_sec(exc, now) or 0.0
                    wait = min(
                        max(hinted, _THROTTLE_WAITS_SEC[throttled - 1]),
                        _THROTTLE_MAX_WAIT_SEC,
                    )
            else:
                others += 1
                give_up = others >= retries
                wait = 0.0 if give_up else backoff_initial_sec * 2 ** (others - 1)
            print(
                f"  [{label}] 試行 {attempt} 失敗"
                f"（429/503 {throttled}/{_THROTTLE_ATTEMPTS}・"
                f"その他 {others}/{retries}）"
                f" ({type(exc).__name__}): サイズ={size}"
                f" Content-Length={content_length} 先頭={head}"
                f" 状態={status} Retry-After={raw}"
                f" 次の待ち={'なし' if give_up else f'{wait:g} 秒'}"
            )
            if give_up:
                print(
                    f"  [{label}] 取得を断念: 最後の状態={status}"
                    f" 待った合計={waited:g} 秒"
                )
                raise
            sleep(wait)
            waited += wait


def _download_verified(
    url: str,
    dest: str,
    expected: str,
    label: str,
    *,
    retries: int = 3,
    backoff_initial_sec: float = 2.0,
    sleep=None,
) -> None:
    """ダウンロード後に zip などの sha256 を検証する。失敗は取り直す（#265、#413）。

    取り直しの規則は `_download_retrying`。sha256 不一致は取り直し、sha256 未設定
    （`PinConfigError`）は即時中断する。全滅時は最後の例外を送出して従来どおり
    ビルドを中断する（fail-closed は `_verify_sha256` 側で維持）。
    """
    _download_retrying(
        url,
        dest,
        label,
        check=lambda: _verify_sha256(dest, expected, label),
        retries=retries,
        backoff_initial_sec=backoff_initial_sec,
        sleep=sleep,
    )


def _check_zip(path: str, tool: str) -> None:
    """取得した zip が壊れていない（CRC が合い、対象のファイルがある）ことを確かめる。

    転送中に壊れた zip を取得ごと取り直すための検査（#413）。壊れていれば
    `zipfile.BadZipFile` を送出する。
    """
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad is not None:
            raise zipfile.BadZipFile(f"CRC が合わない: {bad}")
        if not any(_is_tool_entry(n, tool) for n in z.namelist()):
            raise zipfile.BadZipFile(f"{tool} が zip に無い")


def _is_tool_entry(name: str, tool: str) -> bool:
    """zip の entry が対象のツールの実体か（`__MACOSX/._<tool>` は除く）。"""
    base = os.path.basename(name)
    return base == tool and not base.startswith("._") and "__MACOSX" not in name


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
            entry = next((n for n in z.namelist() if n.endswith(f"/bin/{name}")), None)
            if entry is None:
                raise RuntimeError(
                    f"[ffmpeg-win] アーカイブ内に bin/{name} が見つかりません"
                    "（上流レイアウト変更の可能性）"
                )
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
            # 照合は展開後なので、取り直すのは取得と zip の破損だけ（#413）。
            # 展開後の sha256 不一致は差し替え・改ざんの疑いなので取り直さない。
            _download_retrying(
                url, tmp, label, check=lambda t=tmp, n=tool: _check_zip(t, n)
            )
        with zipfile.ZipFile(tmp) as z:
            # __MACOSX/._<tool>（AppleDouble）を除外して実体エントリを選ぶ
            entry = next(n for n in z.namelist() if _is_tool_entry(n, tool))
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

    # BtbN の tar.xz は win の zip と同じく ffmpeg-*/bin/ 配下に両バイナリを持つ
    with tarfile.open(tmp, "r:xz") as t:
        for binary, out_path in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)):
            member = next(
                (
                    m
                    for m in t.getmembers()
                    if m.isfile() and m.name.endswith(f"/bin/{binary}")
                ),
                None,
            )
            if member is None:
                raise RuntimeError(
                    f"[ffmpeg-linux] アーカイブ内に bin/{binary} が見つかりません"
                    "（上流レイアウト変更の可能性）"
                )
            src = t.extractfile(member)
            assert src is not None  # isfile() 済みメンバーなので None にならない
            with open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            _make_executable(out_path)
        # BtbN の tarball はアーカイブ直下に LICENSE.txt を同梱する
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

# niconicomments（MIT）の許諾表示の全文。`yt_gui/nico_ass.py` の
# `NICONICOMMENTS_LICENSE` と同じ（tests/test_download_binaries.py が一致を確かめる）。
_NICONICOMMENTS_LICENSE = """\
MIT License

Copyright (c) 2022 xpadev-net

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


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
            "Linux: https://github.com/BtbN/FFmpeg-Builds "
            "(linux64-gpl / linuxarm64-gpl)"
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
    {
        "name": "niconicomments",
        "license": "MIT",
        "copyright": "Copyright (c) 2022 xpadev-net",
        "homepage": "https://github.com/xpadev-net/niconicomments",
        "source": ("https://github.com/xpadev-net/niconicomments (ref: 899203436285)"),
        "distribution": "式・定数・色表を yt_gui/nico_ass.py に移植して同梱",
        "note": "ニコニコ動画コメント → ASS 字幕変換（#387）の移植元。",
        "license_text": _NICONICOMMENTS_LICENSE,
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
        if c.get("license_text"):
            lines += ["```text", c["license_text"], "```", ""]
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
