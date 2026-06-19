# 拡張機能からオリジナル形式で送るとキュー表示が「最高画質」になる

対応 Issue: #175

## 背景

ブラウザ拡張から `kind: "original"` で送ると、内部的には `fmt_original` で正しく DL されるのに、キューの「形式」列が「最高画質」と表示される。

## 原因

`yt_gui/app.py` `_build_original_job()`（app.py:929）が表示ラベルをメイン画面の形式コンボの現在表示文字列（`self.format_combo.currentText()`）から取得している。

- アプリ内フロー（追加 `_on_dialog_add_requested` / 編集 `_on_dialog_edit_applied`）はダイアログを開く前提でコンボが `fmt_original` にセット済みのため、`currentText()` が「オリジナルの形式」を返し正しい。
- 拡張フロー（`_on_extension_dialog_add`）はコンボを操作しないため、既定 `fmt_best_mp4`（=「最高画質」）のままラベル採用されてしまう。

`_build_original_job` は常に `build_job_spec(_ORIGINAL_KEY, ...)`（app.py:933-934）でオリジナル形式の JobSpec を組むため、コンボ参照は本質的に不要な偶発的結合。

## 確定した設計判断（ユーザー確認済み）

- `_build_original_job` のラベル基点を `self.format_combo.currentText()` から
  **`self._format_display[FORMAT_KEYS.index(_ORIGINAL_KEY)]`（= 常に「オリジナルの形式」）** に固定する。
- アプリ内追加・編集フローは現状コンボが `fmt_original` のため同値となり、リグレッションなし。
  拡張フローのみ表示が「最高画質」→「オリジナルの形式」へ修正される。
- `audio_only` 時のサフィックス（`→ MP3/FLAC`）結合は基点文字列のみ差し替えるため挙動不変。

## 実装方針

### yt_gui/app.py
- `_build_original_job()` 内の `format_label = self.format_combo.currentText()` を
  `format_label = self._format_display[FORMAT_KEYS.index(_ORIGINAL_KEY)]` に変更。

### tests/test_app.py
- 拡張オリジナルフロー（`_on_extension_dialog_add` 経由）で、コンボが `fmt_best_mp4` のままでも
  キューアイテムのラベルが「オリジナルの形式」になることを検証する回帰テストを追加。

### docs
- `docs/spec/features/browser-extension.md`: オリジナル形式ダイアログ確定時、キューの形式列に
  「オリジナルの形式」ラベルを表示する旨を明記。
- `docs/arch/app.md`: `_build_original_job` のラベルはオリジナル形式表示ラベルに固定する旨を明記。
