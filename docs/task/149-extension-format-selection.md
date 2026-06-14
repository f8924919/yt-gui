# 149 ブラウザ拡張のポップアップで形式選択（案A）

対応 Issue: #149

## 目的

ブラウザ拡張から動画を送る際に形式を選べるようにする。コンテナはアプリ側グローバル設定で拡張から知り得ないため、**案A**を採用：拡張はコンテナ非依存ラベルで「意味（kind＋params）」のみ送り、形式解決はアプリ側に一任する。

## 決定事項（ユーザー確認済み）

- 露出する形式: `最高画質` / `解像度指定`（480/720/1080/1440/2160）/ `音声のみ`（mp3・flac、mp3 はビットレート 128/192/256/320）/ `アプリの既定を使う`。
- 拡張ラベルにコンテナ名を焼き込まない（実コンテナはアプリ設定に従う）。
- オリジナル形式は拡張に出さない（別タスク）。
- メインボタンの既定動作は**前回選択を記憶**（`chrome.storage`）。初回既定は `アプリの既定を使う`。
- 音声の `audio_format`(mp3/flac) / `mp3_bitrate` は拡張で選べる＝アイテム単位の上書きとして適用。
- プロトコル `format` は構造化オブジェクト `{kind, resolution?, audio_format?, mp3_bitrate?}`。
- アプリ側は受信 format を信頼せず許可 enum へクランプ。未知/欠落は既定へフォールバック。

## 設計メモ

### プロトコル

`POST /enqueue` の `format`（任意）:

```json
{ "kind": "best | resolution | audio | app_default",
  "resolution": "1080",        // kind=resolution のみ
  "audio_format": "mp3|flac",  // kind=audio のみ
  "mp3_bitrate": "192" }       // kind=audio かつ mp3 のみ
```

- `format` 欠落・`app_default`・不正 → アプリ既定形式（現行 MVP 挙動）。
- container は **送らない**（アプリ設定に従う）。

### 形式解決（Qt 非依存・純関数）

`formats.py` に `resolve_extension_format(fmt, *, default_resolution, default_audio_format, default_mp3_bitrate) -> ResolvedExtensionFormat | None` を新設。

- 返り値: `format_id` と実効 `resolution` / `audio_format` / `mp3_bitrate`（許可 enum へクランプ済み）。
- `None` を返したら「アプリ既定形式を使う」を意味する（`app_default` / 欠落 / 未知 kind）。
- `test_formats.py` で単体テスト（クランプ・フォールバック・未知 kind）。

### 接続ポイント

- `extension_server.py:84-88` `handle_request`: `format` を `str` 前提から `dict`（or 欠落）に変更。dict 以外は `400 invalid_format`。`on_enqueue(url, cookies, fmt: dict|None)`。
- `app.py:1164-1183` `_on_extension_enqueue`: `resolve_extension_format` を呼び、結果が `None` なら従来 `_extension_default_format()`、そうでなければ `dataclasses.replace(settings, ...)` で実効 settings を作って `build_job_spec(format_id, eff_settings)`。`fmt_original` は拡張から来ない（kind に存在しない）。
- 合流点 `_start_add_thread`（`app.py:861`）は不変。

### 拡張 UI

- `manifest.json` の `action` に `default_popup` 追加。**注意**: popup を付けると `chrome.action.onClicked`（`background.js:21`）は発火しなくなるため、送信トリガを popup の送信ボタンへ移す。
- 真のワンクリック即送信は**右クリックメニュー「yt-gui に送る」**で維持（記憶済み形式で送信）。
- 形式ラベルは `_locales`（ja/en）で多言語化。

## 進捗

- [x] Issue 起票（#149）・ブランチ作成・investigate
- [x] docs 先行更新
- [x] テスト先行（test_formats / test_extension_server / test_extension）
- [x] 実装 → green（351 passed・ruff・mypy・format OK）
- [x] verify-gate（verify green / docs-check PASS / evaluator PASS）
- [ ] PR
