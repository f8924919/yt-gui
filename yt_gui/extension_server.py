"""ブラウザ拡張連携のローカル受信サーバー（127.0.0.1 限定）。

ブラウザ拡張から `POST /enqueue {url, cookies?, format?}` を受け取り、
`on_enqueue` コールバックへ委譲する。トークン認証と Origin 制限で保護する。

このモジュールは Qt 非依存である。ハンドラはサーバースレッドで動くため、
`on_enqueue` 内で Qt ウィジェットを直接操作してはならない（メインスレッドへ
シグナル等で委譲すること）。検証・パースのコアは純関数 `handle_request` に
分離し、ソケットを使わず単体テストできるようにしている。

仕様: docs/spec/features/browser-extension.md
"""

from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

# enqueue コールバック: (url, cookies, format) を受け取る。受理した時点で
# 即時に戻り、実際のタイトル取得・キュー行確定はアプリ側が非同期に行う。
EnqueueCallback = Callable[[str, str | None, str | None], None]


class _HeaderLike(Protocol):
    """`dict` と `http.client.HTTPMessage` の両方を受けるための最小 Protocol。

    `HTTPMessage`（`email.message.Message`）は大文字小文字を無視して `get` を
    引けるため、ヘッダ参照はこのインタフェース越しに行う。
    """

    def get(self, key: str, default: str, /) -> str: ...


def handle_request(
    method: str,
    path: str,
    headers: _HeaderLike,
    body: bytes,
    *,
    expected_token: str,
    on_enqueue: EnqueueCallback,
) -> tuple[int, dict[str, Any]]:
    """1 リクエストを検証・パースし、(status, response_dict) を返す。

    妥当なリクエストのときだけ `on_enqueue` を呼ぶ。ソケットに依存しない
    純関数で、`BaseHTTPRequestHandler` と単体テストの両方から使う。
    """
    # Origin: chrome-extension スキームのみ許可（http(s) の Web ページは拒否）。
    # Origin ヘッダ自体が無い場合（curl 等）はトークンのみで判定する。
    origin = headers.get("Origin", "")
    if origin and not origin.startswith("chrome-extension://"):
        return 403, {"ok": False, "error": "forbidden_origin"}

    # トークン認証（タイミング攻撃を避けるため compare_digest）。
    token = headers.get("X-YtGui-Token", "")
    if not expected_token or not secrets.compare_digest(token, expected_token):
        return 403, {"ok": False, "error": "unauthorized"}

    if path != "/enqueue":
        return 404, {"ok": False, "error": "not_found"}
    if method != "POST":
        return 405, {"ok": False, "error": "method_not_allowed"}

    try:
        data = json.loads(body.decode("utf-8"))
    except ValueError, UnicodeDecodeError:
        return 400, {"ok": False, "error": "invalid_json"}
    if not isinstance(data, dict):
        return 400, {"ok": False, "error": "invalid_json"}

    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return 400, {"ok": False, "error": "invalid_url"}

    cookies = data.get("cookies")
    if cookies is not None and not isinstance(cookies, str):
        return 400, {"ok": False, "error": "invalid_cookies"}

    fmt = data.get("format")
    if not isinstance(fmt, str):
        fmt = None

    on_enqueue(url.strip(), cookies, fmt)
    return 200, {"ok": True}


def _make_handler(
    expected_token: str, on_enqueue: EnqueueCallback
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        # クッキー・トークンが標準出力へ漏れないようアクセスログを無効化する。
        def log_message(self, *args: Any) -> None:  # noqa: A002
            pass

        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length > 0 else b""
            status, payload = handle_request(
                method,
                self.path,
                self.headers,
                body,
                expected_token=expected_token,
                on_enqueue=on_enqueue,
            )
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

    return _Handler


class ExtensionServer:
    """ローカル受信サーバーのライフサイクル管理（127.0.0.1 限定）。"""

    def __init__(
        self,
        token: str,
        on_enqueue: EnqueueCallback,
        *,
        port: int,
        fallback_ports: tuple[int, ...] = (),
    ) -> None:
        self._token = token
        self._on_enqueue = on_enqueue
        self._port = port
        self._fallback_ports = fallback_ports
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._bound_port: int | None = None

    @property
    def bound_port(self) -> int | None:
        return self._bound_port

    def start(self) -> int | None:
        """空いているポートにバインドしてサーバースレッドを起動する。

        バインドできたポート番号を返す。全ポートが使用中なら `None`。
        """
        handler = _make_handler(self._token, self._on_enqueue)
        for port in (self._port, *self._fallback_ports):
            try:
                httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            except OSError:
                continue
            self._httpd = httpd
            self._bound_port = httpd.server_address[1]
            self._thread = threading.Thread(
                target=httpd.serve_forever, daemon=True, name="ExtensionServer"
            )
            self._thread.start()
            return self._bound_port
        return None

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._bound_port = None
