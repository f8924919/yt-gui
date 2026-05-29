# タスク一覧

`docs/task/` 配下のタスクの進捗を管理します。タスク追加・完了時にはこのファイルを更新してください。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）
- **完了** : 対応済み

## タスク

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [refine-docs.md](refine-docs.md) | 完了 | CLAUDE.md と docs 構成の改善（言語ルール追加・arch/build ハブ新設・双方向リンク） | 2026-05-16 |
| [yt-dlp-output-template.md](yt-dlp-output-template.md) | 完了 | 設定画面へのOUTPUT TEMPLATE設定UIの追加 | 2026-05-16 |
| [fix-original-format-no-codec.md](fix-original-format-no-codec.md) | 完了 | codec 情報を返さない抽出器（xvideos 等）でオリジナル形式が「プレイリスト」誤判定される不具合の修正 | 2026-05-17 |
| [linux-appimage-build.md](linux-appimage-build.md) | 完了 | Linux 向け PyInstaller ビルド時の AppImage 自動生成 | 2026-05-17 |
| [original-audio-only.md](original-audio-only.md) | 完了 | オリジナル形式パネルの出力形式に「音声のみ」選択肢を追加 | 2026-05-17 |
| [multi-audio-download.md](multi-audio-download.md) | 完了 | オリジナル形式パネルの音声を multi-select 化し、複数音声トラックを MKV にマージできるようにする（フェーズ 1） | 2026-05-20 |
| [proxy-settings.md](proxy-settings.md) | 完了 | 設定ダイアログにプロキシタブを追加し、yt-dlp の `proxy` オプションを GUI から設定可能にする | 2026-05-22 |
| [niconico-comments-verify.md](niconico-comments-verify.md) | 完了 | ニコニコ動画コメント取得（フェーズ 0）: yt-dlp の `comments` JSON が danmaku2ass で変換可能かを事前検証する Go/NoGo ゲート | 2026-05-24 |
| [niconico-comments-phase1.md](niconico-comments-phase1.md) | 完了 | ニコニコ動画コメント取得（フェーズ 1）: `comments` lang を字幕リストに追加し JSON ファイルとして保存可能にする | 2026-05-24 |
| [niconico-comments-phase2.md](niconico-comments-phase2.md) | 完了 | ニコニコ動画コメント取得（フェーズ 2）: danmaku2ass を PyInstaller でビルドして `bin/` に同梱し、コメント JSON を ASS に変換する | 2026-05-24 |
| [niconico-comments-phase3.md](niconico-comments-phase3.md) | 完了 | ニコニコ動画コメント取得（フェーズ 3）: ffmpeg で動画 + ASS を MKV ソフトサブとして統合する | 2026-05-24 |
| [refactor-overview.md](refactor-overview.md) | 完了 | リファクタリング全体計画（フェーズ 1–7 の進行管理） | 2026-05-26 |
| [refactor-job-spec.md](refactor-job-spec.md) | 完了 | リファクタ フェーズ 1: `JobSpec` dataclass + `build_job_spec` 集約 + テスト先行（候補 A/B/C） | 2026-05-25 |
| [refactor-app-split.md](refactor-app-split.md) | 完了 | リファクタ フェーズ 2: `App` を `ThumbnailCache` / `QueueController` に分割（候補 D） | 2026-05-25 |
| [refactor-nico-comments-group.md](refactor-nico-comments-group.md) | 完了 | リファクタ フェーズ 3: `_NicoCommentsGroup` を子ウィジェットに切り出し（候補 E） | 2026-05-26 |
| [refactor-thread-signal-helper.md](refactor-thread-signal-helper.md) | 完了 | リファクタ フェーズ 4: バックグラウンドスレッド + シグナルの共通化（候補 F） | 2026-05-26 |
| [refactor-i18n-combo-sentinel.md](refactor-i18n-combo-sentinel.md) | 完了 | リファクタ フェーズ 5: コンボの sentinel 化 + AUTO/SKIP オフセット隠蔽（候補 G/H） | 2026-05-26 |
| [refactor-downloader-split.md](refactor-downloader-split.md) | 完了 | リファクタ フェーズ 6: `download_video` 分割 + 依存チェック公開化（候補 I/J） | 2026-05-26 |
| [refactor-misc-cleanup.md](refactor-misc-cleanup.md) | 完了 | リファクタ フェーズ 7: 小規模クリーンアップ（候補 K/L） | 2026-05-26 |
| [version-single-source.md](version-single-source.md) | 完了 | バージョンを `pyproject.toml` に単一ソース化（spec へ tomllib 注入 + UI 表示 + copy_metadata 同梱） | 2026-05-29 |
| [release-workflow.md](release-workflow.md) | 完了 | GitHub Actions でバージョン更新時にタグ作成・3 OS リリースバイナリを自動ビルド（Issue #5） | 2026-05-29 |
| [bundle-third-party-licenses.md](bundle-third-party-licenses.md) | 進行中 | GPL/MIT 同梱バイナリのライセンス・対応ソースをリリース成果物に同梱（Issue #12） | 2026-05-29 |
