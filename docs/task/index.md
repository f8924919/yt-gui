# タスク一覧

`docs/task/` 配下のタスクの進捗を管理します。タスク追加・完了時にはこのファイルを更新してください。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）
- **完了** : 対応済み

## 進行中・未着手のタスク

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [original_format_panel 排他ロジックのテスト](original-format-panel-tests.md) | 進行中 | #22 / `_AudioListWidget` の AUTO/SKIP/音声 ID 排他を検証 | 2026-05-30 |
| [App 周辺 UI ロジックのテスト](app-ui-logic-tests.md) | 進行中 | #23 / `_QueueTree._edit_targets` の編集対象判定・`_refresh_format_labels` の言語追従 | 2026-05-30 |
| [#24 GitHub Actions の Node24 対応](https://github.com/f8924919/yt-gui/issues/24) | 未着手 | `test.yml` / `release.yml` のアクションを Node24 対応版へ更新 | 2026-05-30 |

## 完了タスク

完了したタスクは [archive/index.md](archive/index.md) にテーマ別で記録しています。

> **運用**: タスク完了時は `docs/task/{slug}.md` を `docs/task/archive/` へ移動し、上記「進行中・未着手」テーブルから該当行を削除して `archive/index.md` の該当テーマ表に追記してください。
