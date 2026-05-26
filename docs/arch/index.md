# yt-gui アーキテクチャ — 目次

`yt_gui/` パッケージ各モジュールの実装詳細を記載します。
モジュールを変更・拡張するときは、対応するファイルも合わせて更新してください。

---

## スレッド間通信パターン

バックグラウンドスレッドから直接 Qt ウィジェットを操作しないこと。`Signal` / `Slot` を経由してメインスレッドにキューイングすること。Qt シグナルは別スレッドから emit しても自動的に `Qt.QueuedConnection` でメインスレッドへ配送される。シグナル定義・一覧は [app.md](app.md) を参照。

---

## モジュール一覧

| ドキュメント | モジュール | 関連仕様 |
|---|---|---|
| [entry.md](entry.md) | `__main__.py` / `__init__.py` — エントリーポイント・リソースパス解決 | — |
| [app.md](app.md) | `app.py` — メインウィンドウ・ウィジェット組み立て・シグナル配線 | [メインウィンドウ](../spec/screens/main-window.md) / [ダウンロードキュー](../spec/features/queue.md) |
| [queue_controller.md](queue_controller.md) | `queue_controller.py` — キュー所有・ワーカースレッド・編集モード状態機械 | [ダウンロードキュー](../spec/features/queue.md) |
| [thumbnail_cache.md](thumbnail_cache.md) | `thumbnail_cache.py` — 動画サムネイル画像の非同期取得・キャッシュ | — |
| [threading_utils.md](threading_utils.md) | `threading_utils.py` — バックグラウンドスレッド + Qt シグナル転送の共通ヘルパ | — |
| [downloader.md](downloader.md) | `downloader.py` — yt-dlp ラッパー・ダウンロード実行 | [ダウンロード動作](../spec/features/download-behavior.md) / [ダウンロード形式](../spec/features/download-formats.md) |
| [original_format_panel.md](original_format_panel.md) | `original_format_panel.py` — オリジナル形式パネル | [オリジナル形式パネル](../spec/screens/original-format-panel.md) |
| [settings_dialog.md](settings_dialog.md) | `settings_dialog.py` — 設定ダイアログ | [設定ダイアログ](../spec/screens/settings-dialog.md) |
| [log_dialog.md](log_dialog.md) | `log_dialog.py` — ログ表示ダイアログ | [ログダイアログ](../spec/screens/log-dialog.md) |
| [settings.md](settings.md) | `settings.py` — 設定の読み書き | [設定管理](../spec/settings.md) |
| [formats.md](formats.md) | `formats.py` — フォーマット定数・仕様生成関数 | [ダウンロード形式](../spec/features/download-formats.md) |
| [job_spec.md](job_spec.md) | `job_spec.py` — `JobSpec` DTO と `build_job_spec` (`format_id` 派生ラダー集約) | [ダウンロード形式](../spec/features/download-formats.md) / [ダウンロード動作](../spec/features/download-behavior.md) |
| [output_template.md](output_template.md) | `output_template.py` — OUTPUT TEMPLATE 定数・検証/プレビュー補助 | [設定管理](../spec/settings.md) |
| [i18n.md](i18n.md) | `i18n.py` — 多言語対応 | [多言語対応](../spec/i18n.md) |
| [locales.md](locales.md) | `locales/` — 言語別文字列辞書 | [多言語対応](../spec/i18n.md) |
| [utils.md](utils.md) | `utils.py` — 共通ユーティリティ | — |

---

## 新しい言語を追加する手順

[locales.md](locales.md) を参照。
