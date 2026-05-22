# 設定ダイアログにプロキシ設定タブを追加

[← タスク一覧](index.md)

## 背景

社内ネットワークや地域制限の回避などで yt-dlp の `--proxy` を恒常的に利用したいユーザーが、毎回 CLI から指定するのではなく GUI から指定できるようにする。設定値は `settings.json` に永続化し、再起動なしで反映する。

## 仕様

### Settings の拡張（`yt_gui/settings.py`）

`Settings` dataclass に以下のフィールドを追加。

| フィールド | 型 | デフォルト |
|---|---|---|
| `proxy_enabled` | `bool` | `False` |
| `proxy_scheme` | `str` | `"http"` |
| `proxy_host` | `str` | `""` |
| `proxy_port` | `str` | `""` |
| `proxy_username` | `str` | `""` |
| `proxy_password` | `str` | `""` |

加えて `PROXY_SCHEMES = ("http", "https", "socks4", "socks5", "socks5h")` 定数と、`build_proxy_url(settings) -> str` 関数を追加。`build_proxy_url` は `proxy_enabled=False` または `proxy_host` が空のときは `""` を返す。ユーザー名・パスワードは `urllib.parse.quote(..., safe="")` でエンコードする。

### 設定ダイアログのプロキシタブ（`yt_gui/settings_dialog.py`）

末尾（ファイル名タブの後ろ）に「プロキシ」タブを追加する。レイアウトは `QGridLayout`、構成は以下:

| 行 | ウィジェット | 備考 |
|---|---|---|
| 0 | `QCheckBox`（プロキシを有効にする） | OFF のとき下記入力欄を `setEnabled(False)` でグレーアウト |
| 1 | `QComboBox`（プロトコル） | `PROXY_SCHEMES` から選択 |
| 2 | `QLineEdit`（ホスト） | プレースホルダ `example.com` |
| 3 | `QLineEdit`（ポート） | `QIntValidator(1, 65535)` 装着、プレースホルダ `8080` |
| 4 | `QLineEdit`（ユーザー名） | 任意 |
| 5 | `QLineEdit`（パスワード） | `EchoMode.Password` |
| 6 | ヘルプ文 | グレー文字、平文保存の注意喚起 |

#### バリデーション

`_save()` で以下を確認し、エラー時は警告ダイアログを出してプロキシタブにジャンプ:

- 有効化 ON でホストが空欄 → `warn_proxy_no_host`
- ポートが 1〜65535 の範囲外 → `warn_proxy_bad_port`

### Downloader への注入（`yt_gui/downloader.py`）

`Downloader.__init__` に `proxy_url: str = ""` 引数を追加し、`self.proxy_url` として保持。`_base_ydl_opts()` 内で `if self.proxy_url: opts["proxy"] = self.proxy_url` を付与する。これにより全 `YoutubeDL` 呼び出し（`fetch_title_or_entries` / `fetch_formats` / `download_video`）で有効化される。

### App での配線（`yt_gui/app.py`）

- `Downloader` 初期化時に `proxy_url=build_proxy_url(self._settings)` を渡す
- `_open_settings()` の末尾で `self.downloader.proxy_url = build_proxy_url(self._settings)` を更新（次のダウンロードから反映）

### 翻訳キー

`locales/ja.py` と `locales/en.py` に以下を追加:

- `tab_proxy`
- `label_proxy_enabled` / `label_proxy_scheme` / `label_proxy_host` / `label_proxy_port` / `label_proxy_username` / `label_proxy_password`
- `proxy_help`
- `warn_proxy_no_host` / `warn_proxy_bad_port`

## 範囲外

- 接続テスト機能（将来別タスク）
- パスワードの暗号化保存（OS キーストア連携など）
- バイパスリスト（`no_proxy` 相当）
- アイテム単位の個別プロキシ指定

## テスト

`tests/test_settings.py` に追加:

- `proxy_*` フィールドのデフォルト値
- ラウンドトリップ（save → load）
- 旧 settings.json（`proxy_*` 無し）からのマイグレーション
- `build_proxy_url` の各分岐: 無効化・ホスト空・基本 HTTP・ポート省略・認証あり・ユーザーのみ・特殊文字エンコード

## 想定リスク

- **パスワードの平文保存**: 既存の Cookies パス等と同等の運用。ヘルプテキストで注意喚起。
- **SOCKS プロキシ依存**: yt-dlp は `urllib3`/`requests` 経由で対応するが、ビルド構成に依存。検証フェーズで確認。
- **既存実行中ジョブには反映されない**: 次のジョブから新しいプロキシを使う（Cookies と同じ挙動）。
