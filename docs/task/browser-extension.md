# ブラウザ拡張連携（URL + Cookies をワンクリックでキュー追加）

[← タスク一覧](index.md)

- Issue: [#140](https://github.com/f8924919/yt-gui/issues/140)
- ブランチ: `feature/140-browser-extension`
- 関連 spec: [browser-extension.md](../spec/features/browser-extension.md) / [download-behavior.md#cookies](../spec/features/download-behavior.md#cookies) / [queue.md](../spec/features/queue.md)

## 背景

認証付き動画の DL に「URL コピー往復」「cookies.txt 手動エクスポート」の手間がかかる。ブラウザ拡張から URL と `chrome.cookies` 由来のクッキーを yt-gui のローカルサーバーへ送り、ワンクリックでキュー追加できるようにする。

## 設計メモ（調査結果）

### 既存のクッキー連携（流用できる）
- `Downloader` は `cookies_path`（cookies.txt）と `cookies_browser`（`cookiesfrombrowser`）の 2 系統を既に持つ（`downloader.py:199-203`）。
- クッキーは**追加時のメタデータ取得**（`fetch_title_or_entries` / `fetch_formats`）と**実ダウンロード**（`download_video`）の両方で必要。
- → 拡張から受け取ったクッキーを一時 cookies.txt に書いて既存 `cookies_path` 経路に乗せれば、**Downloader は無改修**で済む。

### アイテム単位 Cookies の持たせ場所
- **`_QueueItem.cookies_path`（path のみ）に持たせる**（`JobSpec` ではない）。
  - 根拠: `_QueueItem` は url / playlist 情報など「アイテム固有の素性」を持つ場所で、クッキー（ソース認証）はここが自然。`JobSpec` は frozen な「出力/符号化の実行設定」で意味的に異質。
  - worker のクッキー解決（`queue_controller.py:363`）を「アイテム固有 > グローバル `cookies_resolver()`」に変更するだけ。**Downloader 無改修**。
  - 編集モード（`apply_edit` は job/label のみ差し替え）でクッキーが保持される利点。
  - `cookies_browser` はアイテム単位には持たせない（拡張連携と排他）。

### 一時 cookies.txt のライフサイクル
- 専用一時ディレクトリ・権限 0600。done/error・アイテム削除・アプリ終了時に掃除。失敗は非致命（区間 DL の一時ファイル処理に倣う）。

## 確定事項
- サーバー既定: 無効（オプトイン）
- 既定ポート: `8718`（フォールバック `8719` → `8720`）
- 拡張配布: 当面 unpacked（Manifest V3・Chromium 系）
- アイテム単位は cookies path のみ

## 進め方（フェーズ）

1. **docs 先行（完了）**: spec ファイル化・index/関連 spec 追記。
2. **アイテム単位 Cookies（完了）**: `_QueueItem.cookies_path` 追加・`enqueue_single(cookies_path=...)`・worker のフォールバック解決（アイテム固有 > グローバル、欠落時は警告して cookies なし続行）・テスト 5 件・arch 更新。
3. ローカル受信サーバー:
   - **3a（完了）**: settings フィールド（`extension_enabled` / `extension_port` / `extension_token`）・`generate_extension_token()`・定数・`extension_server.py`（`handle_request` 純関数 + `ExtensionServer` ライフサイクル、`127.0.0.1` 限定・トークン/Origin 認証・ポートフォールバック）・テスト 15 件・arch/spec docs。
   - **3b（完了）**: app.py の配線。`_AppSignals.extension_enqueue` でサーバースレッド→メインスレッド委譲。`_sync_extension_server` / `_start`/`_stop` / `_on_extension_enqueue` / `_extension_default_format`（現在のコンボ選択、original→best_mp4）/ `_write_extension_cookies`（TemporaryDirectory・0600）/ `closeEvent` 掃除。`_start_add_thread`・`_on_fetch_for_add_done` に `item_cookies_path` を通し、`enqueue_single`/`enqueue_playlist` の cookies_path へ。i18n キー追加。app テスト 7 件・queue テスト 1 件追加。
4. **設定 UI（完了）**: 設定ダイアログに「ブラウザ連携」タブを追加。有効化チェック・受信ポート（QSpinBox）・トークン（read-only + コピー/再生成）。有効化時/保存時にトークン自動生成。i18n キー・spec/arch docs・テスト 4 件。
5. **拡張機能（完了）**: `extension/` に Manifest V3 一式（`manifest.json` / `background.js` / `options.html` / `options.js` / `README.md`）。ツールバー/右クリックで URL 取得・`chrome.cookies` → Netscape 整形・トークン付き POST・ポート追従（8718→8720）・バッジ結果表示。JS のため pytest 対象外（手動検証）。
6. arch ドキュメント更新（完了: app/queue_controller/extension_server/settings/settings_dialog の arch、各 spec）。

## 手動 E2E 検証

- 2026-06-13: 実ブラウザ（Chrome ログイン済み）＋アプリでニコニコ動画の DL に成功。
- この過程で pre-existing バグを発見・修正: `_cookies_opts` が cookie ファイルを誤キー `cookies` で渡しており yt-dlp に無視されていた → `cookiefile` に修正（cookies.txt 指定が初めて実際に有効化）。

## 残作業

- PR #141 のレビュー/マージ。マージ後は `/finish-task`（archive 移動）。

## 検証メモ

（実装着手後に追記）
