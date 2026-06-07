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
| [concurrent-fragments.md](concurrent-fragments.md) | 設定ダイアログに「ダウンロード」タブを新設し、並列フラグメント DL（`concurrent-fragments`）を指定可能にする（Issue #53 / PR #54） | 2026-05-31 |
| [57-sponsorblock.md](57-sponsorblock.md) | 設定ダイアログに「SponsorBlock」タブを新設し、スポンサー区間の印付け（mark）/ 除去（remove）に対応（Issue #57 / PR #58） | 2026-06-01 |
| [original-format-dialog.md](original-format-dialog.md) | オリジナル形式パネルをモーダルダイアログへ分離。メイン QSplitter 撤去・幅縮小・ニコ動コメント設定の折り返しも実施（Issue #61 / PR #62） | 2026-06-02 |
| [limit-rate.md](limit-rate.md) | 設定ダイアログの「ダウンロード」タブに速度制限（`--limit-rate` / `ratelimit`）を追加。値 + 単位（KB/s・MB/s）、0 で無制限（Issue #64 / PR #65） | 2026-06-02 |
| [67-cancel-downloading.md](67-cancel-downloading.md) | 「一時停止」で進行中ダウンロードを即中断し `waiting` へ戻す。中断時に部分ファイル・字幕サイドカーを削除（Issue #67 / PR #68） | 2026-06-02 |
| [75-download-archive.md](75-download-archive.md) | ダウンロードアーカイブ（`--download-archive` 相当）を追加。差分取得・再 DL 防止、新ステータス `skipped`。アイテム単位再取得は #76 へ分離（Issue #75 / PR #77） | 2026-06-03 |
| [81-download-sections.md](81-download-sections.md) | 区間ダウンロード（時間範囲の切り出し）を追加。安定性優先でフル取得→ローカル ffmpeg 切り出し方式。チャプター指定は #83、通信量節約版は #84 へ分離（Issue #81 / PR #82） | 2026-06-04 |
| [76-ignore-archive-refetch.md](76-ignore-archive-refetch.md) | アイテム単位でダウンロードアーカイブを無視して再取得する手段を追加。右クリック「アーカイブを無視して再取得」、再記録せず既存記録は保持（Issue #76 / PR #91） | 2026-06-07 |

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
| [actions-node24.md](actions-node24.md) | GitHub Actions を Node24 メジャーへ更新（checkout v6・setup-uv v7・upload v7・download v8）。`test.yml` / `release.yml`（Issue #24 / PR #28） | 2026-05-30 |
| [intel-mac-build.md](intel-mac-build.md) | リリース CI に `macos-15-intel` を追加し x86_64 成果物を配布・macOS パッケージ名の arch 動的化（Issue #41 / PR #43） | 2026-05-30 |
| [macos-arm64-ffmpeg.md](macos-arm64-ffmpeg.md) | arm64 リリースの ffmpeg を osxexperts.net 由来の Apple Silicon ネイティブ版に変更し Rosetta 依存を解消（Issue #42 / PR #44） | 2026-05-30 |

## テスト基盤

| タスク | 概要 | 更新日 |
|---|---|---|
| [qt-ui-test-ci.md](qt-ui-test-ci.md) | Qt UI テスト導入 (1): `test.yml` 新設で PR/push に ruff・mypy・pytest の CI を追加、Qt offscreen の土台も先行投入（Issue #17） | 2026-05-30 |
| [qt-ui-test-policy.md](qt-ui-test-policy.md) | Qt UI テスト導入 (2): `policy.md` の Qt UI 行を `△` に格上げ・実行要件（§2.5）を明文化・spec 整合を確認（PR #19） | 2026-05-30 |
| [qt-ui-test-harness.md](qt-ui-test-harness.md) | Qt UI テスト導入 (3): `pytest-qt` 導入・conftest 整備（offscreen / QMessageBox 抑制 / importorskip）・`threading_utils` / `queue_controller` のテスト追加（Issue #20 / PR #21） | 2026-05-30 |
| [original-format-panel-tests.md](original-format-panel-tests.md) | Qt UI テスト: `_AudioListWidget` の AUTO/SKIP/音声 ID 排他ロジックのテスト追加（Issue #22 / PR #26） | 2026-05-30 |
| [app-ui-logic-tests.md](app-ui-logic-tests.md) | Qt UI テスト: `_QueueTree._edit_targets` の編集対象判定・`_refresh_format_labels` の言語追従のテスト追加（モーダル QMenu.exec 回避のため `_edit_targets` を抽出）（Issue #23 / PR #27） | 2026-05-30 |

## ドキュメント整備

| タスク | 概要 | 更新日 |
|---|---|---|
| [refine-docs.md](refine-docs.md) | CLAUDE.md と docs 構成の改善（言語ルール追加・arch/build ハブ新設・双方向リンク） | 2026-05-16 |
| [evaluator-agent.md](evaluator-agent.md) | evaluator サブエージェント新設（計画・生成・評価の3分離）。受け入れ条件・spec の充足を独立評価（Opus）、feature/bugfix/hotfix で必須（Issue #99 / PR #100） | 2026-06-07 |
| [skill-layer.md](skill-layer.md) | Skills 層の新設。PR 前検証ゲート `/verify-gate` とマージ後処理 `/finish-task` を追加し git-workflow §5.3 に位置づけ。skill はルールを再定義せず正本を参照（Issue #102 / PR #103） | 2026-06-07 |
| [start-task-skill.md](start-task-skill.md) | ワークフロー前半（§5 step 1-6）の入口 skill `/start-task` を新設。docs 先・テスト先の順序ゲートで実装先行を防止。判断ステップは確認ゲートに留め自動化しない（Issue #105 / PR #106） | 2026-06-07 |
