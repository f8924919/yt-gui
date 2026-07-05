# アプリ本体の更新チェック＋通知（アプリ更新 Phase A）

対応 Issue: [#198](https://github.com/f8924919/yt-gui/issues/198)

## 目的

アプリ本体（yt-gui）の新版リリースに気づけるよう、起動時自動チェック＋通知
（オプトアウト可）と、バージョン情報ダイアログからの手動チェックを追加する。

## 設計判断（確定済み）

- 起動時自動チェック＋オプトアウト設定（既定オン）。頻度制御なし（毎起動 1 回）。
- 新版検出時のみメインウィンドウ表示後に `QMessageBox` 通知。失敗・最新はサイレント。
- UI はバージョン情報ダイアログに「yt-gui の更新を確認」ボタンを別ボタンとして追加。
- 照会・解析は新規 `yt_gui/app_update.py`（`yt_dlp_update.py` と同型の純関数）。
  比較は `yt_dlp_update.compare_versions` / `UpdateStatus` を再利用。
- Phase B（実体更新）はスコープ外。方式調査は
  [docs/research/app-update.md](../research/app-update.md) に記録済み。

## 進捗

- [x] Issue 起票・受け入れ条件確定（criteria-review 反映済み）
- [x] docs 先行: [spec/features/app-update.md](../spec/features/app-update.md) /
      [arch/app_update.md](../arch/app_update.md) /
      [research/app-update.md](../research/app-update.md) / 各 index・設定 spec
- [ ] 設計レビュー（design-review・§5.5 発火）
- [ ] テスト先行（`tests/test_app_update.py`）
- [ ] 実装 → green
- [ ] verify-gate → PR
