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
3. ローカル受信サーバー: `127.0.0.1` 限定・トークン/Origin 認証・`POST /enqueue`・一時ファイル管理 + テスト。
4. 設定 UI: ブラウザ連携の有効化・トークン・ポート。
5. 拡張機能（unpacked）: URL/cookies 取得・送信・オプション画面。
6. arch ドキュメント更新。

## 検証メモ

（実装着手後に追記）
