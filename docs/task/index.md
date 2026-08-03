# タスク一覧

**進行中・未着手**のタスクを管理します。タスク追加・状態変更時にこのファイルを更新してください。
完了したタスクは [docs-guide.md](../docs-guide.md) §4.2 の手順で [archive/](archive/index.md) へ移動します（下の表からは削除）。

> **このファイルは短く保つ。** セッション開始時に毎回読み込まれる（[SessionStart hook](../../.claude/hooks/session_task_status.py) が下記 2 つの表を自動で注入する。[git-workflow.md](../git-workflow.md) §5.6）ため、**「今なにが残っているか」だけ**を置きます。完了タスクの経緯・判断の理由・着手時の申し送りは [archive/index.md](archive/index.md) の「完了タスクの経緯・申し送り」へ書きます。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）

## タスク

タスクメモ（`docs/task/{slug}.md`）を持つ進行中・未着手のタスク。

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [284-pin-update-pr-ci.md](284-pin-update-pr-ci.md) | 進行中 | ピン更新 PR で必須 CI が発火しない問題を fine-grained PAT で解消（#284） | 2026-08-04 |

<!-- タスク追加時の記入例:
| [task-slug.md](task-slug.md) | 未着手 | 1 行サマリ | YYYY-MM-DD |
-->

## 起票済み・未着手の Issue

タスクメモをまだ作っていない（着手時に作る）未着手の Issue。

| Issue | 概要 | 着手時に読むもの |
|---|---|---|
| [#39](https://github.com/f8924919/yt-gui/issues/39) | 配布バイナリのコード署名・公証（Windows Authenticode / macOS 公証） | [build.md](../build.md) |
| [#84](https://github.com/f8924919/yt-gui/issues/84) | 区間ダウンロード: ネイティブ `download_ranges` 経路のハング解消（通信量節約版）の検討 | [archive/81-download-sections.md](archive/81-download-sections.md) |
