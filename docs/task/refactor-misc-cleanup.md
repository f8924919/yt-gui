# リファクタリング フェーズ 7: 小規模クリーンアップ

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §K, §L](../research/refactoring-analysis.md)
> ブランチ: `refactor/misc-cleanup`

## 背景

調査メモで低優先度に分類された 2 件のクリーンアップ。フェーズ 1–6 で構造が整った後の仕上げとして実施する。

### K. `_QueueTree._is_editing` / `_get_*_cb` の素朴な属性差し込み

`app.py:512-515` で外から 4 つのコールバックを直接代入している。

```python
self._queue_tree._get_item_cb = self._get_item
self._queue_tree._get_state_cb = self._get_state
# ...
```

Qt のシグナル/スロットで揃えれば一貫する。

> ※ フェーズ 2 ([refactor-app-split.md](refactor-app-split.md)) で `QueueController` 切り出し時に一部対応されている場合は、残った差分のみ片付ける。

### L. `App._open_settings` の重複ロジック

`app.py:1385-1416` で「言語が変わった時」と「変わらなかった時」の `format_combo` / `original_panel.retranslate` の再構築を二度書きしている (`_retranslate_ui` 側と部分重複)。

## ゴール

- `_QueueTree` のコールバック差し込みをシグナル/スロット経由に統一
- `_open_settings` の重複ロジックを `_retranslate_ui` 等の既存メソッドに集約

## 着手手順

### ステップ 1: `_QueueTree` のシグナル化

- `_QueueTree` に必要なシグナル（例: `state_requested`, `item_state_requested`）を定義
- 既存のコールバック属性差し込みを削除
- `App.__init__` または `_wire_signals()` でシグナル接続

### ステップ 2: `_open_settings` の整理

- 言語変更時の処理を `_apply_language_change()` 等のヘルパに抽出
- 設定変更後の共通処理（`format_combo` 再構築等）も別ヘルパに分離
- `_open_settings` 本体は「ダイアログ表示 → 結果に応じてヘルパ呼び出し」の薄い構造に

## ドキュメント更新

- `docs/arch/app.md` — `_QueueTree` 連携がシグナル化された旨を反映
- 必要に応じて `docs/arch/index.md` の関連リンクを更新

## 範囲外

- `_QueueTree` 自体の責務分割 — 現状の規模では不要
- 設定変更時の他の重複ロジック — フェーズ 2 (`QueueController`) で吸収済みの想定

## ステータス

未着手
