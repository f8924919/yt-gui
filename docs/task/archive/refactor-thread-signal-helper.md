# リファクタリング フェーズ 4: バックグラウンドスレッド共通ヘルパ

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §F](../research/refactoring-analysis.md)
> ブランチ: `refactor/thread-signal-helper`

## 背景

`threading.Thread(target=..., daemon=True).start()` + `_PanelSignals` / `_AppSignals` で `finish` / `done` / `failed` を emit するパターンが 3 箇所で再実装されている。

| 箇所 | 用途 |
|---|---|
| `App._start_add_thread` / `_run_fetch_for_add` | 追加時のタイトル取得 |
| `App._start_thumbnail_fetch` / `_run_thumbnail_fetch` | サムネイル取得 |
| `OriginalFormatPanel._start_fetch_thread` / `_run_fetch` | フォーマット取得 |

各々が「ボタン disable → 状態文言更新 → 例外時はメッセージ + status update → finally で再 enable」を独自に書いている。

## ゴール

- 共通ヘルパ `run_in_thread(work, *, on_done, on_failed, on_finished)` を 1 箇所に集約
- 3 箇所のスレッド起動部を共通ヘルパ呼び出しに置換
- 振る舞いは不変、特に例外伝搬と finally の順序

## 着手手順

### ステップ 1: ヘルパ設計

`yt_gui/threading_utils.py`（新規）に以下を実装。

```python
def run_in_thread(
    work: Callable[[], T],
    *,
    on_done: Callable[[T], None],
    on_failed: Callable[[BaseException], None],
    on_finished: Callable[[], None] | None = None,
    parent: QObject | None = None,
) -> None:
    """ワーカースレッドで work() を実行。

    結果はメインスレッドの on_done/on_failed/on_finished にキューイングされる。
    on_failed は work() 内で発生した例外を受ける。
    on_finished は成功・失敗どちらの場合も最後に呼ばれる。
    """
```

実装は内部で `QObject` + `Signal` 一式を生成し、`parent` がある場合は親に紐付けてライフサイクルを管理。

### ステップ 2: 既存 3 箇所の置換

#### `App._start_add_thread` / `_run_fetch_for_add`

```python
run_in_thread(
    lambda: self.downloader.fetch_title(url),
    on_done=self._on_fetch_for_add_done,
    on_failed=self._on_fetch_for_add_failed,
    on_finished=lambda: self._set_add_buttons_enabled(True),
)
```

#### `App._start_thumbnail_fetch` / `_run_thumbnail_fetch`

フェーズ 2 で `ThumbnailCache` に移動済みであれば、そのクラス内で `run_in_thread` を呼ぶ。

#### `OriginalFormatPanel._start_fetch_thread` / `_run_fetch`

同様に置換。`_PanelSignals` の `fetch_*` シグナル定義は撤廃。

### ステップ 3: シグナル定義の整理

- `_AppSignals` / `_PanelSignals` から「3 箇所のスレッド処理用」のシグナルを削除
- 別目的（例: queue progress, status emit）のシグナルは残す
- `docs/arch/app.md` のシグナル表からも該当行を削除

## ドキュメント更新

- `docs/arch/index.md` — `threading_utils` モジュールを追記
- `docs/arch/threading_utils.md`（新規）
- `docs/arch/app.md` — `_AppSignals` 表の更新、スレッド処理の標準パターンを記述
- `docs/arch/original_format_panel.md` — `_PanelSignals` 表の更新

## 範囲外

- `App._worker`（キュー走行スレッド）— 長時間ループなのでヘルパ対象外
- danmaku2ass / ffmpeg のサブプロセス起動 — `Downloader` 内部で完結しており別パターン

## ステータス

完了 (2026-05-26)
