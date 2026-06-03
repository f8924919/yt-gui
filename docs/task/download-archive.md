# ダウンロードアーカイブ機能

対応 Issue: #75
ブランチ: `feature/75-download-archive`

## 目的

yt-dlp の `--download-archive` 相当を導入し、プレイリスト再追加時の差分取得・同一動画の再 DL 防止を実現する。

## 確定した設計方針

- **保存スコープ**: グローバル単一アーカイブ。既定パスは設定ディレクトリの `download_archive.txt`、設定で変更可能。
- **キュー適用方式**: プレフィルタ ＋ DL 時スキップの併用。
  - プレイリスト展開時に `YoutubeDL.in_download_archive(info)` で照合し、一致エントリはキューに追加しない。
  - DL 時は `download_archive` opt を常に渡す（記録は opt 経由でのみ行われるため必須・単発 URL の取りこぼし防止も兼ねる）。
- **記録単位**: 動画 ID 単位・フォーマット非依存・DL 完全成功時のみ（yt-dlp 仕様どおり）。
- **既存パターン踏襲**: download 系オプション（proxy / rate_limit / sponsorblock）と同様に「Downloader 属性 ＋ `_build_ydl_opts` で付与 ＋ `_open_settings` で即時反映」。
- **新ステータス `skipped`**: `done`/`error` と区別。検出は `download_video` 内で `in_download_archive` 照合 → 専用例外 → worker が `DownloadCancelled` と同様に `Exception` より前で捕捉。

## 実装方針（作業順 = docs 先・テストファースト）

1. spec / arch を先に更新（設計をドキュメントで固定）。
2. テストを先に書く（`_build_ydl_opts` 表ベース・プレフィルタ純関数・skip 遷移）。
3. 実装:
   - `settings.py`: `download_archive_enabled` / `download_archive_path` 追加。空パス→設定ディレクトリ既定の解決ヘルパ。
   - `downloader.py`: 属性追加・`_build_ydl_opts` で opt 付与・skip 検出例外。
   - `queue_controller.py`: プレフィルタ・`skipped` ステータスと色/ラベル。
   - `settings_dialog.py`: ダウンロードタブに UI（チェック・パス・件数・クリア）。
   - `app.py`: `_open_settings` 反映・skip 表示配線。
   - `locales/`: 文字列追加。
4. lint / 型 / テスト green。
5. PR（`Closes #75`）。

## 残課題・将来拡張

- フォーマット非依存記録の落とし穴（画質変更で再取得したい場合に効かない）→ アイテム単位「アーカイブを無視して再取得」は **#76 として分離**（本実装スコープ外）。
- グローバルアーカイブの「ファイル削除しても記録は残る」セマンティクスを spec に明記（本実装で対応）。

## 検証メモ

- ruff check / format（`yt_gui/`）・mypy・pytest 全て green（pytest 166 件、新規 +13 件）。
- 実 yt-dlp の `in_download_archive` で記録形式 `youtube {id}` の照合が想定どおり動作することを確認。
- `SettingsDialog` をオフスクリーンで構築し、有効/無効トグルでパス入力・参照・クリアの活性切替と件数表示が動くことを確認。

## 実装サマリ（完了）

- `settings.py`: `download_archive_enabled` / `download_archive_path` 追加。`default_download_archive_path` / `resolve_download_archive_path` / `count_download_archive_entries` 追加。
- `downloader.py`: `download_archive_path` 属性・`_build_ydl_opts` で opt 付与・`_resolve_unique_path` 内で `in_download_archive` 判定 → `DownloadSkipped` 送出・`filter_unarchived_entries` プレフィルタ・flat エントリに `id`/`ie_key` 追加。
- `queue_controller.py`: `skipped` ステータス（ラベル/色）・`DownloadSkipped` を `Exception` より前で捕捉。
- `app.py`: Downloader 生成・`_open_settings` で `resolve_download_archive_path` 反映・プレイリスト追加時にプレフィルタ。
- `settings_dialog.py`: ダウンロードタブに有効化チェック・パス・参照・件数・クリア。
- `locales/ja.py` / `en.py`: 文字列追加。
- docs: spec（download-behavior / settings / settings-dialog / queue）・arch（downloader / queue_controller / settings）・research（feature-gap ✅化）更新。
- 残課題はアイテム単位再取得 #76 へ分離。
