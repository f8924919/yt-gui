# #164 ブラウザ拡張の UI を Chrome 風（Material 3）デザインへ刷新

- Issue: [#164](https://github.com/f8924919/yt-gui/issues/164)
- ステータス: 進行中
- 関連 spec: [browser-extension.md](../spec/features/browser-extension.md#ui-デザインポップアップオプション画面)

## 目的

拡張のポップアップ（`popup.html`）と設定画面（`options.html`）を、最小限のインラインスタイルから **Material 3（現行 Chrome 風）** のデザインへ刷新する。Chromium 系ブラウザにネイティブに馴染ませ、別アプリ感をなくす。

## 決定事項

- デザイン言語: Material 3（GM3）。アクセント `#0b57d0`、主ボタンはピル型。
- ダークモード: `prefers-color-scheme` でブラウザのテーマに自動追従。
- 色・角丸・余白は CSS カスタムプロパティに集約し、`:root` とダーク時で値だけ差し替える。
- スタイルは各 HTML の `<style>` 内に閉じる（外部 CSS ファイルは追加しない）。

## 非破壊の制約

既存 JS が参照する DOM を壊さないこと。

- `id`: `kind` / `resolution` / `audio_format` / `mp3_bitrate` / `send`（popup）、`token` / `port` / `save` / `status`（options）
- `.hidden`（サブ選択行の表示切替）
- `data-i18n` / `data-i18n-placeholder`（多言語差し替え）

## 作業ログ

- spec に「UI デザイン」節を追加。
- `popup.html` / `options.html` のスタイルを Material 3 化（ライト/ダーク両対応）。
