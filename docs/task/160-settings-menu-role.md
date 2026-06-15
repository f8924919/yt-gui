# 設定メニュー項目の置き場所を macOS で言語非依存にする

対応 Issue: [#160](https://github.com/f8924919/yt-gui/issues/160)

## 背景

macOS で設定ダイアログを開くメニュー経路が UI 言語で異なる（日本語: `ファイル → 設定...` / 英語: `yt-gui → Preferences`）。原因は Qt の macOS 自動メニューマージ。`menuRole` 未指定（既定 `TextHeuristicRole`）はアクションのテキストを英語キーワードで判定するため、英語 `Settings...` はアプリメニューへ移動するが日本語 `設定...` は移動せず `ファイル` に残る。

## 設計方針（案A）

`yt_gui/app.py` の `_act_settings` に `setMenuRole(QAction.MenuRole.PreferencesRole)` を明示し、UI 言語によらず macOS では常にアプリメニュー配下に表示する（macOS HIG 慣習に合致）。Windows / Linux はメニューマージ非対象で影響なし。

## 対象ファイル

- `yt_gui/app.py`（`_create_menu` の `_act_settings`）
- `tests/test_app.py`（メニューロール検証テスト）
- `docs/arch/app.md`（メニュー構成の記述）

## 進捗

- [x] docs 先行更新（arch/app.md にメニュー構成節を追加）
- [ ] テスト先行
- [ ] 実装 → green
- [ ] 検証ゲート（verify / docs-check / evaluator）
- [ ] PR

## 補足

- macOS 実機での最終的なメニュー表示確認は別途ユーザー側で必要（Linux サンドボックスでは macOS ネイティブのメニューマージを再現できない）。
