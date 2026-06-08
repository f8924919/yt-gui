# 並列ダウンロード（複数アイテム同時実行）＋キュー行単位の進捗表示

対応 Issue: #108

## 背景

キューは単一ワーカースレッドで逐次実行（`queue_controller.py` `_worker`）。進捗はステータスバーの単一プログレスバーのみ（`app.py` `progress_bar` / `_update_status`）。複数同時 DL と行単位の進捗表示を追加する。

## 確定した設計判断（ユーザー確認済み）

1. **ワーカー方式: Downloader を N 個プール化**。`Downloader` は `status_callback` / `_cancel_requested` をインスタンス属性で持つため、単一インスタンスを並列で共有するとコールバック衝突・中断が混線する。ワーカーごとに独立した `Downloader` を割り当て、`downloader.py` の中断ロジック（`_progress_hook` で `DownloadCancelled`）は無改修のまま隔離を成立させる。
2. **行単位の進捗: ステータス列に % テキスト**。`downloading` 行のステータス列に「ダウンロード中 45.2%」を表示。列レイアウトは 4 列のまま（列追加・デリゲートはしない）。
3. **ステータスバー: 全体進捗に役割変更**。単一プログレスバーは「完了数/総数」を示す全体進捗に変更（例: 3/10 完了 = 30%）。

## 実装方針

### settings.py
- `Settings.max_concurrent_downloads: int = 1`（既定 1 = 現行の逐次挙動）を追加。
- 範囲定数 `MAX_CONCURRENT_DOWNLOADS_MIN = 1` / `MAX_CONCURRENT_DOWNLOADS_MAX = 5`。

### settings_dialog.py
- 「ダウンロード」タブに「同時ダウンロード数」`QSpinBox`（1〜5）を追加し保存・復元。

### queue_controller.py
- `_QueueItem` に `progress: float = 0.0`（0–100、行表示用）を追加。
- コンストラクタに `make_downloader: Callable[[], Downloader] | None` / `get_concurrency: Callable[[], int] | None` を追加。
  - 既定: `make_downloader = lambda: downloader`（後方互換・既存テスト維持）、`get_concurrency = lambda: 1`。
  - **ワーカーは常に `make_downloader()` で得た downloader を使う**（共有 `self._downloader` のコールバックを汚さない）。App は各ワーカーに distinct インスタンスを返すファクトリを渡す。
- `_worker_running: bool` → `_active_workers: int`（走行中ワーカー数）。`is_running = _active_workers > 0`。
- `_active_downloaders: list[Downloader]`（`_lock` 保護）で走行中ワーカーの downloader を追跡し、`pause()` で全件 `request_cancel()`（dedupe）。
- `start(cookies_resolver)`: `n = clamp(get_concurrency(), 1, MAX)` 本のワーカースレッドを起動。
- `_worker(cookies_resolver, downloader)`:
  - ループ先頭で `_paused` 判定 → break。`waiting` を取り出し `downloading`＋`progress=0` に（`_lock` 内）。
  - `downloader.status_callback = make_cb(item)`。`make_cb` は percent を `item.progress` に格納し `item_refresh.emit(item)`（行更新）＋全体進捗を `status_update` で emit。
  - 例外処理（`DownloadCancelled`→waiting / `DownloadSkipped`→skipped / その他→error）は現行踏襲。
  - `finally` で `_active_downloaders` から除去・`_active_workers -= 1`。最後のワーカーのみ「全体進捗 / `worker_done` / `log_queue_done`（pause 時は出さない）」を emit。
- 全体進捗 `_emit_overall_progress()`: `total = {waiting,downloading,done,error,skipped}` 件数、`finished = {done,error,skipped}` 件数、`pct = finished/total*100`。`status_update.emit(t("status_overall_progress").format(done, total), pct)`。

### app.py
- `_build_download_worker() -> Downloader`: 現在の設定から status_callback=None・log_callback=`_on_downloader_log` の Downloader を生成（`__init__` の生成ブロックを共通化）。
- `QueueController(... , make_downloader=self._build_download_worker, get_concurrency=lambda: self._settings.max_concurrent_downloads)`。
- `self.downloader`（primary）はタイトル取得・アーカイブ事前フィルタ・依存チェック・オリジナル形式パネル参照用に従来どおり残す（`_open_settings` のミューテートも維持）。
- `refresh_tree_item`: `downloading` のとき列 3 を `t("queue_status_downloading_pct").format(percent=item.progress)` にする。
- ステータスバーは `status_update`（全体進捗）でこれまでどおり更新。

### i18n（locales）
- `status_overall_progress`: ja「完了 {done}/{total}」/ en「Completed {done}/{total}」
- `queue_status_downloading_pct`: ja「ダウンロード中 {percent:.1f}%」/ en「Downloading {percent:.1f}%」
- 設定ダイアログ: `settings_max_concurrent_label` 等。

## 既知の挙動・トレードオフ

- 走行中に待機が尽きたワーカーは終了する。走行中にアイテムを追加した場合、残存ワーカー数で処理される（最大 N は「同時に最大 N」を意味する best-effort）。
- 既定 N=1 では現行と同じ逐次挙動・行表示・全体進捗（1 件のみ）になる（後方互換）。
- 速度/ETA はステータスバーが全体進捗に変わるため常時表示から外す（受け入れ条件外）。必要なら将来ツールチップ等で再導入。

## テスト方針（テスト先行）

- `test_settings.py`: `max_concurrent_downloads` の既定・保存/復元・未知キー無視。
- `test_queue_controller.py`:
  - N>1 で複数 `waiting` が同時に `downloading` になる（distinct mock downloader ファクトリ）。
  - 取り出し排他: 各 waiting がちょうど 1 回ずつ処理される（重複処理が無い）。
  - 進捗ルーティング: status_callback で `item.progress` が更新され該当行だけ変わる。
  - `pause()` が全 active downloader の `request_cancel()` を呼ぶ。
  - 全体進捗 `status_update` が finished/total を反映する。
  - 既定 N=1 の既存テストが green のまま（後方互換）。
- 既存の `test_worker_*`（cancel/error/skipped）が N=1 で従来どおり通ること。

## 受け入れ条件（Issue より）

- [ ] 設定に「同時ダウンロード数」があり保存・復元（既定 1）
- [ ] N>1 で最大 N 件が同時に `downloading`
- [ ] 各行に進捗 % が表示され混線しない
- [ ] 一時停止で全 in-flight が中断され `waiting` に戻り部分ファイル削除、再開で先頭から
- [ ] 既定 1 で現行と同じ逐次挙動・表示（後方互換）
- [ ] `_items` 並行アクセスで競合・クラッシュ無し
- [ ] 既存テスト green ＋ 並列・進捗ルーティングの単体テスト追加
- [ ] spec / arch 更新
