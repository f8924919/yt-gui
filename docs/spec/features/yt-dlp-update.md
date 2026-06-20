# yt-dlp 本体のバージョン管理・更新

yt-dlp はサイト側の仕様変更へ追従するためほぼ週次で更新される。yt-gui は
yt-dlp を**固定バージョンの PyPI パッケージ**として同梱しており、配布バイナリを
使い続けると抽出ロジックが古くなりダウンロードが失敗し得る。アプリ全体を再
インストールせずに yt-dlp を最新化する手段（または最低限その必要性を知らせる
手段）を提供する。

本仕様は **Issue [#119](https://github.com/f8924919/yt-gui/issues/119) の方式決定**に
基づく。採用方式は **A（更新チェック＋通知）短期 ＋ B（side-load による実体更新）
本格** の段階導入。実装は Phase A / Phase B を別 Issue として進める（[#119]
コメントに決定を記録）。設計の意図・接続点は [arch/yt_dlp_update.md](../../arch/yt_dlp_update.md)
を参照。

## 前提（現状の制約）

- yt-dlp は **pip/uv 依存の PyPI パッケージ**として同梱（`pyproject.toml` で
  バージョン固定、`uv.lock` に記録）。yt-dlp 単体バイナリは同梱していない。
- 呼び出しは **Python API 経由**（`yt_gui/downloader.py` の
  `from yt_dlp import YoutubeDL`）。subprocess で yt-dlp CLI を起動する箇所はない。
- PyInstaller では yt-dlp は読み取り専用の `sys._MEIPASS` 展開先に freeze される
  （[entry.md](../../arch/entry.md) の `get_resource_base()`）。
- 以上より **`yt-dlp -U`（CLI 自己更新）は使えず**、freeze 済みパッケージの
  その場書き換えも不可。
- アプリ独自の HTTP クライアント実装はゼロ（ネットワークはすべて yt-dlp 経由）。

## Phase A: バージョン表示＋更新チェック＋通知

実体更新はせず、現バージョン表示と「より新しい版があるか」の通知に徹する。
実体の最新化は既存の週次 Dependabot → 再リリース配信で対応する。

### 表示するバージョン

- **yt-dlp バージョン**: 実行中の `yt_dlp.version.__version__`（freeze 同梱版）。
- **アプリバージョン**: 既存の `yt_gui.get_version()`（[build.md](../../build.md)
  の単一ソース設計）。

### 照会先（データソース）

- 最新版は **PyPI JSON API**（`https://pypi.org/pypi/yt-dlp/json` の
  `info.version`）を正とする。yt-dlp の同梱が PyPI/uv パッケージであり
  バージョン体系が一致するため、Phase B の wheel 取得とも整合する。
- 照会は**ユーザー操作（メニューからの明示実行）を起点**とし、起動時の自動
  バックグラウンド通信は既定で行わない（プライバシー・オフライン動作の配慮）。
  将来オプトインの自動チェックを検討する余地は残す。

### 比較と通知

- 同梱版と最新版を比較し、以下を表示する。
  - 最新版と同じ: 「最新です」相当のメッセージ。
  - 古い: 「より新しい yt-dlp (X) があります」＋リリースページへの導線。
- バージョン比較は `packaging.version`（既存の直接依存）で行い、日付ベースの
  yt-dlp バージョン（例 `2026.06.09`）を正しく比較する。
- 照会失敗（オフライン・HTTP エラー・rate limit 等）はエラーダイアログ等で
  穏当に通知し、アプリ動作は継続する（クラッシュさせない）。
- 文言はすべて [i18n](../i18n.md) の翻訳キー経由で提供する。

### UI 配置（Phase A 実装 [#178](https://github.com/f8924919/yt-gui/issues/178) で確定）

- メニューバーに「ヘルプ」メニューを追加し（現状メニューは「ファイル」のみ）、
  その配下に **1 項目「バージョン情報 / 更新を確認」** を置く。バージョン併記と
  更新照会を 1 つのフローに統合する。
- 項目を選ぶと `QMessageBox`（情報アイコン）で yt-gui / yt-dlp 双方のバージョンを
  併記し、「更新を確認」ボタンで PyPI 照会を起動する。
- 照会結果は別の `QMessageBox` で通知する。
  - 最新: 情報メッセージ「yt-dlp は最新です」。
  - 古い: 「より新しい yt-dlp (X) があります」＋「リリースページを開く」ボタンで
    yt-dlp の **GitHub releases**（`https://github.com/yt-dlp/yt-dlp/releases`）を
    既定ブラウザで開く。
- macOS では「バージョン情報 / 更新を確認」アクションに `AboutRole` を付与し、
  プラットフォーム慣習に従いアプリメニューへ移動させる（設定の `PreferencesRole`
  と同方針）。

## Phase B: side-load による実体更新

最新 yt-dlp を**書き込み可能なユーザーディレクトリ**へ取得し、起動時に
`sys.path` 先頭へ差し込んで freeze 同梱版より優先 import させる。Python API は
そのまま使い続ける（`downloader.py` の import 経路は不変）。

### 取得と保存先

- PyPI から最新 yt-dlp の **wheel** を取得し、ユーザー領域へ配置する。
  - Windows: `%LOCALAPPDATA%\yt-gui\`、macOS/Linux: `~/.local/share/yt-gui/`
    などの書き込み可能領域（OS 別に解決）。
- 取得物は **PyPI 公開の sha256**（JSON API の `urls[].digests.sha256`）と
  照合して改ざんを検知する。HTTP は stdlib `urllib` を用いる。

### 適用（差し込み）

- `import yt_dlp` より**前**に、保存先を `sys.path` 先頭へ差し込む起動
  ブートストラップを設ける（[arch/yt_dlp_update.md](../../arch/yt_dlp_update.md)）。
- freeze 環境では実行中プロセスの差し替えはできないため、適用は**次回起動
  から有効**（実質再起動が必要）。ユーザーへその旨を通知する。

### 安全策（フォールバック）

- side-load 版の import に失敗した場合は、`sys.path` 差し込みを外して
  **freeze 同梱版へフォールバック**し、アプリは必ず起動する。
- 新 yt-dlp が freeze 済み transitive 依存（`requests` / `urllib3` /
  `websockets` / `pycryptodomex` 等）より新しい版を要求しうる。更新可能範囲を
  制限し、不整合・import 失敗時は同梱版へ戻す。
- `yt-dlp-ejs`（deno による JS チャレンジ解決）との組み合わせ整合を検証する。

これらの詰めるべき課題は Phase B 実装 Issue の受け入れ条件として明文化する。

## 受け入れ条件との対応（本 Issue = 方式決定）

- 方式（A→B 段階導入）を決定し [#119] にコメント記録する。
- 採用方式に対応する本 spec と [arch/yt_dlp_update.md](../../arch/yt_dlp_update.md)
  を新規作成する。
- 実装は Phase A / Phase B の受け入れ条件付き Issue へ落とし込む。
