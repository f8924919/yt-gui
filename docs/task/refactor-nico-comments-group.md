# リファクタリング フェーズ 3: `_NicoCommentsGroup` の切り出し

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §E](../research/refactoring-analysis.md)
> ブランチ: `refactor/nico-comments-group`

## 背景

`original_format_panel.py` 1,136 行のうち、ニコニコ動画コメント (ASS / MKV 統合) 関連コードは以下に散在し、計 ~200 行を占める。

| 区分 | 行範囲 |
|---|---|
| ビルド | 340–420 |
| イベント | 615–685 |
| 復元 | 755–773 |
| 翻訳 | 519–526 |
| リセット | 464–474 |

ニコニコ動画コメント機能（フェーズ 1–3, 2026-05-24 完了）として最新追加されたばかりで境界が新鮮なため、`_NicoCommentsGroup` という子 `QGroupBox` サブクラスにまとめやすい。

## ゴール

- `_NicoCommentsGroup`（仮）を `original_format_panel.py` 内、または `yt_gui/original_format/nico_comments_group.py`（新ファイル）として切り出す
- `OriginalFormatPanel` 本体は本来の映像 / 音声 / 字幕の議論に集中できる構造にする
- 振る舞いは変更しない（表示・復元・翻訳・リセットがすべて従来通り）

## 着手手順

### ステップ 1: 切り出し先の決定

選択肢:

- (a) `original_format_panel.py` 内に `_NicoCommentsGroup(QGroupBox)` クラスを追加（モジュール内分離のみ）
- (b) `yt_gui/original_format/` サブパッケージを新設し、`nico_comments_group.py` を分割

→ **まず (a) で実施**。将来 `original_format_panel.py` 全体の構造化が必要になった時点で (b) に格上げを検討。

### ステップ 2: API 定義

`_NicoCommentsGroup` に以下を持たせる。

- `setVisible(bool)` — ニコニコ URL 検出時のみ表示
- `reset()` — リセット時呼び出し
- `retranslate()` — `set_language()` 時呼び出し
- `get_state() -> dict` — 復元用 snapshot
- `restore_from(state: dict)` — 編集モード復元
- シグナル: `state_changed` — 親パネルの dirty 判定用

### ステップ 3: 親パネルとの配線

- `OriginalFormatPanel.__init__` でインスタンス化、レイアウトに追加
- `retranslate_ui()` / `reset()` / `restore_from_settings()` / `get_raw_settings()` から子グループへ委譲
- `_video_combo` の選択変更などのイベントは親側で握ったまま、子への通知が必要な場合のみ signal/method 経由で渡す

## ドキュメント更新

- `docs/arch/original_format_panel.md` — `_NicoCommentsGroup` の責務と委譲経路を追記
- `docs/spec/screens/original-format-panel.md` — 構造変更なしのため更新不要（振る舞い不変）

## 範囲外

- 字幕リスト全体の切り出し — 本フェーズではニコニコグループのみ
- 映像 / 音声グループの切り出し — 必要性が確認できないため対象外

## ステータス

完了 (2026-05-26)
