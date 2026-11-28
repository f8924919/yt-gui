"""bin/pins.json を上流の最新版へ更新する（週次 Workflow / 手動から実行）。

各コンポーネントの上流最新を解決し、**上流チェックサム／署名で真正性を確認**してから
version / url / sha256 を更新する（docs/research/binary-supply-chain.md §5）。
更新があれば pins.json を書き換え、PR 本文用のサマリ（旧→新・検証根拠）を出力する。

- 検証に失敗した場合は例外で停止する（pins.json は書き換えない）。
- danmaku2ass は git の SHA 固定（内容アドレス性）のため対象外。
- BtbN（ffmpeg の win / linux）は最新の不変 `autobuild-*` タグへ再ピンする。
  リリース一覧の解決は `refresh_pins()` が 1 回だけ行い、win / linux の両
  refresher へ同一リリースを注入して同一タグ・同一バージョンに揃える（#272）。
  再ピンは **ffmpeg のバージョンが変わっていなくても毎回行う**。BtbN は古い
  `autobuild-*` タグを削除する（保持は直近約 2 週間の日次＋以前は月 1 本）ため、
  週次で再ピンし続けないとピン URL が 404 になる。「バージョン不変なら再ピンしない」
  最適化は入れてはならない（詳細は docs/build.md「再ピンは『ffmpeg のバージョンが
  変わったとき』だけではない」）。

`scripts/` はパッケージではないため download_binaries を同ディレクトリから import する。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

import download_binaries as db

_GH_HEADERS = {"Accept": "application/vnd.github+json"}
_UA = {"User-Agent": "yt-gui-pin-refresh"}


# --- 純粋ヘルパー（単体テスト対象） ---------------------------------------


def _parse_sha256sum(text: str) -> str:
    """sha256sum 系ファイルの本文から 64 桁 hex を取り出す。

    deno は `<hash>  <path>` 形式と、Windows 版の `Hash : <HASH>` 形式の両方を返す。
    最初の 64 桁 hex を採用することでどちらにも対応する。
    """
    m = re.search(r"[0-9a-fA-F]{64}", text)
    if not m:
        raise RuntimeError("sha256sum を解析できませんでした")
    return m.group(0).lower()


def _select_latest_autobuild(releases: list[dict]) -> dict:
    """BtbN の releases 一覧から最新の不変 `autobuild-*` リリースを選ぶ。

    ローリングの `latest` タグは除外し、`autobuild-YYYY-MM-DD-HH-MM` のうち
    タグ名（ゼロ埋め日時のため辞書順 = 時系列順）が最大のものを返す。これにより
    取得 URL が日付固定タグ配下＝不変アセットを指すようになる（#72）。

    タグは不変（中身がすり替わらない）だが**永続ではなく**、古いものは上流が
    削除する。常に最新を選び直すことでピンを保持期間内に保つ（モジュール
    docstring 参照）。
    """
    autobuilds = [
        r for r in releases if str(r.get("tag_name", "")).startswith("autobuild-")
    ]
    if not autobuilds:
        raise RuntimeError("BtbN に autobuild-* リリースが見つかりません")
    return max(autobuilds, key=lambda r: r["tag_name"])


def _select_btbn_versioned_asset(
    assets: list[dict], variant: str, ext: str
) -> tuple[str, str]:
    """autobuild リリースのアセット一覧から最新の安定版 `<variant>` を選ぶ。

    autobuild タグのアセットは `ffmpeg-nX.Y.Z-<N>-g<hash>-<variant>-X.Y.<ext>`
    形式（正確なバージョン+commit 入り。`latest` タグの `-latest-` 名とは異なる）。
    variant は `win64-gpl` / `linux64-gpl` / `linuxarm64-gpl`、ext は `zip` /
    `tar.xz`。末尾のリリースブランチ `X.Y` が最大のものを採用し、`(version, url)`
    を返す。version はアセット名のバージョントークン（例 `n8.1.1-9-g58d4114d36`）。
    master ローリング・shared 版・lgpl は除外する。
    """
    pattern = re.compile(
        r"^ffmpeg-(n\d+\.\d+(?:\.\d+)?(?:-\d+-g[0-9a-f]+)?)-"
        + re.escape(variant)
        + r"-(\d+)\.(\d+)\."
        + re.escape(ext)
        + r"$"
    )
    best: tuple[tuple[int, int], str, str] | None = None
    for asset in assets:
        name = asset.get("name", "")
        m = pattern.match(name)
        if not m:
            continue
        branch = (int(m.group(2)), int(m.group(3)))
        if best is None or branch > best[0]:
            best = (branch, m.group(1), asset["browser_download_url"])
    if best is None:
        raise RuntimeError(f"autobuild に安定版 {variant} アセットが見つかりません")
    return best[1], best[2]


# --- ネットワーク（実機検証） ---------------------------------------------


def _http_text(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={**_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text: str = resp.read().decode("utf-8", "replace")
    return text


def _http_json(url: str, headers: dict | None = None) -> Any:
    # GitHub API はエンドポイントにより dict（単一リリース）/ list（リリース一覧）の
    # 双方を返すため戻り値は Any とし、呼び出し側で適切に扱う。
    return json.loads(_http_text(url, {**_GH_HEADERS, **(headers or {})}))


def _hashes_of_url(url: str) -> tuple[str, int]:
    """URL をダウンロードして (sha256, size) を返す。"""
    fd, tmp = tempfile.mkstemp(prefix="pin-refresh-")
    os.close(fd)
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        sha = hashlib.sha256()
        with open(tmp, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                sha.update(chunk)
        return sha.hexdigest(), os.path.getsize(tmp)
    finally:
        os.remove(tmp)


# --- コンポーネント別リフレッシュ -----------------------------------------
# 各関数は (新コンポーネント dict, 旧→新サマリ用 dict) を返す。変更有無は呼び出し側で
# 旧 dict との比較により判定する。


def refresh_deno(old: dict) -> tuple[dict, str]:
    rel = _http_json("https://api.github.com/repos/denoland/deno/releases/latest")
    tag = rel["tag_name"]
    base = f"https://github.com/denoland/deno/releases/download/{tag}"
    new = dict(old)
    new["version"] = tag
    new["base_url"] = base
    if tag == old["version"]:
        return new, f"deno: {tag}（変更なし）"
    assets = {}
    for asset in old["assets"]:
        text = _http_text(f"{base}/{asset}.sha256sum")
        assets[asset] = _parse_sha256sum(text)
    new["assets"] = assets
    return new, f"deno: {old['version']} → {tag}（上流 .sha256sum と照合）"


def refresh_ffmpeg_win(old: dict, release: dict) -> tuple[dict, str]:
    # `releases/latest`（ローリング）ではなく、不変な `autobuild-*` タグの最新
    # リリースへ再ピンする（#72）。release は refresh_pins() が 1 回だけ解決した
    # 共有リリース（linux と同一タグ・同一バージョンに揃えるため。#272）。
    # version が old と同じでも再ピンする（上流が古いタグを消すため。冒頭 docstring）。
    version, url = _select_btbn_versioned_asset(
        release.get("assets", []), "win64-gpl", "zip"
    )
    sha, _size = _hashes_of_url(url)
    new = dict(old)
    new["version"] = version
    new["url"] = url
    new["sha256"] = sha
    note = f"（不変タグ {release['tag_name']} のアセットを取得し sha256 算出）"
    if version == old["version"] and sha == old["sha256"]:
        return new, f"ffmpeg-win: {version}（変更なし）"
    return new, f"ffmpeg-win: {old['version']} → {version} {note}"


def refresh_ffmpeg_mac(old: dict) -> tuple[dict, str]:
    # x86_64 は evermeet.cx の info API で自動追従する。arm64（osxexperts.net）は
    # API も署名サイドカーも無く、公開値はページ HTML 上の展開後バイナリ sha256 の
    # ため自動スクレイピングはせず、更新はページの公開値を人手で確認する運用とする
    # （docs/research/binary-supply-chain.md §5）。ここでは arm64 を現状維持する。
    # ただしピンが古くなったことは別途検知して知らせる（#412。docs/build.md
    # 「macOS arm64 のピンの古さの検知」）。
    new = dict(old)
    old_x86 = old["x86_64"]
    x86 = dict(old_x86)
    changed = False
    detail = []
    for tool in ("ffmpeg", "ffprobe"):
        info = _http_json(f"https://evermeet.cx/ffmpeg/info/{tool}/release")
        version = info["version"]
        entry = info["download"]["zip"]
        url = entry["url"]
        x86["version"] = version
        x86[tool] = dict(old_x86[tool])
        x86[tool]["url"] = url
        if version != old_x86["version"] or old_x86[tool].get("sha256") is None:
            sha, size = _hashes_of_url(url)
            x86[tool]["sha256"] = sha
            ok = size == entry.get("size")
            detail.append(
                f"{tool} {version}（sig: {'有' if entry.get('sig') else '無'} / "
                f"info size 一致: {'OK' if ok else 'NG'}）"
            )
            changed = changed or x86[tool]["sha256"] != old_x86[tool].get("sha256")
    new["x86_64"] = x86
    arm_version = old["arm64"]["version"]
    arm_note = f"arm64={arm_version}（osxexperts.net・手動更新）"
    if not _same_version(x86["version"], arm_version):
        # 版の差は判定に使わない（osxexperts の追従待ちの間は正当にずれる。#412）
        arm_note += "（x86_64 と版が異なる: osxexperts の追従待ちの可能性）"
    if not changed:
        return new, f"ffmpeg-mac: x86_64={old_x86['version']}（変更なし） / {arm_note}"
    return new, (
        f"ffmpeg-mac: x86_64 {old_x86['version']} → {x86['version']}"
        f"（TOFU: 別経路確認推奨） " + " / ".join(detail) + f" / {arm_note}"
    )


# pins.json の arch キーと BtbN アセットの variant の対応
_BTBN_LINUX_VARIANTS = {"amd64": "linux64-gpl", "arm64": "linuxarm64-gpl"}


def refresh_ffmpeg_linux(old: dict, release: dict) -> tuple[dict, str]:
    # win と同じ不変 `autobuild-*` タグへの再ピン方式（#272。バージョン不変でも
    # 再ピンする理由は冒頭 docstring）。release は
    # refresh_pins() が 1 回だけ解決した共有リリース（win と同一タグ保証）。
    # 旧 johnvansickle の `.md5` 照合は取得元廃止に伴い撤去。
    assets = release.get("assets", [])
    selected = {
        arch: _select_btbn_versioned_asset(assets, variant, "tar.xz")
        for arch, variant in _BTBN_LINUX_VARIANTS.items()
    }
    versions = {arch: version for arch, (version, _url) in selected.items()}
    if len(set(versions.values())) != 1:
        raise RuntimeError(
            f"ffmpeg-linux: amd64 / arm64 のバージョンが不一致です（{versions}）。"
            f"タグ {release.get('tag_name')} のアセットを確認してください。"
        )
    version = versions["amd64"]
    new = dict(old)
    new["version"] = version
    new["assets"] = {}
    changed = False
    for arch, (_version, url) in selected.items():
        sha, _size = _hashes_of_url(url)
        new["assets"][arch] = {"url": url, "sha256": sha}
        old_entry = old.get("assets", {}).get(arch, {})
        changed = changed or sha != old_entry.get("sha256")
    note = f"（不変タグ {release['tag_name']} のアセットを取得し sha256 算出）"
    if version == old.get("version") and not changed:
        return new, f"ffmpeg-linux: {version}（変更なし）"
    return new, f"ffmpeg-linux: {old.get('version')} → {version} {note}"


# --- macOS arm64（osxexperts.net）のピンの古さの検査（#412） -----------------
# 再ピンはしない（sha256 は人がページの公開値で確認して登録する）。ここでは
# ページ上の Apple Silicon 版とピンを比べ、古い・検査できないときに警告を返す。
# 仕様: docs/build.md「macOS arm64 のピンの古さの検知」。
#
# 警告文には、正規表現で絞った値（版・固定ホストの URL・sha256・HTTP の結果・
# 例外の型名）と固定の文言だけを入れる。第三者のページの HTML や例外メッセージの
# 生の文字列は、ジョブログ（`::error::`）と PR 本文に流れるので入れない。

_OSXEXPERTS_URL = "https://www.osxexperts.net/"
_ARM64_TOOLS = ("ffmpeg", "ffprobe")
_ALERT_STALE = "arm64 のピンが古い"
_ALERT_UNCHECKED = "arm64 のピンを検査できなかった"
_RERUN_HINT = "一時的な失敗なら workflow_dispatch で再実行して再現するか確認する"
# ページ取得の一時的な失敗（5xx・429・接続失敗）で取得し直すまでの待ち秒数（計 3 回）
_PAGE_RETRY_WAITS = (10.0, 30.0)


class ArmPageError(RuntimeError):
    """osxexperts.net のページから Apple Silicon 版を読めない。

    ページの構造の変化か、ランナーへのブロック。
    """


def _strip_trailing_zero(version: str) -> str:
    return version[:-2] if version.endswith(".0") else version


def _same_version(a: str, b: str) -> bool:
    """末尾の `.0` の有無を区別せずに版を比べる（9 と 9.0 は同じ）。"""
    return _strip_trailing_zero(a) == _strip_trailing_zero(b)


def _arm_link_tokens(version: str) -> set[str]:
    """版に対応するリンクの数字の候補（9.1 → 91、9.0 → 90 または 9）。

    osxexperts は 9.0 を `ffmpeg9arm.zip`、9.1 を `ffmpeg91arm.zip` と名付けている。
    """
    return {version.replace(".", ""), _strip_trailing_zero(version).replace(".", "")}


def _parse_osxexperts_arm64(html: str) -> dict[str, tuple[str, str]]:
    """ページから Apple Silicon 版の ffmpeg / ffprobe の `(版, URL)` を読む。

    ツールごとに、リンク `href="https://www.osxexperts.net/<tool><数字>arm.zip"` と
    文言 `Download <tool> <版> (Apple Silicon)` をちょうど 1 件ずつ探し、リンクの数字が
    文言の版に対応するときだけ採用する（版は文言を正とする）。見つからない・複数ある・
    食い違うときは `ArmPageError`。Intel 版（`...intel.zip` / `(Intel)`）と ffplay は
    ツール名と `arm.zip` / `(Apple Silicon)` で絞るので拾わない。
    """
    result = {}
    for tool in _ARM64_TOOLS:
        links = re.findall(
            r'href="(https://www\.osxexperts\.net/' + tool + r'(\d+)arm\.zip)"', html
        )
        texts = re.findall(
            r"Download " + tool + r" (\d+(?:\.\d+)*) \(Apple Silicon\)", html
        )
        if len(links) != 1 or len(texts) != 1:
            raise ArmPageError(
                f"{tool}: Apple Silicon 版のリンク {len(links)} 件・"
                f"文言 {len(texts)} 件"
            )
        (url, token), version = links[0], texts[0]
        if token not in _arm_link_tokens(version):
            raise ArmPageError(
                f"{tool}: リンクの数字 {token} と文言の版 {version} が食い違う"
            )
        result[tool] = (version, url)
    return result


def _url_ok(url: str, open_fn: Callable[..., Any] = urllib.request.urlopen) -> str:
    """ピンの URL が取れるかを、本体を落とさずに確かめる。

    HEAD（405 / 501 なら `Range: bytes=0-0` の GET）で問い合わせ、
    `"ok"`（取れる zip）/ `"gone"`（404・410、別 URL へのリダイレクト、zip でない応答）/
    `"error"`（タイムアウト・5xx・接続失敗など。古いとは言えない）を返す。
    """
    attempts = (
        urllib.request.Request(url, headers=_UA, method="HEAD"),
        urllib.request.Request(
            url, headers={**_UA, "Range": "bytes=0-0"}, method="GET"
        ),
    )
    for i, req in enumerate(attempts):
        try:
            with open_fn(req, timeout=60) as resp:
                ctype = str(resp.headers.get("Content-Type", "")).split(";")[0].strip()
                if resp.geturl() != url or ctype != "application/zip":
                    return "gone"
                return "ok"
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return "gone"
            if e.code in (405, 501) and i == 0:
                continue  # HEAD 非対応 → Range GET
            return "error"
        except urllib.error.URLError, OSError:
            return "error"
    return "error"


def _is_transient(e: BaseException) -> bool:
    """取得し直せば直りうる失敗か（5xx・429・接続失敗・タイムアウト）。"""
    if isinstance(e, urllib.error.HTTPError):
        return e.code == 429 or e.code >= 500
    return isinstance(e, (urllib.error.URLError, OSError))


def _fetch_page(fetch: Callable[[str], str], sleep: Callable[[float], None]) -> str:
    """osxexperts.net のページを取得する。一時的な失敗だけ待って取得し直す。

    手元でページ取得が HTTP 503 になったことがある（状態コードで確かめたのは 1 回。
    #412 のタスクメモ「C9」）。直後の取得はキャッシュ（Varnish）から 200 だったので、
    キャッシュが切れて配布元へ取りに行ったときの一時的な失敗とみられる。週次の実行は
    ランナーからの初回アクセスで、この条件に当たりやすいと考え、`_PAGE_RETRY_WAITS`
    の秒数だけ待って取得し直す。404 などの
    恒久的な失敗と、待ち尽くした最後の失敗はそのまま送出する。
    """
    for wait in (*_PAGE_RETRY_WAITS, None):
        try:
            return fetch(_OSXEXPERTS_URL)
        except Exception as e:
            if wait is None or not _is_transient(e):
                raise
            sleep(wait)
    raise AssertionError("unreachable")


def check_ffmpeg_mac_arm64(
    arm_pin: dict,
    fetch_text: Callable[[str], str] | None = None,
    url_ok: Callable[[str], str] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> list[str]:
    """arm64 のピンを osxexperts.net のページと比べ、警告の文字列のリストを返す。

    警告は `_ALERT_STALE`（古い）か `_ALERT_UNCHECKED`（検査できなかった）で始まる
    1 行の文字列。例外は外へ出さず、型名だけを入れた「検査できなかった」警告に変える
    （黙って通さない）。ピンは書き換えない。
    """
    fetch = fetch_text or _http_text
    check_url = url_ok or _url_ok
    try:
        try:
            html = _fetch_page(fetch, sleep or time.sleep)
        except Exception as e:
            # HTTPError は状態コードを入れる（429 / 403 / 503 の切り分け用。#412 の C9）
            detail = (
                f"HTTP {e.code}"
                if isinstance(e, urllib.error.HTTPError)
                else type(e).__name__
            )
            return [
                f"{_ALERT_UNCHECKED}: {_OSXEXPERTS_URL} を取得できない"
                f"（{detail}）。{_RERUN_HINT}"
            ]
        try:
            page = _parse_osxexperts_arm64(html)
        except ArmPageError:
            return [
                f"{_ALERT_UNCHECKED}: ページから Apple Silicon 版の"
                f"リンクと文言を読めない"
                f"（ページの構造の変化、またはブロック。応答 {len(html)} 文字・sha256 "
                f"{hashlib.sha256(html.encode('utf-8')).hexdigest()}）"
            ]
        alerts = []
        pin_version = arm_pin["version"]
        page_versions = {tool: page[tool][0] for tool in _ARM64_TOOLS}
        if not _same_version(page_versions["ffmpeg"], page_versions["ffprobe"]):
            alerts.append(
                f"{_ALERT_STALE}: ページ上で ffmpeg（{page_versions['ffmpeg']}）と "
                f"ffprobe（{page_versions['ffprobe']}）の版が違う"
                f"（ピンの version は 1 つなので、両方の公開値を確認して更新する）"
            )
        lowered = html.lower()
        for tool in _ARM64_TOOLS:
            page_version, page_url = page[tool]
            pin_url = arm_pin[tool]["url"]
            pin_sha = str(arm_pin[tool]["sha256"]).lower()
            if not _same_version(page_version, pin_version):
                alerts.append(
                    f"{_ALERT_STALE}: {tool}"
                    f"（ページ {page_version} / ピン {pin_version}）"
                )
            elif page_url != pin_url:
                alerts.append(
                    f"{_ALERT_STALE}: {tool} の URL がページと違う"
                    f"（ページ {page_version} {page_url} / ピン {pin_version}）"
                )
            if not re.fullmatch(r"[0-9a-f]{64}", pin_sha) or pin_sha not in lowered:
                alerts.append(
                    f"{_ALERT_STALE}: {tool} のピンの sha256 がページに無い"
                    f"（同じファイル名のまま配布物が差し替わった可能性）"
                )
            status = check_url(pin_url)
            if status == "gone":
                alerts.append(
                    f"{_ALERT_STALE}: {tool} のピンの URL が取得できない（404 など）"
                )
            elif status != "ok":
                alerts.append(
                    f"{_ALERT_UNCHECKED}: {tool} のピンの URL を確かめられない"
                    f"（タイムアウト・5xx など）。{_RERUN_HINT}"
                )
        return alerts
    except Exception as e:
        return [f"{_ALERT_UNCHECKED}: 検査中に想定外の例外（{type(e).__name__}）"]


def _write_alerts(path: str, alerts: list[str]) -> None:
    """警告を 1 行 1 件・LF 改行で書く。警告が無くても空ファイルを作る。"""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for alert in alerts:
            f.write(re.sub(r"[\r\n]+", " ", alert) + "\n")


# 値のシグネチャは fn(old) または fn(old, release)（BtbN 系のみ）の 2 種のため
# Callable[..., ...] で受ける。呼び分けは refresh_pins() が _BTBN_KEYS で行う。
_REFRESHERS: dict[str, Callable[..., tuple[dict, str]]] = {
    "deno": refresh_deno,
    "ffmpeg-win": refresh_ffmpeg_win,
    "ffmpeg-mac": refresh_ffmpeg_mac,
    "ffmpeg-linux": refresh_ffmpeg_linux,
}

# BtbN 共有リリースを注入する refresher（win / linux の同一タグ保証。#272）
_BTBN_KEYS = frozenset({"ffmpeg-win", "ffmpeg-linux"})
_BTBN_RELEASES_URL = (
    "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases?per_page=20"
)


def refresh_pins(pins: dict) -> tuple[dict, list[str], list[str]]:
    """pins を更新した新 dict と、(変更サマリ, 全コンポーネントの状況) を返す。

    BtbN の autobuild リリースはここで 1 回だけ解決し、win / linux の refresher へ
    同一リリースを注入する（同一タグ・同一バージョンの構造的保証。#272）。
    """
    btbn_release = _select_latest_autobuild(_http_json(_BTBN_RELEASES_URL))
    new_pins = dict(pins)
    changes = []
    statuses = []
    for key, fn in _REFRESHERS.items():
        if key in _BTBN_KEYS:
            new_component, summary = fn(pins[key], btbn_release)
        else:
            new_component, summary = fn(pins[key])
        statuses.append(summary)
        if new_component != pins[key]:
            changes.append(summary)
        new_pins[key] = new_component
    return new_pins, changes, statuses


def run(
    pins: dict, alerts_out: str | None = None
) -> tuple[dict, list[str], list[str], list[str]]:
    """arm64 の検査 → 警告の書き出し → 再ピン、の順に行う（IO は警告ファイルだけ）。

    検査と書き出しを再ピンより先に行うので、他の配布元の障害で `refresh_pins()` が
    例外になった週でも、arm64 の警告は警告ファイルに残る（#412）。
    """
    alerts = check_ffmpeg_mac_arm64(pins["ffmpeg-mac"]["arm64"])
    if alerts_out:
        _write_alerts(alerts_out, alerts)
    new_pins, changes, statuses = refresh_pins(pins)
    return new_pins, changes, statuses, alerts


def _build_summary(
    changes: list[str], statuses: list[str], alerts: list[str] | tuple = ()
) -> str:
    lines = ["## 同梱バイナリのピン更新", ""]
    if alerts:
        lines.append("> [!CAUTION]")
        lines.append(
            "> **macOS arm64 の ffmpeg / ffprobe のピン（osxexperts.net）に"
            "問題があります**。"
            "このワークフローは失敗として終わります。"
        )
        lines.append(">")
        lines += [f"> - {a}" for a in alerts]
        lines.append(">")
        lines.append(
            "> osxexperts.net のページで公開値（URL・展開後バイナリの sha256）を"
            "確認して "
            "`bin/pins.json` の `ffmpeg-mac.arm64` を手で更新すること"
            "（docs/build.md「macOS arm64 のピンの古さの検知」）。"
        )
        lines.append("")
    if changes:
        lines.append(
            "以下のコンポーネントを更新しました。**マージ前に上流の真正性を確認してください**。"
        )
        lines.append("")
        lines += [f"- {c}" for c in changes]
    else:
        lines.append("更新はありません。")
    lines += ["", "<details><summary>全コンポーネントの状況</summary>", ""]
    lines += [f"- {s}" for s in statuses]
    lines += ["", "</details>", ""]
    lines.append(
        "検証根拠は docs/research/binary-supply-chain.md §5 を参照。"
        "evermeet / osxexperts は TOFU のため、別経路での再確認を推奨します。"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-out", help="PR 本文用サマリ Markdown の出力先パス")
    parser.add_argument(
        "--alerts-out",
        help=(
            "macOS arm64 のピンの警告（1 行 1 件）の出力先パス。"
            "警告が無くても空ファイルを作る"
        ),
    )
    args = parser.parse_args()

    pins = db._load_pins()
    new_pins, changes, statuses, alerts = run(pins, alerts_out=args.alerts_out)
    for alert in alerts:
        # 行頭が `::` にならないよう前置きを付ける
        # （ワークフローコマンドとして解釈させない）
        print(f"[arm64] {alert}")

    if new_pins != pins:
        with open(db.PINS_PATH, "w", encoding="utf-8") as f:
            json.dump(new_pins, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[refresh] pins.json を更新しました（{len(changes)} 件）")
    else:
        print("[refresh] 更新はありません")

    summary = _build_summary(changes, statuses, alerts)
    print(summary)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
