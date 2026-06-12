# リファクタリング フェーズ 2: `App` クラスの分割

[← タスク一覧](index.md) / [← 全体計画](refactor-overview.md)

> 対応候補: [refactoring-analysis.md §D](../../research/refactoring-analysis.md)
> ブランチ: `refactor/app-split`
> 前提: フェーズ 1 ([refactor-job-spec.md](refactor-job-spec.md)) 完了

## 背景

`app.py` の `App` クラスは 1,447 行 / 30 メソッド超で、以下の 6 責務を一手に持っている。

1. ウィジェット生成・レイアウト (`_create_widgets`, `_create_menu`)
2. キュー管理・ワーカースレッド (`_start_queue`, `_worker`, `_remove_selected`)
3. サムネイルキャッシュ（HTTP 取得スレッド・dict + Lock）
4. 編集モード状態機械 (`_enter_edit_mode`, `_apply_edit`, `_cancel_edit`, `_exit_edit_mode`)
5. 形式 ↔ パネル可視性 (`_on_format_changed`, `_build_format_display`)
6. ログ管理・ステータス送出・設定リロード

このうち少なくとも 2 つは独立した責務として切り出せる。

## ゴール

- `ThumbnailCache` を独立クラス（pure / UI 非依存）として切り出す
- `QueueController` を独立クラスとして切り出し、「キュー走行・ワーカースレッド・編集モード状態機械」をまとめる
- `App` クラスは「ウィジェット組み立てとシグナル配線」に責務を絞る

## 着手手順

### ステップ 1: `ThumbnailCache` の切り出し

`yt_gui/thumbnail_cache.py`（新規）を作成。

- 既存の `App` 内 dict + `Lock` + HTTP 取得スレッドをそのまま移植
- 公開 API: `get(url) -> QPixmap | None`, `request(url, callback)` (取得完了時にメインスレッドへ deliver)
- Signal は `ThumbnailCache` 内に閉じ込め、`App` は `cache.thumbnail_ready.connect(...)` でつなぐだけ
- 既存のキャッシュキーポリシー（URL or video_id）と LRU 上限（あれば）は現状維持

### ステップ 2: `QueueController` の切り出し

`yt_gui/queue_controller.py`（新規）を作成。

- 責務: キュー走行 (`_worker`), 編集モード状態機械 (`_enter_edit_mode` 系), `_QueueItem` のライフサイクル管理
- 依存: `Downloader`, `Settings`, `_QueueTree` ウィジェット参照（または signal で疎結合化を検討）
- シグナル: `item_status_changed`, `item_progress`, `edit_mode_entered`, `edit_mode_exited`, `queue_finished`
- `_QueueTree._is_editing` / `_get_*_cb` の素朴な属性差し込み (`app.py:512-515`) もここに引き取り、シグナル/スロットで再配線（候補 K に隣接）

### ステップ 3: `App` のスリム化

- 切り出した 2 クラスのインスタンスを `App.__init__` で生成
- シグナル配線を `_wire_signals()` ヘルパに分離
- 削除されたメソッドが他箇所から参照されていないか grep で確認

## ドキュメント更新

- `docs/arch/index.md` — `thumbnail_cache`, `queue_controller` を追記
- `docs/arch/thumbnail_cache.md`（新規）
- `docs/arch/queue_controller.md`（新規）
- `docs/arch/app.md` — 責務記述を「ウィジェット組み立てとシグナル配線」に絞り、移譲先を明記
- `docs/testing/policy.md` — 新モジュールのテスト対象/対象外を記載

## 範囲外

- 「形式 ↔ パネル可視性」(`_on_format_changed`) の切り出し — `App` 本体の役割の一部として残す
- ログ管理の切り出し — `LogDialog` 側に既に独立しているため対象外
- 設定リロード処理の切り出し — `Settings` 側に集約済みで対象外

## ステータス

完了 (2026-05-25)
