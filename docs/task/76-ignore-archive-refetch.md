# #76 ダウンロードアーカイブ: アイテム単位で「アーカイブを無視して再取得」

- GitHub Issue: [#76](https://github.com/f8924919/yt-gui/issues/76)
- ブランチ: `feature/76-ignore-archive-refetch`
- ステータス: 進行中

## 目的

ダウンロードアーカイブ（#75）は動画 ID 単位・フォーマット非依存で記録するため、720p 取得済みの動画を
1080p で取り直す等ができない。アイテム単位で「今回だけアーカイブを無視して取得する」手段を提供する。

## 設計

per-item の実行設定 `JobSpec.ignore_archive: bool`（既定 `False`）を追加する（`section_*` と同じ流儀）。

`job.ignore_archive` が True のとき:

1. `downloader._build_ydl_opts`: `download_archive` opt を**渡さない** → yt-dlp の内部スキップが起きず再取得される。
2. `downloader._resolve_unique_path`: `in_download_archive` チェックを**スキップ** → `DownloadSkipped` を送出しない。

### 再記録の扱い（確定）

**既存記録を保持・再記録しない**（ユーザー確定）。`download_archive` opt を外すだけなので、

- 既にアーカイブ済みの記録はそのまま残る（削除しない）。
- 今回の DL は記録されない。
- 次回（フラグ無し）の通常 DL では既存記録により再びスキップされる。

→ `ignore_archive` は**一回限りの上書き**。yt-dlp は `download_archive` を渡すと記録済み動画を内部で
スキップする（だから既存の手動 `in_download_archive` チェックがある）ため、再取得には opt を外すしかなく、
結果として「skip も record もしない」が最もシンプルで整合する。

### UI（確定）

- キュー右クリックメニューに「アーカイブを無視して再取得」を追加。
  - 活性条件: アーカイブ有効（`settings.download_archive_enabled`）× 選択に `waiting` がある × 非編集モード。
  - 対象は `waiting` アイテムの部分集合（編集メニューと同じ `_edit_targets`）。
- ツールチップに「アーカイブ無視: 有効」を 1 行追加（フラグが立っているアイテムのみ）。
- ステータスは `waiting` のまま（新ステータスは作らない）。ログにマーク件数を出す。

### 既知の制限

- フラグ設定後に「形式を変更」で編集すると、`build_job_spec` で `JobSpec` が再生成され `ignore_archive` は
  `False` に戻る（編集フォームに該当 UI が無いため）。再取得したい場合は編集後にメニューを再実行する。spec に明記する。

## 影響ファイル

| 層 | ファイル | 変更 |
|---|---|---|
| DTO | `yt_gui/job_spec.py` | `JobSpec.ignore_archive` フィールド追加 |
| DL | `yt_gui/downloader.py` | `_build_ydl_opts` / `_resolve_unique_path` で `ignore_archive` 分岐 |
| 制御 | `yt_gui/queue_controller.py` | `mark_ignore_archive(items)` 追加 |
| UI | `yt_gui/app.py` | `_QueueTree` にメニュー項目・シグナル・ツールチップ行・配線 |
| i18n | `yt_gui/locales/ja.py` / `en.py` | メニュー・ツールチップ・ログ文言 |
| docs | spec: download-behavior / queue / main-window、arch: job_spec / downloader / queue_controller / app | 仕様反映 |
| test | test_downloader / test_job_spec / test_queue_controller | ケース追加 |

## 受け入れ条件（Issue 由来）

- [x] 待機中キューアイテムに対し、アーカイブを無視して再取得する操作を提供する。
- [x] 当該操作を選んだアイテムは archive 照合・スキップの対象外になる。
- [x] 再記録の有無の挙動を spec に明記する（= 再記録しない・既存記録は保持）。
