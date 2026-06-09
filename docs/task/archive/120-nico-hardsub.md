# 互換性優先（再エンコード）出力モード — Phase 2: ニコニコ動画コメントの焼きこみ（ハードサブ）

- 対応 Issue: [#120](https://github.com/f8924919/yt-gui/issues/120)（Phase 2 完了で #120 クローズ）
- ブランチ: `feature/120-nico-hardsub`（マージ済み・削除済み）
- PR: [#123](https://github.com/f8924919/yt-gui/pull/123)（マージ済み）
- ステータス: 完了（2026-06-09）

## 背景 / 目的

ニコニコ動画コメントの動画統合は現状ソフトサブ MKV（`-c copy`・無劣化）のみで、ASS をレンダリングできる環境が前提。SNS 投稿・スマホ標準プレーヤーなど ASS 非対応環境でもコメント付きで見られるよう、コメントを映像に焼き付けた（ハードサブ）動画を生成する。Phase 1（[120-recode-video](120-recode-video.md)）と同じ「再エンコードを許容する」軸。

## 設計方針（確定事項・ユーザー確認済み）

- 既存ソフトサブ MKV 統合は**置き換えず併設**。`_NicoCommentsGroup` に独立チェック「コメントを焼きこむ（ハードサブ）」を追加。MKV 統合と同時 ON 可（別ファイルを生成）。
- 焼きこみチェックは ASS 変換に依存（ON で ASS 変換を強制 ON、ASS 変換 OFF で焼きこみも OFF）。「音声のみ」「remux のみ」では disable。
- 出力は常に `{stem}.hardsub.mp4`、映像 H.264 / 音声 AAC（Phase 1 と統一）。元動画・既存出力は触らない。
- ffmpeg は subprocess（既存 `_embed_nico_comments_into_mkv` と同パターン）。`ass` フィルタで焼き付け。
- **filtergraph パスエスケープ**: `cwd` を動画ディレクトリにして ASS のベース名のみをフィルタに渡し、`_escape_ass_filter_value()` で単一引用符＋`\`/`'` エスケープ。Windows のドライブコロン・パス区切りを構造的に回避。
- 失敗・前提ファイル不在はすべて非致命（ログのみ）。

## 対象ファイル

- `yt_gui/downloader.py` — `_burn_nico_comments_into_video` / 純関数 `_build_hardsub_cmd` / `_escape_ass_filter_value`、`download_video` の呼び出し追加
- `yt_gui/original_format_panel.py` — `_NicoCommentsGroup` に焼きこみチェック・`get_opts`/`restore_from`・enable 連動・tooltip
- `yt_gui/locales/ja.py` / `en.py` — `nico_burn_in`（＋ tooltip）・`status_nico_hardsub_created` / `warn_nico_hardsub_*`
- テスト: `tests/test_downloader.py`（cmd 構成・エスケープ・ガード）

## 関連 docs

- spec: [original-format-panel.md](../../spec/screens/original-format-panel.md)
- arch: [downloader.md](../../arch/downloader.md#コメント-ass-の動画への焼きこみハードサブ) / [original_format_panel.md](../../arch/original_format_panel.md)

## 進捗メモ

- docs 先行 → テスト先行 → 実装 → green 完了。verify-gate（verify / docs-check / evaluator）通過。
- stale だったニコ動コメント節の旧フェーズ記述も現状へ整合済み。
- これにより Issue #120（Phase 1 + Phase 2）が完結。
