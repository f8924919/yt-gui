# タスク一覧

`docs/task/` 配下のタスクの進捗を管理します。タスク追加・完了時にはこのファイルを更新してください。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）
- **完了** : 対応済み

## 進行中・未着手のタスク

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [268-progress-dialog-cancel](268-progress-dialog-cancel.md) | 進行中 | self-update: 進捗ダイアログ close() の canceled 発火で適用がサイレント放棄されるバグの修正（[#268](https://github.com/f8924919/yt-gui/issues/268)）。完了後 v0.6.4 で実 GUI E2E 再検証 | 2026-07-18 |

## 完了タスク

完了したタスクは [archive/index.md](archive/index.md) にテーマ別で記録しています。

> **運用**: タスク完了時は `docs/task/{slug}.md` を `docs/task/archive/` へ移動し、上記「進行中・未着手」テーブルから該当行を削除して `archive/index.md` の該当テーマ表に追記してください。この移動は**原則タスクを完結させる実装 PR に同梱**します（[docs-guide.md](../docs-guide.md) §4.2）。
