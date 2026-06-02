# オリジナル形式パネルのモーダルダイアログ分離（#61）

対応 Issue: [#61](https://github.com/f8924919/yt-gui/issues/61)

## 概要

メインウィンドウ上段にインライン埋め込みされている `OriginalFormatPanel`（約 1226 行）を、`settings_dialog.py` と同型のモーダル `QDialog`（`OriginalFormatDialog`）へ分離する。今後の機能追加に耐えるレイアウト余地を確保し、メインウィンドウから高さ同期機構を撤去して単純化する。

既存 `OriginalFormatPanel`（`QGroupBox`）はロジック資産（sentinel 方式・排他制御・`get_snapshot` 等、テスト済み）を温存するため、基本そのままダイアログ内へ再ペアレントして再利用する。

## 確定方針

1. **方式**: モーダル `QDialog`。既存パネルを内部に再ペアレント。
2. **追加操作はダイアログ内**: 「キューに追加」/編集時「変更」をダイアログ内ボタンに。ダイアログは `add_requested` / `edit_applied` / `edit_cancelled` シグナルで `App` に通知する薄いシェル。enqueue は `App` / `QueueController` が行う（キュー所有は移動しない）。

### 課題1: 追加後の挙動 → 閉じる

- 追加成功で `accept()`。連続追加用に開いたままにはしない。
- 根拠: オリジナル形式は動画 1 本単位の操作（フォーマットは特定 URL に対して取得）。開いたままだと前動画の取得結果が残り誤選択の温床になる。現行の「追加成功 → `reset()` + URL クリア」（app.py:644-645）とも整合。

### 課題2: 「未取得のまま追加」経路 → 温存

- ダイアログの追加ボタンは取得済み/未取得を区別せず snapshot + URL を emit。`App` 側で現状の `has_formats_loaded()` 分岐（app.py:637-649）をそのまま使う。
  - 取得済み → 選択値で即 enqueue（単独動画）。
  - 未取得 → 既存のバックグラウンド取得→enqueue 経路（`_start_add_thread`）に委譲。
- 根拠: この経路は単独動画でフォーマット取得を省き、auto 選択のまま出力モード・埋め込み等だけ指定して追加するユースケースを担う。取得必須にするとこの素早い追加経路が失われる。
- **注意（コード裏取りで判明・当初想定の訂正）**: オリジナル形式はプレイリスト非対応。`_on_fetch_for_add_done`（app.py:716-719）がプレイリスト判明時に `warn_playlist_original_fmt` で中止する。当初「未取得追加でプレイリスト対応を維持」と書いていたが誤りで、未取得追加は単独動画のための経路。
- 移動するのはボタンの場所と検証 2 種（`warn_skip_both` / `warn_skip_audio_only`、app.py:622-628）のみ。判定ロジックは `App` に残す。

### 編集モードの扱い（docs 化に伴い確定）

編集モードでは形式コンボで形式タイプ切替（オリジナル ↔ 他形式）が可能（app.py:763-768）であり、「変更」ボタンを兼ねている。これを踏まえ:

- メインウィンドウの編集モード UI（URL 読み取り専用・形式コンボ・キャンセルボタン）は維持する。
- 編集対象がオリジナル形式のときは、メインの「変更」ボタンの代わりに「詳細設定...」ボタンを出し、ダイアログを**編集モードで開いて「変更」を適用**する（`edit_applied`）。`App` が `orig_settings` を渡し、復元 + 取得はダイアログ側。`キャンセル`はメイン側に残す。
- 形式タイプをオリジナル以外へ切り替えた場合は従来どおりメインの「変更」ボタンで適用。

> この編集モードのオーケストレーション（ダイアログを編集で開く／メインのボタン出し分け）は「追加操作はダイアログ内」の自然な拡張として確定扱いとする。実装時に不都合が出た場合は §5.1 に従い案を提示する。

### 必要な i18n キー（実装時に ja/en 追加）

- 「詳細設定...」ボタン
- ダイアログタイトル（`label_original_detail` 流用可）
- ダイアログ主ボタン「キューに追加」/「変更」、副ボタン「キャンセル」

検証文言（`warn_skip_both` / `warn_skip_audio_only` / `warn_no_url`）は既存を流用。

### 課題3: ダイアログは使い捨て（開くたびに生成・破棄）

- 永続インスタンスを持たない。生成時点の言語・コンテナ設定で組み立てる。
- 根拠: 課題1・2 の決定により状態を跨いで保持する必要がない。使い捨てにすれば言語変更を生存インスタンスへ配送する `retranslate` 再配線が不要になる。`retranslate(video_container, audio_label)` は生成直後に 1 回呼ぶだけ（現状 app.py:461 と同じ）。
- 編集モードは開くたびに `restore_from_settings` + `trigger_fetch` を実行する設計なので使い捨てでも回帰しない。widget 生成は I/O を伴わず軽量。

## 現状の結合点（裏取り済み）

`OriginalFormatPanel` は既に DI コールバック（`downloader` / `get_url` / `get_cookies` / `update_status`、original_format_panel.py:467）で疎結合化されている。`app.py` との結合経路:

| 種別 | 経路 |
|---|---|
| 表示制御 | `_on_format_changed`（setVisible + resize、app.py:588） |
| 高さ同期 | `on_size_hint_changed` → `_resync_splitter_to_top_hint`（app.py:466,567） |
| 追加時読み出し | `get_snapshot` / `has_formats_loaded` / `get_fetched_title`（app.py:629,637） |
| 入力検証 | `get_audio_only` / `is_audio_skipped` / `is_both_skipped`（app.py:622-628） |
| 編集モード | `restore_from_settings` + `trigger_fetch`（app.py:778,789） |
| リセット | `reset`（app.py:645,713,845） |
| 多言語 | `retranslate`（app.py:299,461） |

## 撤去できるもの

- `_WIN_H_EXPANDED`(700) と `_on_format_changed` 内の resize 分岐 → メイン高さ固定。
- `_resync_splitter_to_top_hint`（app.py:567-586）と `_PanelSignals.size_hint_changed` / `on_size_hint_changed` → 高さ同期機構を丸ごと撤去。ニコグループの `updateGeometry()` ハックも不要。
- `App` 側のパネル永続参照・retranslate 再配線。`App` が保持するのは「ダイアログを開くファクトリ」と `add_requested` / `edit_applied` / `edit_cancelled` の受け口のみ。
- **メインの `QSplitter`（上段/キューの高さ比調整）**: 上段がパネル分離で固定高になったため存在意義を失い撤去。`QVBoxLayout` でキュー領域に伸縮 stretch を与える単純構成に置換。`size_hint_changed` の消費先はダイアログの `adjustSize()`。

## docs 更新対象

- 改訂: `docs/spec/screens/original-format-panel.md` / `docs/spec/screens/main-window.md` / `docs/arch/app.md` / `docs/arch/original_format_panel.md` / `docs/spec/index.md` / `docs/arch/index.md`
- 新規: `docs/spec/screens/original-format-dialog.md` / `docs/arch/original_format_dialog.md`

## 進捗

- [x] 設計検討（方式・課題1〜3 の方針確定）
- [x] Issue 起票（#61）・task doc 作成
- [x] docs（spec / arch）先行更新（dialog spec/arch 新規 + main-window / panel / app の改訂 + 目次）
- [x] テスト先書き（`test_original_format_dialog.py` 11 ケース / `test_app.py` にボタン表示・高さ固定・URL ガード 4 ケース追加）
- [x] 実装（`OriginalFormatDialog` 新設・`app.py` 改修・i18n キー `btn_open_detail` / `btn_add_to_queue` 追加）
- [x] lint / format / mypy / pytest（132 passed）
- [ ] PR 作成・レビュー・マージ
