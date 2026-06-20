# yt_dlp 更新（バージョン管理・side-load）

> 関連仕様: [yt-dlp 本体のバージョン管理・更新](../spec/features/yt-dlp-update.md)

yt-dlp 本体のバージョン表示・更新チェック（Phase A）と side-load による実体更新
（Phase B）の実装意図・接続点をまとめる。

本ドキュメントは Issue [#119](https://github.com/f8924919/yt-gui/issues/119) の
方式決定（A→B 段階導入）に基づく**設計**であり、実装は Phase A / Phase B の
別 Issue で行う。各モジュールは実装時に新規作成する想定で、ここでは責務境界と
既存コードへの接続点を確定する。

## なぜ side-load か（C を採らない理由）

yt-dlp は `downloader.py` で **Python API として密結合**している
（`YoutubeDL` 直呼び・独自 `PostProcessor`・進捗フック・`DownloadCancelled` /
`DownloadError` 例外捕捉）。yt-dlp を単体バイナリ＋subprocess（`-U` 利用）へ
再設計する案（C）は、この進捗・キャンセル・PostProcessor を全面再実装すること
になり、更新機能のためだけに払うコストに見合わない。Python API を維持したまま
`sys.path` 差し込みで実体を差し替える side-load（B）を本格策とする。

## Phase A: バージョン照会と通知

| 要素 | 接続点・責務 |
|---|---|
| yt-dlp 現バージョン | `yt_dlp.version.__version__` を参照（新規ヘルパで取得） |
| アプリ現バージョン | 既存 `yt_gui.get_version()`（[entry.md](entry.md)） |
| 最新版照会 | PyPI JSON API（`pypi.org/pypi/yt-dlp/json` の `info.version`）を stdlib `urllib` で取得 |
| 比較・通知 | 同梱版と最新版を比較し UI へ結果を返す |
| UI 接続 | `app.py` にヘルプメニュー＋バージョン情報/更新確認を追加（既存メニューは「ファイル」のみ。`_window_title` がバージョン表示の前例） |

- ネットワーク照会は**バックグラウンドスレッド**で行い、結果は Qt の
  `Signal`/`Slot` でメインスレッドへ戻す（[app.md](app.md) のスレッド間通信
  パターン。ワーカーは [threading_utils.md](threading_utils.md) を流用しうる）。
- 照会は明示操作起点。失敗時は穏当に通知しアプリ動作は継続。
- 照会・比較ロジックは UI 非依存の純関数として切り出し、テスト容易性を確保する
  （HTTP 部分は差し替え可能にしてオフラインでも単体テストできる形にする）。

## Phase B: side-load ブートストラップ

```
プロセス起動
  └─ ブートストラップ（import yt_dlp より前）
       ├─ ユーザー領域の side-load 版を探索
       ├─ あれば sys.path 先頭へ差し込み
       └─ import 検証に失敗したら差し込みを外し同梱版へフォールバック
  └─ from .app import App   ← 以降は通常どおり yt_dlp を import
```

### 接続点

| 要素 | 接続点・責務 |
|---|---|
| 差し込み位置 | `yt_gui/__main__.py` の `from .app import App` より**前**。`app` → `downloader` の import 連鎖で `yt_dlp` が解決される前に `sys.path` を確定する必要がある |
| 取得 | PyPI から最新 yt-dlp wheel を取得（stdlib `urllib`）し、PyPI 公開 sha256（`urls[].digests.sha256`）で照合 |
| 保存先 | OS 別の書き込み可能領域（Windows `%LOCALAPPDATA%\yt-gui\`、macOS/Linux `~/.local/share/yt-gui/`） |
| 適用タイミング | freeze 環境では次回起動から有効（実質再起動）。開発（非 freeze）時は分岐 |
| フォールバック | side-load 版の import 失敗時は同梱版へ復帰し、アプリは必ず起動 |

### 詰めるべき課題（Phase B 実装 Issue の受け入れ条件候補）

- **依存整合**: 新 yt-dlp が freeze 済み transitive 依存（`requests` /
  `urllib3` / `websockets` / `pycryptodomex` 等）より新しい版を要求した場合の
  扱い。更新可能範囲の制限＋失敗時フォールバック。
- **`yt-dlp-ejs` 互換**: 本体だけ更新した組み合わせの検証。
- **取得物の検証**: PyPI 公開 sha256 による改ざん検知。
- **import 順序**: `import yt_dlp` 前の `sys.path` 差し込みブートストラップ。
- **適用タイミング**: freeze での再起動必須・開発時分岐。
- **保存先**: 書き込み可能領域の OS 別解決。

## 既存コードへの影響範囲

| ファイル | 影響 |
|---|---|
| `yt_gui/__init__.py` | yt-dlp バージョン取得ヘルパを追加（`get_version()` 近傍） |
| `yt_gui/app.py` | ヘルプメニュー・バージョン情報/更新確認 UI を追加 |
| `yt_gui/__main__.py` | Phase B の起動時 `sys.path` ブートストラップ |
| `yt_gui/downloader.py` | import 経路は不変（side-load 版が `sys.path` 経由で解決される） |
| 新規モジュール | バージョン照会・side-load を担う新モジュール（実装 Issue で確定） |
