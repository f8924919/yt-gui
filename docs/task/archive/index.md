# 完了タスク アーカイブ

完了済みタスクの記録です。テーマ別に分類しています。進行中・未着手のタスクは [../index.md](../index.md) を参照してください。

> 各タスクの正式な仕様・実装説明は完了時に `docs/spec/` / `docs/arch/` へ転記済みです。ここに残るのは作業中の設計・進捗メモです。

## 機能追加・改善

| タスク | 概要 | 更新日 |
|---|---|---|
| [yt-dlp-output-template.md](yt-dlp-output-template.md) | 設定画面へのOUTPUT TEMPLATE設定UIの追加 | 2026-05-16 |
| [original-audio-only.md](original-audio-only.md) | オリジナル形式パネルの出力形式に「音声のみ」選択肢を追加 | 2026-05-17 |
| [multi-audio-download.md](multi-audio-download.md) | オリジナル形式パネルの音声を multi-select 化し、複数音声トラックを MKV にマージできるようにする（フェーズ 1） | 2026-05-20 |
| [proxy-settings.md](proxy-settings.md) | 設定ダイアログにプロキシタブを追加し、yt-dlp の `proxy` オプションを GUI から設定可能にする | 2026-05-22 |

## バグ修正

| タスク | 概要 | 更新日 |
|---|---|---|
| [fix-original-format-no-codec.md](fix-original-format-no-codec.md) | codec 情報を返さない抽出器（xvideos 等）でオリジナル形式が「プレイリスト」誤判定される不具合の修正 | 2026-05-17 |

## ニコニコ動画コメント取得

| タスク | 概要 | 更新日 |
|---|---|---|
| [niconico-comments-verify.md](niconico-comments-verify.md) | フェーズ 0: yt-dlp の `comments` JSON が danmaku2ass で変換可能かを事前検証する Go/NoGo ゲート | 2026-05-24 |
| [niconico-comments-phase1.md](niconico-comments-phase1.md) | フェーズ 1: `comments` lang を字幕リストに追加し JSON ファイルとして保存可能にする | 2026-05-24 |
| [niconico-comments-phase2.md](niconico-comments-phase2.md) | フェーズ 2: danmaku2ass を PyInstaller でビルドして `bin/` に同梱し、コメント JSON を ASS に変換する | 2026-05-24 |
| [niconico-comments-phase3.md](niconico-comments-phase3.md) | フェーズ 3: ffmpeg で動画 + ASS を MKV ソフトサブとして統合する | 2026-05-24 |

## リファクタリング（フェーズ 1–7）

| タスク | 概要 | 更新日 |
|---|---|---|
| [refactor-overview.md](refactor-overview.md) | リファクタリング全体計画（フェーズ 1–7 の進行管理） | 2026-05-26 |
| [refactor-job-spec.md](refactor-job-spec.md) | フェーズ 1: `JobSpec` dataclass + `build_job_spec` 集約 + テスト先行（候補 A/B/C） | 2026-05-25 |
| [refactor-app-split.md](refactor-app-split.md) | フェーズ 2: `App` を `ThumbnailCache` / `QueueController` に分割（候補 D） | 2026-05-25 |
| [refactor-nico-comments-group.md](refactor-nico-comments-group.md) | フェーズ 3: `_NicoCommentsGroup` を子ウィジェットに切り出し（候補 E） | 2026-05-26 |
| [refactor-thread-signal-helper.md](refactor-thread-signal-helper.md) | フェーズ 4: バックグラウンドスレッド + シグナルの共通化（候補 F） | 2026-05-26 |
| [refactor-i18n-combo-sentinel.md](refactor-i18n-combo-sentinel.md) | フェーズ 5: コンボの sentinel 化 + AUTO/SKIP オフセット隠蔽（候補 G/H） | 2026-05-26 |
| [refactor-downloader-split.md](refactor-downloader-split.md) | フェーズ 6: `download_video` 分割 + 依存チェック公開化（候補 I/J） | 2026-05-26 |
| [refactor-misc-cleanup.md](refactor-misc-cleanup.md) | フェーズ 7: 小規模クリーンアップ（候補 K/L） | 2026-05-26 |

## リリース・配布基盤

| タスク | 概要 | 更新日 |
|---|---|---|
| [linux-appimage-build.md](linux-appimage-build.md) | Linux 向け PyInstaller ビルド時の AppImage 自動生成 | 2026-05-17 |
| [version-single-source.md](version-single-source.md) | バージョンを `pyproject.toml` に単一ソース化（spec へ tomllib 注入 + UI 表示 + copy_metadata 同梱） | 2026-05-29 |
| [release-workflow.md](release-workflow.md) | GitHub Actions でバージョン更新時にタグ作成・3 OS リリースバイナリを自動ビルド（Issue #5） | 2026-05-29 |
| [bundle-third-party-licenses.md](bundle-third-party-licenses.md) | GPL/MIT 同梱バイナリのライセンス・対応ソースをリリース成果物に同梱（Issue #12） | 2026-05-29 |

## テスト基盤

| タスク | 概要 | 更新日 |
|---|---|---|
| [qt-ui-test-ci.md](qt-ui-test-ci.md) | Qt UI テスト導入 (1): `test.yml` 新設で PR/push に ruff・mypy・pytest の CI を追加、Qt offscreen の土台も先行投入（Issue #17） | 2026-05-30 |
| [qt-ui-test-policy.md](qt-ui-test-policy.md) | Qt UI テスト導入 (2): `policy.md` の Qt UI 行を `△` に格上げ・実行要件（§2.5）を明文化・spec 整合を確認（PR #19） | 2026-05-30 |

## ドキュメント整備

| タスク | 概要 | 更新日 |
|---|---|---|
| [refine-docs.md](refine-docs.md) | CLAUDE.md と docs 構成の改善（言語ルール追加・arch/build ハブ新設・双方向リンク） | 2026-05-16 |
