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
- `format` は[形式指定オブジェクト](../spec/features/browser-extension.md#形式指定オブジェクトformat)（dict）。欠落（`None`）は許容してそのまま渡す。dict 以外（文字列・配列・数値等）は `400`（`invalid_format`）。`on_enqueue(url, cookies, format)` の `format` 引数の型は `dict | None`。**中身の検証・許可値クランプ・既定フォールバックは呼び出し側（`app.py`）が行う**（サーバー層は構造の型のみ検証し、`kind: "original"`・未知 `kind`・余分フィールドはそのまま透過する。`original` 受信時のダイアログ起動も `app.py` 側の責務）。
- ヘッダ参照は `_HeaderLike` Protocol（`get` のみ要求）越しに行い、`dict` と `http.client.HTTPMessage`（大文字小文字無視）の両対応とする。

### `ExtensionServer(token, on_enqueue, *, port, fallback_ports=())`

サーバーのライフサイクル管理。

| メソッド/属性 | 説明 |
|---|---|
| `start() -> int \| None` | `port` → `fallback_ports` の順にバインドを試み、成功したポート番号を返す。全て使用中なら `None`。デーモンスレッドで `serve_forever` を回す |
| `stop() -> None` | `shutdown()` / `server_close()` してスレッドを join する |
| `bound_port` (property) | バインド済みポート（未起動/停止後は `None`） |

### bind の排他制御（Windows の `SO_REUSEADDR` 仕様差・#201）

`http.server.HTTPServer` は基底クラスで `allow_reuse_address = 1`（`SO_REUSEADDR`）を
設定するが、**Windows の `SO_REUSEADDR` は POSIX と意味が異なり、他ソケットが
LISTEN 中のポートへの bind も成功してしまう**。そのままではポートフォールバックが
発動せず、他アプリ使用中のポートに二重 bind する（接続の行き先が不定になる）。

- 対策として `ThreadingHTTPServer` のサブクラス（`_ExclusiveBindHTTPServer`）を用い、
  `allow_reuse_address` を **Windows（`sys.platform == "win32"`）では `False`、
  それ以外では `True`** とする。`start()` はこのサブクラスでバインドする。
  サブクラスの**クラス属性**で与えるのは、`TCPServer.__init__` が既定
  `bind_and_activate=True` でコンストラクタ内に `server_bind()` を呼ぶため
  （インスタンス生成後の属性書き換えでは bind に間に合わない）。
- POSIX で `SO_REUSEADDR` を維持するのは、`stop()`（`server_close()`）後の
  TIME_WAIT 中ポートへの再バインド失敗（無効化→再有効化の即時再起動）を避けるため。
- Windows では排他 bind の副作用として、アプリ再起動直後に旧接続の TIME_WAIT と
  衝突し先頭ポートの bind に失敗することがあり得る。その場合は**フォールバック
  ポートへ退避する（想定内の挙動）**。拡張側はフォールバック順にポートを試すため
  利用者影響はない。TIME_WAIT は 2MSL（数分）で解消されるため、Windows で短時間に
  連続再起動するとポートが一時的に 8719 等へ移り、解消後の再起動で 8718 へ戻る
  「さまよい」が起こり得るが、これも許容仕様とする。
- プラットフォーム分岐は `sys.platform` を引数に取る純関数（`resolve_allow_reuse_address`）
  に切り出し、Linux CI でも win32 分岐を単体テストできる形にする。

## セキュリティ

- バインドは `127.0.0.1` のみ（外部公開しない）。
- トークンは主防御、Origin 制限は多層防御。`BaseHTTPRequestHandler.log_message` を無効化し、クッキー・トークンを標準出力へ漏らさない。
