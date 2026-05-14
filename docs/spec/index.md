# yt-gui 仕様書 — 目次

このディレクトリは yt-gui の動作仕様・画面仕様を記載します。
実装を変更・拡張するときは、対応するファイルも合わせて更新してください。

---

## 概要

- [アプリ概要](overview.md) — 機能一覧・対応形式・動作環境

---

## 画面仕様

| ファイル | 内容 |
|---|---|
| [メインウィンドウ](screens/main-window.md) | URL入力・形式選択・キュー表示・ステータスバー・メニューバー |
| [設定ダイアログ](screens/settings-dialog.md) | 一般タブ（保存先・Cookies・言語）・画質音質タブ |
| [オリジナル形式パネル](screens/original-format-panel.md) | 映像/音声/字幕トラック選択・出力形式・メタデータ設定 |
| [ログダイアログ](screens/log-dialog.md) | 動作ログ表示・クリア |

---

## 機能仕様

| ファイル | 内容 |
|---|---|
| [ダウンロードキュー](features/queue.md) | キュー追加・実行・一時停止・削除・編集モード・ツールチップ |
| [ダウンロード形式](features/download-formats.md) | 形式定義・yt-dlp フォーマット文字列生成ロジック |
| [ダウンロード動作](features/download-behavior.md) | ファイル名重複回避・プレイリスト・サムネイル埋め込み・字幕・Cookies |

---

## 設定・多言語

| ファイル | 内容 |
|---|---|
| [設定管理](settings.md) | 設定項目・永続化パス・デフォルト値・設定変更の反映タイミング |
| [多言語対応](i18n.md) | 翻訳関数・言語切り替え・新言語追加手順 |

---

## アーキテクチャ（モジュール実装）

モジュールレベルの実装詳細は [`docs/arch/`](../arch/) 以下に別途記載。

| ドキュメント | モジュール |
|---|---|
| [entry.md](../arch/entry.md) | `__main__.py` / `__init__.py` |
| [app.md](../arch/app.md) | `app.py` |
| [downloader.md](../arch/downloader.md) | `downloader.py` |
| [original_format_panel.md](../arch/original_format_panel.md) | `original_format_panel.py` |
| [settings_dialog.md](../arch/settings_dialog.md) | `settings_dialog.py` |
| [log_dialog.md](../arch/log_dialog.md) | `log_dialog.py` |
| [settings.md](../arch/settings.md) | `settings.py` |
| [formats.md](../arch/formats.md) | `formats.py` |
| [i18n.md](../arch/i18n.md) | `i18n.py` |
| [locales.md](../arch/locales.md) | `locales/` |
| [utils.md](../arch/utils.md) | `utils.py` |
