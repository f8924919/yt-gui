"""ブラウザ拡張連携のローカル受信サーバーを検証する。

対応 spec: docs/spec/features/browser-extension.md
"""

import json
import socket
import urllib.error
import urllib.request

import pytest

from yt_gui.extension_server import ExtensionServer, handle_request

TOKEN = "test-token-abc"
EXT_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


def _call(method, path, headers, body, token=TOKEN):
    """handle_request を呼び、(status, data, captured) を返す。"""
    captured: list = []

    def on_enqueue(url, cookies, fmt):
        captured.append((url, cookies, fmt))

    status, data = handle_request(
        method,
        path,
        headers,
        body,
        expected_token=token,
        on_enqueue=on_enqueue,
    )
    return status, data, captured


# ── handle_request: 正常系 ────────────────────────────────────────────────


def test_valid_post_enqueues_and_returns_200():
    body = json.dumps({"url": "https://example.com/v", "cookies": "C"}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 200
    assert data == {"ok": True}
    assert captured == [("https://example.com/v", "C", None)]


def test_url_is_stripped():
    body = json.dumps({"url": "  https://example.com/v  "}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 200
    assert captured[0][0] == "https://example.com/v"


def test_cookies_omitted_passes_none():
    body = json.dumps({"url": "https://example.com/v"}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    _status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert captured[0][1] is None


def test_format_passed_through():
    body = json.dumps({"url": "https://example.com/v", "format": "fmt_mp3"}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    _status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert captured[0][2] == "fmt_mp3"


def test_missing_origin_with_token_allowed():
    """Origin ヘッダ無し（curl 等）でもトークンが正しければ受理。"""
    body = json.dumps({"url": "https://example.com/v"}).encode()
    headers = {"X-YtGui-Token": TOKEN}
    status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 200
    assert len(captured) == 1


# ── handle_request: 認証 ──────────────────────────────────────────────────


def test_missing_token_returns_403():
    body = json.dumps({"url": "https://example.com/v"}).encode()
    headers = {"Origin": EXT_ORIGIN}
    status, data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 403
    assert data["ok"] is False
    assert captured == []


def test_wrong_token_returns_403():
    body = json.dumps({"url": "https://example.com/v"}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": "wrong"}
    status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 403
    assert captured == []


def test_http_origin_rejected():
    """通常の Web ページ origin は拒否（CSRF 防止）。"""
    body = json.dumps({"url": "https://example.com/v"}).encode()
    headers = {"Origin": "https://evil.example.com", "X-YtGui-Token": TOKEN}
    status, data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 403
    assert data["error"] == "forbidden_origin"
    assert captured == []


# ── handle_request: メソッド/パス/ボディ ──────────────────────────────────


def test_wrong_path_returns_404():
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, _data, _c = _call("POST", "/other", headers, b"{}")
    assert status == 404


def test_get_method_returns_405():
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, _data, _c = _call("GET", "/enqueue", headers, b"")
    assert status == 405


def test_invalid_json_returns_400():
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, data, captured = _call("POST", "/enqueue", headers, b"not json")
    assert status == 400
    assert captured == []


def test_missing_url_returns_400():
    body = json.dumps({"cookies": "C"}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 400
    assert captured == []


def test_non_string_cookies_returns_400():
    body = json.dumps({"url": "https://example.com/v", "cookies": 123}).encode()
    headers = {"Origin": EXT_ORIGIN, "X-YtGui-Token": TOKEN}
    status, _data, captured = _call("POST", "/enqueue", headers, body)
    assert status == 400
    assert captured == []


# ── ExtensionServer: 実バインドの統合テスト ────────────────────────────────


def _post(port, body, token=TOKEN, origin=EXT_ORIGIN):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/enqueue",
        data=body,
        method="POST",
        headers={"X-YtGui-Token": token, "Origin": origin},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_binds_and_handles_post():
    captured: list = []
    server = ExtensionServer(
        TOKEN, lambda *a: captured.append(a), port=0  # 0 = OS 任意ポート
    )
    port = server.start()
    try:
        assert port is not None
        body = json.dumps({"url": "https://example.com/v"}).encode()
        status, data = _post(port, body)
        assert status == 200
        assert data == {"ok": True}
        # ハンドラは別スレッド。captured 反映を少し待つ
        for _ in range(50):
            if captured:
                break
            import time

            time.sleep(0.01)
        assert captured == [("https://example.com/v", None, None)]
    finally:
        server.stop()


def test_server_falls_back_when_port_in_use():
    # 既定ポートを占有してフォールバックされることを確認
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    busy_port = occupied.getsockname()[1]

    # 別の空きポートをフォールバック先として用意
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()

    server = ExtensionServer(
        TOKEN, lambda *a: None, port=busy_port, fallback_ports=(free_port,)
    )
    try:
        bound = server.start()
        assert bound == free_port
    finally:
        server.stop()
        occupied.close()
