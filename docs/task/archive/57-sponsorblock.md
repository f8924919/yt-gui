# SponsorBlock 対応（#57）

対応 Issue: [#57](https://github.com/f8924919/yt-gui/issues/57)

## 概要

YouTube 等のスポンサー区間・自己宣伝・イントロ等を、SponsorBlock データベースを参照して **チャプター印付け（mark）** / **動画から除去（remove）** する機能。設定ダイアログに専用タブを追加し、`Downloader` で yt-dlp の `SponsorBlock` / `ModifyChapters` ポストプロセッサとして反映する。

実装パターンは並列フラグメント DL（#53）と同型（設定永続化 → `Downloader` プロパティ → `_build_ydl_opts` で PP 付与、メタデータ取得には付与しない、次の DL から反映）。

## UI

専用タブ「SponsorBlock」＋ 3 択ラジオ（使用しない / mark / remove）＋ カテゴリチェックボックス 7 種。「使用しない」選択時はカテゴリ群をグレーアウト。

## 設計メモ

- `Settings.sponsorblock_mode: str`（`""` / `"mark"` / `"remove"`）/ `sponsorblock_categories: list[str]`（`default_factory` で `["sponsor", "selfpromo"]`）。
- カテゴリ定数 `SPONSORBLOCK_CATEGORIES` / `SPONSORBLOCK_DEFAULT_CATEGORIES` / `SPONSORBLOCK_MODES` を `settings.py` に定義。未知カテゴリは downloader 側でフィルタ（安全フォールバック）。
- `Downloader._append_sponsorblock_postprocessors`:
  - `SponsorBlock` PP（`when="after_filter"`）はリスト末尾に追加（位置は実行順に無関係）。
  - `ModifyChapters` PP は `FFmpegMetadata` / `EmbedThumbnail` の直前に挿入（`FFmpegExtractAudio` は先頭にあるため自動的に前段）。
  - mark 時は `_ensure_chapters_embedded` で `FFmpegMetadata.add_chapters=True` を保証（yt-dlp CLI の自動 ON と同じ）。
- 正準的な PP 構成は同梱 yt-dlp の `__init__.py`（`SponsorBlock` after_filter / `ModifyChapters` は FFmpegMetadata より前）で裏取り済み。

## 進捗

- [x] `settings.py` 定数・フィールド
- [x] `downloader.py` プロパティ・`_append_sponsorblock_postprocessors`
- [x] `settings_dialog.py` SponsorBlock タブ
- [x] `app.py` 反映（コンストラクタ / `_open_settings`）
- [x] i18n（ja / en）
- [x] テスト（`test_downloader.py` 7 ケース / `test_settings.py` 3 ケース）
- [x] docs（spec / arch / research）更新
- [x] lint / format / mypy / pytest（117 passed）
- [x] PR 作成・レビュー・マージ（PR #58、2026-06-01 マージ）
