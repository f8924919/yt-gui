# #243 再翻訳の生成時登録方式への置き換え（再翻訳漏れの恒久対策）

- Issue: https://github.com/f8924919/yt-gui/issues/243
- ブランチ: `feature/243-retranslate-registry`
- ステータス: 完了（2026-07-12）

## 背景

#238（区間ダウンロード UI の再翻訳漏れ）の根本原因は、ウィジェット生成と `_retranslate_ui()` の手動列挙が分離しており、機械的な紐付けがないこと。#238 は列挙追記の対症療法で完了し、恒久対策は対象外とされていた。本タスクでその恒久対策を実装する。

## 方針（決定済み）

- **案A（構造的解決）**: 「初期テキスト設定＋再翻訳登録」を同時に行うバインドヘルパを新設し、`_retranslate_ui()` をレジストリ走査に置き換える。
- **案B（セーフティネット）**: `set_language("en")` 後にウィジェットツリーを走査し、ja 固有文字列の残留を検出するテストを追加。
- 却下案: Qt 標準機構（QTranslator / .ts / .qm）への移行 — 自前 i18n（約267キー・テスト整備済み）を捨てる大移行でスコープ過大。

## 進捗

- [x] Issue 起票（#243）
- [x] ブランチ作成
- [x] 調査（investigate: static 26 / dynamic 6 / combo 1 / transient 約45 を全列挙）
- [x] 受け入れ条件レビュー（criteria-review → 指摘反映で Issue 本文更新済み）
- [x] docs 先行（docs/arch/app.md「翻訳バインディング」節・docs/spec/i18n.md「再発防止」節）
- [x] 設計レビュー（design-review → 手動残置で確定・専用テスト追加等を採用。結果は Issue コメント）
- [x] テスト先行（レジストリ全件検証・セーフティネット・複数選択編集・編集モードボタンの 4 本）
- [x] 実装 → green（ruff / format / mypy / pytest 477 件）
- [x] verify-gate → PR

## 実装サマリ

- `_TranslationBinding`（frozen dataclass: key / setter / getter / transform）＋ `_bind_translation` / `_bind_text` / `_bind_header_column` を新設。static 26 箇所を生成時バインドに置き換え、`_retranslate_ui()` はレジストリ走査＋状態依存の手動ブロックに再構成。
- `_window_title()` は撤去（`app_title` バインディングの transform に統合）。
- 新発見漏れ `edit_multiple_selected` は `_retranslate_ui()` の状態依存ブロックで解消。

## 調査で得た正本情報

- **static 26 箇所**: 生成側 `t(key)` と `_retranslate_ui()` 側がキー単位 1:1 重複。レジストリ化の対象。
- **状態依存 3 系統**: `add_button`（edit_mode 分岐）、`status_label`（実行中スキップ）、`url_entry` 複数選択表示（`edit_multiple_selected`、**未登録の実漏れ → 本タスクで解消**）。
- **combo**: `_refresh_format_labels()` 経由（設定値加味の都度再構築）。
- **transient 約 45 箇所**: 都度生成のため対象外。
- setter 差異: QMenu=`setTitle`、QAction/QLabel 等=`setText`、ツリーヘッダー=列単位。
- 派生 Issue: #244（`btn_adding` 状態消失、本タスク後に着手）。

## メモ

- 状態依存テキストと combo は手動残置を許容（理由コメント必須）。手動残置 vs レジストリ拡張は design-review の論点。
- ダイアログ類・インライン QMessageBox 等の transient は毎回生成方式のため対象外。
