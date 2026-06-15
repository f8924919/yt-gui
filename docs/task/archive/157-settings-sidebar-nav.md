# 設定ダイアログのサイドバー型ナビゲーション化

対応 Issue: [#157](https://github.com/f8924919/yt-gui/issues/157)

## 背景

macOS で設定ダイアログ上部の `QTabWidget` のタブが窮屈に潰れる。Windows はタブ溢れ時に `<` `>` スクロールボタンが出るが、macOS ネイティブスタイルは矢印を出さずタブを圧縮・省略表示するため。タブは現在 7 項目あり、固定幅 520px では収まりきらないのが根因。改善案A（左サイドバー型ナビゲーション）で恒久対応する。

## 設計方針

- 上部横並び `QTabWidget` を廃止し、左サイドバー（`QListWidget`）＋右ページ（`QStackedWidget`）のラッパー `_SidebarNav(QWidget)` に置換する。
- ラッパーは整数インデックス API（`addTab` / `currentIndex` / `setCurrentIndex` / `widget` / `count`）を公開し、`self._tabs` がこれを保持する。既存コードの `_template_tab_index` / `_proxy_tab_index` と保存時のページ切替（`_save`）を改変せず動かす。
- 固定サイズはサイドバー幅分を加えて `setFixedSize(700, 520)`（高さは据え置き、コンテンツ幅を現状同等に維持）。
- ナビ項目ラベルは既存ロケールキー `tab_*` を流用（ja/en 双方に既存）。

## 対象ファイル

- `yt_gui/settings_dialog.py`
- `tests/test_settings_dialog.py`
- `docs/spec/screens/settings-dialog.md` / `docs/arch/settings_dialog.md`

## 進捗

- [x] docs 先行更新（spec / arch）
- [ ] テスト先行（サイドバー構造・ページ切替の検証）
- [ ] 実装 → green
- [ ] 検証ゲート（verify / docs-check / evaluator）
- [ ] PR

## 補足

- macOS 実機での最終的な描画確認は別途ユーザー側で必要（Linux サンドボックスでは macOS ネイティブ描画を再現できない）。
