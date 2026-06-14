# yt_gui/extension_server.py

> 関連仕様: [ブラウザ拡張連携](../spec/features/browser-extension.md)

ブラウザ拡張から `POST /enqueue` を受け取るローカル受信サーバー（`127.0.0.1` 限定）。標準ライブラリの `http.server`（`ThreadingHTTPServer`）のみで実装し、新規依存を増やさない。

## Qt 非依存・スレッド規約

本モジュールは **Qt に依存しない**。リクエストは `ThreadingHTTPServer` のワーカースレッドで処理されるため、`on_enqueue` コールバック内で Qt ウィジェットを直接操作してはならない。呼び出し側（`app.py`）がシグナル等でメインスレッドへ委譲する（[スレッド間通信](index.md#スレッド間通信パターン)）。

## 公開 API

### `handle_request(method, path, headers, body, *, expected_token, on_enqueue) -> tuple[int, dict]`

1 リクエストを検証・パースして `(status, response_dict)` を返す純関数。ソケットに依存しないため `BaseHTTPRequestHandler` と単体テストの両方から使う。検証順とレスポンス:

| 条件 | status | error |
|---|---|---|
| `Origin` が `chrome-extension://` 以外（http(s) 等） | 403 | `forbidden_origin` |
| トークン欠如/不一致（`secrets.compare_digest`） | 403 | `unauthorized` |
| パスが `/enqueue` 以外 | 404 | `not_found` |
| メソッドが `POST` 以外 | 405 | `method_not_allowed` |
| JSON 不正・非 dict | 400 | `invalid_json` |
| `url` が無い/空 | 400 | `invalid_url` |
| `cookies` が文字列でない | 400 | `invalid_cookies` |
| `format` が dict でも欠落でもない | 400 | `invalid_format` |
| 妥当 | 200 | — (`{"ok": true}`、`on_enqueue(url, cookies, format)` を呼ぶ) |

- `Origin` ヘッダ自体が無い場合（curl 等）はトークンのみで判定する。
- `format` は[形式指定オブジェクト](../spec/features/browser-extension.md#形式指定オブジェクトformat)（dict）。欠落（`None`）は許容してそのまま渡す。dict 以外（文字列・配列・数値等）は `400`（`invalid_format`）。`on_enqueue(url, cookies, format)` の `format` 引数の型は `dict | None`。**中身の検証・許可値クランプ・既定フォールバックは呼び出し側（`app.py`）が行う**（サーバー層は構造の型のみ検証し、未知 `kind` や余分フィールドはそのまま透過する）。
- ヘッダ参照は `_HeaderLike` Protocol（`get` のみ要求）越しに行い、`dict` と `http.client.HTTPMessage`（大文字小文字無視）の両対応とする。

### `ExtensionServer(token, on_enqueue, *, port, fallback_ports=())`

サーバーのライフサイクル管理。

| メソッド/属性 | 説明 |
|---|---|
| `start() -> int \| None` | `port` → `fallback_ports` の順にバインドを試み、成功したポート番号を返す。全て使用中なら `None`。デーモンスレッドで `serve_forever` を回す |
| `stop() -> None` | `shutdown()` / `server_close()` してスレッドを join する |
| `bound_port` (property) | バインド済みポート（未起動/停止後は `None`） |

## セキュリティ

- バインドは `127.0.0.1` のみ（外部公開しない）。
- トークンは主防御、Origin 制限は多層防御。`BaseHTTPRequestHandler.log_message` を無効化し、クッキー・トークンを標準出力へ漏らさない。
