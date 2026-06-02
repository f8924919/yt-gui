# 進行中ダウンロードの中断

- **Issue**: [#67](https://github.com/f8924919/yt-gui/issues/67)
- **ブランチ**: `feature/67-cancel-downloading`
- **ステータス**: 進行中

## ゴール

進行中のダウンロードを即座に中断し、該当アイテムを `waiting` に戻して再開可能にする。中断時に部分ファイル（`.part` 等）は削除し、再ダウンロードは最初からやり直す。

## 決定事項（ユーザー確認済み）

- 操作種別: **中断して待機に戻す（再開可）**。`error` 化しない。
- 部分ファイル: **削除する**（再ダウンロードは先頭から）。
- UI: 既存の「一時停止」ボタンの意味を「進行中も即中断」に統合する（新規ボタンは追加しない）。

## 中断機構（要点）

唯一の協調的中断ポイントは yt-dlp の `progress_hooks`（`downloader.py:442`, `_progress_hook`）。フック内で `yt_dlp.utils.DownloadCancelled`（`YoutubeDLError` 派生、本リポジトリの yt-dlp==2026.3.17 で利用可）を raise すると現在の DL を中断できる。

- 即時性はベストエフォート: フラグメント DL 中は概ね即時、メタデータ抽出・ポストプロセス中は当該フェーズ完了後になりうる。
- `_worker` の `except Exception`（→ `error`）が `DownloadCancelled` も拾うため、**generic ハンドラより前で個別捕捉**する必要がある。

## 実装ステップ（TDD・docs 先行）

1. spec/arch 更新（`queue.md`「一時停止・再開」/ `queue_controller.md` / `downloader.md`）。
2. テスト追加（先に red を作る）:
   - `Downloader`: 中断要求が立つと `_progress_hook` が `DownloadCancelled` を投げる。
   - `QueueController`: 中断時に当該アイテムが `waiting` に戻り、部分ファイル削除が呼ばれる。
3. 実装:
   - `downloader.py`: 中断要求フラグ（`threading.Event`）+ `_progress_hook` 先頭チェック + ジョブ開始時クリア。
   - `queue_controller.py`: `pause()` で中断要求送出。`_worker` を `except DownloadCancelled`（→ `waiting`・部分ファイル削除）/`except Exception`（→ `error`）に分割。
   - 部分ファイル削除: `_resolve_unique_path` 由来の実効ステムを基に `{stem}*` の一時ファイルを掃除。失敗は非致命（ログのみ）。
   - i18n: `log_download_cancelled` 等を全 locale に追加。
4. lint / format / mypy / pytest を通す。
5. docs の最終整合を確認して PR。

## リスク / 留意

- 部分ファイル削除はステム予測に依存するため最もテストを厚くする。
- 「一時停止」意味変更により「進行中は完了させてから停止」挙動は失われる（Issue に明記済み）。別ボタン分離案は不採用。
