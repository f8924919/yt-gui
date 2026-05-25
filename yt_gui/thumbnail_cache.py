"""動画サムネイル画像の非同期取得・キャッシュ。

URL ごとに 1 度だけ HTTP 取得して base64 data URI に変換し、キュー
ツリーのツールチップ画像として再利用する。取得は `threading.Thread`
で行い、`thumbnail_ready` シグナル経由でメインスレッドへ通知する。
"""

from __future__ import annotations

import base64
import threading
import urllib.request

from PySide6.QtCore import QObject, Signal


class ThumbnailCache(QObject):
    """URL → data URI のキャッシュとバックグラウンド取得。

    - `get(url)` はキャッシュ済みなら data URI を返し、未取得なら None。
    - `request(url)` は未取得・取得中でなければバックグラウンド取得を起動する。
    - 取得完了時に `thumbnail_ready(url)` を emit する (主にツールチップの
      強制再描画用。現状は emit 利用者なしでも安全)。
    """

    thumbnail_ready = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cache: dict[str, str] = {}
        self._fetching: set[str] = set()
        self._lock = threading.Lock()

    def get(self, url: str | None) -> str | None:
        if not url:
            return None
        with self._lock:
            return self._cache.get(url)

    def request(self, url: str | None) -> None:
        if not url:
            return
        with self._lock:
            if url in self._cache or url in self._fetching:
                return
            self._fetching.add(url)
        threading.Thread(target=self._fetch, args=(url,), daemon=True).start()

    def _fetch(self, url: str) -> None:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                ct = resp.headers.get("Content-Type", "image/jpeg")
                content_type = ct.split(";")[0].strip() if ct else "image/jpeg"
            b64 = base64.b64encode(data).decode("ascii")
            data_uri = f"data:{content_type};base64,{b64}"
            with self._lock:
                self._cache[url] = data_uri
                self._fetching.discard(url)
            self.thumbnail_ready.emit(url)
        except Exception:
            with self._lock:
                self._fetching.discard(url)
