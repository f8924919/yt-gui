# 151 拡張からオリジナル形式を指定した際にアプリ側ダイアログを開く導線

対応 Issue: #151

## 目的

[#149](archive/149-extension-format-selection.md)（PR #150）で拡張ポップアップから形式選択（最高画質 / 解像度指定 / 音声のみ / アプリ既定）に対応した。オリジナル形式（映像/音声/字幕トラックの個別選択）はトラックプローブ→対話選択が必要で軽量サーフェスに不適のため**スコープ外**としていた。

本タスクでは「拡張からオリジナル形式を指定したい」ユースケースを、**アプリ側で `OriginalFormatDialog` を開く導線**として実装する。拡張は「アプリで詰める」意図（`kind: "original"`）だけを送り、トラック選択はアプリの既存ダイアログで行う。

## 決定事項（ユーザー確認済み）

- **トリガ**: 拡張の `format` 構造化オブジェクトに `kind: "original"` を追加（#149 プロトコルと前方互換）。
- **キャンセル時**: キューに追加しない（「アプリで詰める」意図なのでキャンセル＝中止が自然）。
- **複数 URL 連続送信**: 内部 pending キューに積み、1 件ずつダイアログを直列表示（多重モーダル防止）。
- **拡張 UI**: popup / 右クリックメニューに「オリジナル形式（アプリで選択）」を追加する。
- **ウィンドウフォーカス**: 送信を機に前面化する（`showNormal()` + `raise_()` + `activateWindow()`）。
- **Cookies**: 拡張由来のアイテム単位 Cookies を、ダイアログのプローブと確定後ダウンロード双方に適用する。

## 設計メモ

### プロトコル

`POST /enqueue` の `format` に `kind: "original"` を追加（#149 の `best | resolution | audio | app_default` に加える）。

```json
{ "kind": "original" }
```

- 追加パラメータは持たない（トラック選択はアプリ側ダイアログで行うため）。
- 未知 kind は従来どおりアプリ既定へフォールバック → 前方互換を維持。

### 形式解決（Qt 非依存）

`formats.resolve_extension_format` の返り値を **3 状態**へ拡張する。

- `None` … アプリ既定形式を使う（従来。`app_default` / 欠落 / 未知 kind）。
- `ResolvedExtensionFormat`（dict 相当）… 即適用（従来。best / resolution / audio）。
- `OriginalIntent`（センチネル）… **アプリ側ダイアログ起動が必要**（新規。`kind == "original"`）。

`test_formats.py` で `original` → `OriginalIntent` を返すこと、未知 kind との区別を単体テスト。

### 接続ポイント

- `extension_server.py` `handle_request`: `format` dict を透過する現状を維持（`kind` の中身検証はアプリ側に一任）。必要なら受理 kind の説明コメントのみ更新。
- `app.py` `_on_extension_enqueue`: `resolve_extension_format` が `OriginalIntent` を返したら、`(url, item_cookies_path)` を**内部 pending キュー**へ積む。現状の `_extension_default_format()` の `fmt_original` → `fmt_best_mp4` 退避ロジック（`app.py:1220` 付近）はこの経路に置き換え。
- pending ディスパッチャ（メインスレッド）: キューから 1 件取り出し →
  1. メインウィンドウ前面化（`showNormal()` + `raise_()` + `activateWindow()`）。
  2. `_make_original_dialog` を `get_url=lambda: url` / `get_cookies=拡張 Cookies を返すラムダ` を注入して生成。
  3. `exec()` で起動。確定（`add_requested`）→ キュー追加（`item_cookies_path` 適用）。キャンセル → 何もしない。
  4. ダイアログが閉じたら次を処理。
- `exec()` をスロット内で直接呼ぶとイベントループがネストするため、ディスパッチは `QTimer.singleShot(0, ...)` 等でスロットを抜けた後に起動する。
- 一時 Cookies ファイルのライフサイクル（プローブ中に消えない）に注意。

### 拡張 UI

- popup / 右クリックメニューに「オリジナル形式（アプリで選択）」を追加し、`{ "kind": "original" }` を送信する。
- 形式ラベルは `_locales`（ja/en）で多言語化。

## 進捗

- [x] Issue 確認（#151）・ブランチ作成・investigate
- [x] docs 先行更新（browser-extension.md スコープ外→正式仕様化 / app.md / formats.md / extension_server.md / original-format-dialog.md / extension/README.md）
- [x] テスト先行（test_formats / test_app / test_extension）
- [x] 実装 → green（359 passed・ruff・mypy・format(yt_gui) OK）
- [ ] verify-gate（verify / docs-check / evaluator）
- [ ] PR
