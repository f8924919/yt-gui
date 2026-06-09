# 互換性優先（再エンコード）出力モード — Phase 1: 映像の H.264 MP4 再変換

- 対応 Issue: [#120](https://github.com/f8924919/yt-gui/issues/120)
- ブランチ: `feature/120-recode-video-h264`
- ステータス: 進行中

## 背景 / 目的

オリジナル形式の出力は remux（コンテナ詰め替え）までで、配信元が VP9 / AV1（webm / mkv）のとき MP4 にできずフォールバックする。古いデバイス・編集ソフト・汎用プレーヤーで確実に再生できる H.264 / AAC の MP4 を得る選択肢を追加する。

## 設計方針（確定事項）

- 出力形式ラジオに第 4 の選択肢「H.264 MP4 に再変換（互換性優先）」を追加（既存の結合 / remux / 音声のみと排他）。
- コーデックは **H.264 / AAC を明示強制**（ユーザー確認済み）。`postprocessor_args` の `videoconvertor` キーに `-c:v libx264 -c:a aac` を渡す。`preferedformat="mp4"` だけでは ffmpeg デフォルト依存になるため明示する。
- `FFmpegVideoConvertor` がスキップしないよう `merge_output_format` を `mkv` に固定し、必ず `mkv → mp4` 変換を走らせる。
- 出力は常に `.mp4`。`video_container` は `build_job_spec` で `"mp4"` に固定。
- 汎用トランスコーダー化（任意コーデック・CRF/プリセット）には踏み込まない（最小スコープ）。

## 対象ファイル

- `yt_gui/job_spec.py` — `JobSpec.recode_video` / `PanelSnapshot.recode_video` 追加、`_build_original_spec` で組み立て
- `yt_gui/original_format_panel.py` — ラジオ追加・`get_recode_video()`・settings 入出力・サムネイル/映像/字幕の enable 連動・ツールチップ
- `yt_gui/downloader.py` — `_append_video_postprocessors` に再エンコード経路、`_resolve_unique_path` の `final_ext` 分岐
- `yt_gui/locales/ja.py` / `en.py` — `orig_output_recode`（＋ツールチップ）
- テスト: `tests/test_downloader.py` / `tests/test_job_spec.py`（＋必要なら panel）

## 関連 docs

- spec: [download-formats.md](../spec/features/download-formats.md) / [original-format-panel.md](../spec/screens/original-format-panel.md)
- arch: [downloader.md](../arch/downloader.md#映像の再エンコードh264-mp4--互換性優先) / [job_spec.md](../arch/job_spec.md) / [original_format_panel.md](../arch/original_format_panel.md)

## 進捗メモ

- docs 先行更新済み（spec / arch）。
- 次: テスト先行 → 実装 → green。

## Phase 2（別 PR）

ニコニコ動画コメントの焼きこみ（ハードサブ）は同 Issue #120 の Phase 2 として別途対応。
