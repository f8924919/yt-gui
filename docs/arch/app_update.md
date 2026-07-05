# app_update — アプリ本体の更新チェック

> 関連仕様: [アプリ本体（yt-gui）の更新チェック・通知](../spec/features/app-update.md)

アプリ本体（yt-gui）の更新チェック（Phase A）の実装意図・接続点をまとめる。
実装 Issue は [#198](https://github.com/f8924919/yt-gui/issues/198)。

## 設計方針

[yt_dlp_update.md](yt_dlp_update.md)（Phase A・#178）の**同型パターンを横展開**
する。照会・解析・比較ロジックは新規モジュール **`yt_gui/app_update.py`** に
UI 非依存の純関数として切り出し、UI（起動時通知・バージョン情報ダイアログ）は
`app.py` 側に置いてバックグラウンドスレッドから純関数を呼ぶ。

yt-dlp 版との差分は次の 2 点のみ。

1. **照会先が GitHub Releases API**（`api.github.com/repos/f8924919/yt-gui/releases/latest`
   の `tag_name`。PyPI JSON API ではない）。`v` prefix の除去が必要。
   GitHub API は **User-Agent ヘッダー必須**。
2. **起動時自動チェックあり**（オプトアウト設定つき。yt-dlp 版は明示操作のみ）。

比較ロジック（`compare_versions` / `UpdateStatus`）は `yt_dlp_update.py` の
実装をそのまま **import して再利用**する（`packaging.version` 比較は照会先に
依存しないため。重複実装しない）。`app_update` → `yt_dlp_update` という
兄弟 feature 間の依存は**暫定**であり、3 つ目の利用者が現れた時点で中立な
共有モジュール（例 `version_check.py`）へ切り出す。

## 接続点

| 要素 | 接続点・責務 |
|---|---|
| アプリ現バージョン | 既存 `yt_gui.get_version()`（[entry.md](entry.md)） |
| 最新版照会 | `app_update.check_for_update()` が GitHub Releases API を stdlib `urllib`（タイムアウト 10 秒・User-Agent 付与）で取得。HTTP は `fetch` 引数で差し替え可能 |
| レスポンス解析 | `app_update.parse_latest_version()`（純関数。`tag_name` を取り出し `v` prefix を除去。不正な形式は「照会失敗」に正規化） |
| 比較 | `yt_dlp_update.compare_versions()` / `UpdateStatus` を再利用 |
| 起動時チェック | `app.py` の既存起動時フック（`__init__` 末尾の `QTimer.singleShot(0, ...)`、`_check_dependencies` と同機構）で照会スレッドを起動する。コールバックはイベントループ起動後＝メインウィンドウ表示後に配送されるため「表示後の通知」が機構的に保証される。`UPDATE_AVAILABLE` のときのみ `QMessageBox` を表示（手動用ハンドラは流用せず、失敗・最新をサイレントに落とす専用ハンドラを設ける）。`get_version() == "unknown"` またはオプトアウト時はスレッド自体を起動しない |
| 手動チェック | `app.py` の既存バージョン情報ダイアログ（`_show_about_dialog`）に「yt-gui の更新を確認」ボタンを追加し、既存ボタンは「yt-dlp の更新を確認」へ改称して対称化する。結果は yt-dlp 用と対称の 3 分岐で `QMessageBox` 表示、更新ありは `QDesktopServices.openUrl` で yt-gui GitHub releases を開く |
| オプトアウト設定 | `settings.py` の `Settings` に `app_update_check_enabled: bool = True` を追加。設定ダイアログ一般タブにチェックボックス（[settings_dialog.md](settings_dialog.md)） |

- ネットワーク照会は**バックグラウンドスレッド**で行い、結果は Qt の
  `Signal`/`Slot` でメインスレッドへ戻す（[app.md](app.md) のスレッド間通信
  パターン。`run_in_thread` を流用）。
- 照会・解析は UI 非依存の純関数とし、HTTP 部分は `fetch` 引数で差し替えて
  オフラインで単体テストする（[testing/policy.md](../testing/policy.md)）。

## 既存コードへの影響範囲

| ファイル | 影響 |
|---|---|
| `yt_gui/app_update.py` | **新規**。最新版照会・解析の純関数（`check_for_update` / `parse_latest_version`） |
| `yt_gui/yt_dlp_update.py` | 変更なし（`compare_versions` / `UpdateStatus` を提供） |
| `yt_gui/app.py` | 起動時チェックのフック、バージョン情報ダイアログへのボタン追加、通知 UI |
| `yt_gui/settings.py` | `app_update_check_enabled` フィールド追加 |
| `yt_gui/settings_dialog.py` | 一般タブにチェックボックス追加 |
| `yt_gui/locales/` | 通知・ボタン・設定項目の翻訳キー追加 |
