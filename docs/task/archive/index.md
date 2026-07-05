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
| [108-parallel-downloads.md](108-parallel-downloads.md) | 並列ダウンロード（複数アイテム同時実行）＋キュー行単位の進捗表示。Downloader を N プール化・ステータス列に進捗 %・ステータスバーを全体進捗に変更（Issue #108 / PR #110） | 2026-06-08 |
| [120-recode-video.md](120-recode-video.md) | 互換性優先の H.264 MP4 再エンコード出力を追加（`FFmpegVideoConvertor` で H.264/AAC 強制・中間 mkv 固定）。#120 Phase 1（Issue #120 / PR #121） | 2026-06-09 |
| [120-nico-hardsub.md](120-nico-hardsub.md) | ニコニコ動画コメントの焼きこみ（ハードサブ）出力を追加（`ass` フィルタで H.264/AAC MP4 を別生成・ソフトサブ MKV と併設）。#120 Phase 2＝#120 完結（Issue #120 / PR #123） | 2026-06-09 |
| [browser-extension.md](browser-extension.md) | ブラウザ拡張から URL + Cookie をワンクリックでキュー追加（ローカル受信サーバー・アイテム単位 Cookie・設定タブ・MV3 拡張）。途中で `cookiefile` キー誤りの pre-existing バグも修正、CI lint を `ruff check .` に拡張（Issue #140 / PR #141） | 2026-06-13 |
| [143-extension-enhancements.md](143-extension-enhancements.md) | ブラウザ拡張の改善: オプション画面の多言語化（`_locales` + `chrome.i18n` でブラウザ言語追従）・manifest 英語化・バージョン同期（`sync_extension_version.py`）・アイコン統一（`build_extension_icons.py`）・リリース zip 生成。README も現状反映（Issue #143 / PR #144） | 2026-06-13 |
| [149-extension-format-selection.md](149-extension-format-selection.md) | ブラウザ拡張のポップアップで形式選択（最高画質/解像度/音声/アプリ既定）に対応。案A＝拡張はコンテナ非依存で意味のみ送り形式解決はアプリ側に一任、`resolve_extension_format` でクランプ。オリジナル形式は #151 へ分離（Issue #149 / PR #150） | 2026-06-14 |
| [151-extension-original-format-dialog.md](151-extension-original-format-dialog.md) | 拡張から `kind:"original"` を送るとアプリ側で `OriginalFormatDialog` を開く導線。`resolve_extension_format` を 3 状態化（`OriginalIntent` センチネル）、pending キュー＋`QTimer.singleShot` で直列起動（多重モーダル防止）・ウィンドウ前面化・アイテム単位 Cookies 引き回し・キャンセル時は非追加（Issue #151 / PR #153） | 2026-06-14 |
| [157-settings-sidebar-nav.md](157-settings-sidebar-nav.md) | 設定ダイアログを上部横並びタブから左サイドバー型（`QListWidget`＋`QStackedWidget` のラッパー `_SidebarNav`）へ刷新し、macOS でタブが窮屈に潰れる問題を解消。固定サイズを 700×520 に拡大・`QTabWidget` 互換 API でページ切替を維持（Issue #157 / PR #158） | 2026-06-15 |
| [164-extension-chrome-ui.md](164-extension-chrome-ui.md) | ブラウザ拡張の popup/options を Material 3（現行 Chrome 風）デザインへ刷新。アクセント `#0b57d0`・ピル型ボタン・`prefers-color-scheme` でダーク追従、色/角丸/余白を CSS カスタムプロパティに集約。既存 JS 参照の id/`.hidden`/`data-i18n` は非破壊（Issue #164 / PR #165） | 2026-06-15 |
| [168-bilibili-danmaku-comments.md](168-bilibili-danmaku-comments.md) | ニコニコ動画コメント機能を一般化し、ビリビリ動画の弾幕（yt-dlp `danmaku` lang / Bilibili XML）も ASS 変換・MKV ソフトサブ統合・ハードサブ焼き込みに対応。サイドカー専用字幕を `_SIDECAR_ONLY_SUB_LANGS` に汎用化、lang→形式マップで `-f Bilibili` に分岐、UI グループも `comments`/`danmaku` 双方で表示（Issue #168 / PR #169） | 2026-06-16 |
| [119-yt-dlp-update-design.md](119-yt-dlp-update-design.md) | yt-dlp 本体更新の実装方式を決定（A→B 段階導入：更新チェック＋通知→side-load 実体更新、C は不採用）。採用方式の spec/arch を新規作成し、実装は Phase A=#178 / Phase B=#179 へ分離（Issue #119 / PR #180） | 2026-06-20 |
| [178-ytdlp-update-phase-a.md](178-ytdlp-update-phase-a.md) | yt-dlp 更新 Phase A: ヘルプメニューに「バージョン情報 / 更新を確認」を追加。yt-gui/yt-dlp 版を併記し、PyPI JSON API 照会で最新版と比較・通知（古い場合は GitHub releases 導線）。照会は純関数 `yt_dlp_update.py`（HTTP 差し替え可）＋ `run_in_thread` でバックグラウンド実行（Issue #178 / PR #182） | 2026-06-20 |
| [198-app-update-phase-a.md](198-app-update-phase-a.md) | アプリ更新 Phase A: yt-gui 本体の更新チェック＋通知。GitHub Releases API 照会の純関数 `app_update.py`（yt_dlp_update 同型）、起動時自動チェック＋オプトアウト設定（既定オン）、バージョン情報ダイアログに「yt-gui の更新を確認」追加・既存ボタンは「yt-dlp の更新を確認」へ改称。Phase B 方式調査は research/app-update.md に記録（Issue #198 / PR #199） | 2026-07-05 |

## バグ修正

| タスク | 概要 | 更新日 |
|---|---|---|
| [fix-original-format-no-codec.md](fix-original-format-no-codec.md) | codec 情報を返さない抽出器（xvideos 等）でオリジナル形式が「プレイリスト」誤判定される不具合の修正 | 2026-05-17 |
| [160-settings-menu-role.md](160-settings-menu-role.md) | macOS で設定メニュー項目の置き場所が言語で異なる不具合（`menuRole` 未指定＝英語テキスト依存マージ）を、`_act_settings` に `PreferencesRole` を明示して言語非依存にアプリメニュー配下へ統一（Issue #160 / PR #161） | 2026-06-15 |
| [175-extension-original-label.md](175-extension-original-label.md) | 拡張から `kind:"original"` 送信時にキュー表示が「最高画質」に化けるバグを修正。`_build_original_job` のラベル基点をコンボの `currentText()` から `_format_display[FORMAT_KEYS.index(fmt_original)]` 固定へ（拡張フローはコンボ非操作のため既定 fmt_best_mp4 に化けていた偶発結合を解消）（Issue #175 / PR #176） | 2026-06-19 |

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
| [132-modal-driven-qt-tests.md](132-modal-driven-qt-tests.md) | Qt UI テスト: モーダル経路を手段B（offscreen + `QTimer`/静的メソッド固定）で検証。設定ダイアログの `_clear_archive`/`_save` 確認・検証分岐、`_open_original_dialog` 追加フロー、`_open_settings` 反映ループ。omit 解除は #134 へ分離（Issue #132 / PR #133） | 2026-06-12 |
| [137-medium-qt-tests.md](137-medium-qt-tests.md) | Qt UI テスト（優先度中・手段A）: 設定ダイアログの `_browse_*` ファイル選択反映・`_on_archive_toggled` 活性連動、`_open_log_dialog` 起動/再利用、`LogDialog.load`/`append`。`log_dialog.py` を ×→△ 格上げ（Issue #137 / PR #138） | 2026-06-12 |
| [134-coverage-omit-release.md](134-coverage-omit-release.md) | coverage の `omit` から `app.py` / `settings_dialog.py` を解除し計測対象化。TOTAL 92%→85%（app.py 66% / settings_dialog.py 96%）。policy §1・§5、testing/index を実態へ更新（Issue #134 / PR #147） | 2026-06-14 |

## ドキュメント整備

| タスク | 概要 | 更新日 |
|---|---|---|
| [refine-docs.md](refine-docs.md) | CLAUDE.md と docs 構成の改善（言語ルール追加・arch/build ハブ新設・双方向リンク） | 2026-05-16 |
| [evaluator-agent.md](evaluator-agent.md) | evaluator サブエージェント新設（計画・生成・評価の3分離）。受け入れ条件・spec の充足を独立評価（Opus）、feature/bugfix/hotfix で必須（Issue #99 / PR #100） | 2026-06-07 |
| [skill-layer.md](skill-layer.md) | Skills 層の新設。PR 前検証ゲート `/verify-gate` とマージ後処理 `/finish-task` を追加し git-workflow §5.3 に位置づけ。skill はルールを再定義せず正本を参照（Issue #102 / PR #103） | 2026-06-07 |
| [start-task-skill.md](start-task-skill.md) | ワークフロー前半（§5 step 1-6）の入口 skill `/start-task` を新設。docs 先・テスト先の順序ゲートで実装先行を防止。判断ステップは確認ゲートに留め自動化しない（Issue #105 / PR #106） | 2026-06-07 |
| [claude-rules-layer.md](claude-rules-layer.md) | `.claude/rules/` path-scoped ルール層を新設。テスト/docs 編集時に遵守事項を再注入（`testing.md` / `docs-upkeep.md`）。薄いポインタに徹し正本を参照、git-workflow §5.4 を新設（Issue #125 / PR #126） | 2026-06-11 |
| [191-criteria-review-agent.md](191-criteria-review-agent.md) | 実装前に受け入れ条件・spec そのものの妥当性（テスト可能・網羅的・非曖昧・Issue 意図整合）を点検する助言エージェント `criteria-review`（Sonnet・read-only）を新設し、start-task の step 3.5 に組み込む。evaluator（実装後・適合性・ゲート）と対象が逆で補完関係、ゲート化せず助言に留める。step 番号は renumber せず 3.5 挿入。docs-guide §4.1 にエージェント/スキル変更行も追記（Issue #191 / PR #192） | 2026-07-04 |
| [194-design-review-agent.md](194-design-review-agent.md) | 設計案の妥当性（アーキ整合・代替案・結合/スコープ・リスク・docs 整合）を実装前に点検する助言エージェント `design-review`（Opus・read-only）を新設し、start-task の step 4.5 に組み込む。発火は主観でなく §5.5 の客観トリガで機械的判定（investigate が推奨 yes/no を出力）、推奨 yes の主観スキップは禁止しユーザー承認必須。criteria-review（step 3.5）の初運用で受け入れ条件を強化（Issue #194 / PR #195） | 2026-07-04 |
