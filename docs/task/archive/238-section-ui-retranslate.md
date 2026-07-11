# 区間ダウンロード UI の言語切替即時反映漏れの修正

対応 Issue: [#238](https://github.com/f8924919/yt-gui/issues/238)

## 概要

表示言語を変更しても「区間を指定してダウンロード」関連 UI の文言が再起動まで切り替わらないバグを修正する。原因は `App._retranslate_ui()`（手動列挙方式）に `_build_section_widget()` のウィジェット群が未登録であること。

## 実装方針

1. `_build_section_widget()` 内の匿名 `QLabel` 3 つ（開始 / 終了 / チャプター名正規表現）をインスタンス属性に昇格する。
2. `_retranslate_ui()` に以下 7 ウィジェットの `setText(t(...))` を追加する。
   - `_section_check`（`section_enable`）
   - `_section_mode_time`（`section_mode_time`）
   - `_section_mode_chapter`（`section_mode_chapter`）
   - 開始ラベル（`section_start`）
   - 終了ラベル（`section_end`）
   - チャプター名正規表現ラベル（`section_chapter_pattern`）
   - `_section_keyframe_check`（`section_force_keyframes`）
3. `_section_start` / `_section_end` の placeholder は言語非依存（時刻フォーマット例示）のため対象外。

## テスト方針

- 言語切替（`set_language` → `_retranslate_ui()`）後、7 ウィジェットの表示文字列が切替先ロケールの `STRINGS` 対応値と一致することを個別に assert する（テキスト一致まで検証）。

## 進捗メモ

- 2026-07-11: 調査完了・Issue #238 起票・docs 先行（arch/app.md へ再翻訳の手動列挙方式と区間 UI の登録を追記）。
- 2026-07-11: テスト先行（`test_retranslate_ui_updates_section_widgets`）→ 実装（ラベル 3 つの属性昇格＋ `_retranslate_ui()` へ 7 ウィジェット登録）。lint / format / mypy / 全テスト green。
