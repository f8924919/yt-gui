# リファクタリング フェーズ 5: コンボの sentinel 化 + AUTO/SKIP オフセットの隠蔽

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §G, §H](../research/refactoring-analysis.md)
> ブランチ: `refactor/combo-sentinel`

## 背景

### G. 翻訳済み文字列を比較キーに使っている

`original_format_panel.py` で以下のような比較が **8 箇所以上**ある。

```python
if self._video_combo.currentText() == t("orig_auto"):
    ...
```

該当行: 538, 602, 691-697, 793-798, 859-884, 935-938 など。

`set_language()` 直後にユーザー操作が走ると比較が一時的にズレ得るし、新言語追加時に「auto」「skip」のサロゲートを切らさない要件が暗黙化している。

### H. AUTO/SKIP オフセット `±2` の散在

`_AudioListWidget` の物理行 (AUTO=0, SKIP=1, audio=2+) を呼び出し側が直接知っている。

| 箇所 | コード |
|---|---|
| `original_format_panel.py:730` | `audio_idx = row - 2` |
| `original_format_panel.py:880` | `setCurrentIndex(i + 2)` |
| `original_format_panel.py:899` | `rows.append(i + 2)` |
| `original_format_panel.py:1012` | `return idx - 2` |

`_AudioListWidget` の内部表現が呼び出し側に漏れている。

## ゴール

- コンボ判定を `userData` の sentinel 値 (`"__auto__"`, `"__skip__"`) 経由に変更
- `_AudioListWidget` に `audio_row(i: int) -> int` / `audio_index_from_row(row: int) -> int | None` を生やし、`±2` のリテラルをコード中から除去
- 翻訳済み文字列と論理状態の完全分離

## 着手手順

### ステップ 1: sentinel 定数の定義

`original_format_panel.py` 冒頭に定数を定義。

```python
_AUTO_SENTINEL = "__auto__"
_SKIP_SENTINEL = "__skip__"
```

### ステップ 2: コンボ生成時に `setItemData` で sentinel をセット

```python
self._video_combo.addItem(t("orig_auto"), _AUTO_SENTINEL)
self._video_combo.addItem(t("orig_skip"), _SKIP_SENTINEL)
# 以降は format ID を userData にセット
for fmt in video_formats:
    self._video_combo.addItem(label, fmt["format_id"])
```

### ステップ 3: 比較を `currentData()` ベースに変更

```python
# Before
if self._video_combo.currentText() == t("orig_auto"):

# After
if self._video_combo.currentData() == _AUTO_SENTINEL:
```

該当 8 箇所以上をすべて更新。`set_language()` 時の再構築でも `userData` を維持する。

### ステップ 4: `_AudioListWidget` のオフセット隠蔽

`_AudioListWidget` クラスに以下を追加。

```python
AUTO_ROW = 0
SKIP_ROW = 1
_AUDIO_OFFSET = 2

def audio_row(self, audio_index: int) -> int:
    return audio_index + self._AUDIO_OFFSET

def audio_index_from_row(self, row: int) -> int | None:
    if row < self._AUDIO_OFFSET:
        return None
    return row - self._AUDIO_OFFSET

def is_meta_row(self, row: int) -> bool:
    return row < self._AUDIO_OFFSET
```

呼び出し側 4 箇所（730, 880, 899, 1012）を新 API 経由に置換。リテラル `2` を削除。

### ステップ 5: 翻訳キー追加時の挙動確認

`set_language()` 後にも sentinel が維持されることを確認。新言語追加時、「auto」「skip」の表示文字列のみを訳せばよく、ロジック側の変更不要になる。

## ドキュメント更新

- `docs/arch/original_format_panel.md` — sentinel 設計と `_AudioListWidget` の公開 API を反映
- `docs/spec/i18n.md` — 「論理状態は sentinel、表示文字列は翻訳キー」の方針を 1 段落追記（任意）

## 範囲外

- 他のコンボ（`format_combo` など）の sentinel 化 — 既に format ID ベースのため対象外
- i18n システム全体の再設計 — 表示文字列 ↔ 論理キーの分離が必要なケースが他に出てきた時点で別タスク化

## ステータス

未着手
