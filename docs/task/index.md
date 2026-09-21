# タスク一覧

**進行中・未着手**のタスクを管理します。タスク追加・状態変更時にこのファイルを更新してください。
完了したタスクは [docs-guide.md](../docs-guide.md) §4.2 の手順で [archive/](archive/index.md) へ移動します（下の表からは削除）。

> **このファイルは短く保つ。** セッション開始時に毎回読み込まれる（[SessionStart hook](../../.claude/hooks/session_task_status.py) が下記 2 つの表と、`進行中` のタスクメモの申し送り・未完了項目を自動で注入する。[git-workflow.md](../git-workflow.md) §5.6。メモ側の見出し規約は [docs-guide.md](../docs-guide.md) §3.2）ため、**「今なにが残っているか」だけ**を置きます。完了タスクの経緯・判断の理由・着手時の申し送りは [archive/index.md](archive/index.md) の「完了タスクの経緯・申し送り」へ書きます。

## ステータス凡例

- **未着手** : 着手前
- **進行中** : 作業中（中断含む）

## タスク

タスクメモ（`docs/task/{slug}.md`）を持つ進行中・未着手のタスク。

| タスク | ステータス | 概要 | 更新日 |
|---|---|---|---|
| [333-template-backport.md](333-template-backport.md) | 進行中 | claude-templates の更新（上流 #82〜#99）から docs 3 点を逆輸入 | 2026-09-22 |

<!-- タスク追加時の記入例:
| [task-slug.md](task-slug.md) | 未着手 | 1 行サマリ | YYYY-MM-DD |
-->

## 起票済み・未着手の Issue

タスクメモをまだ作っていない（着手時に作る）未着手の Issue。

| Issue | 概要 | 着手時に読むもの |
|---|---|---|
| [#39](https://github.com/f8924919/yt-gui/issues/39) | 配布バイナリのコード署名・公証（Windows Authenticode / macOS 公証） | [build.md](../build.md) |
| [#84](https://github.com/f8924919/yt-gui/issues/84) | 区間ダウンロード: ネイティブ `download_ranges` 経路のハング解消（通信量節約版）の検討 | [archive/81-download-sections.md](archive/81-download-sections.md) |
| [#334](https://github.com/f8924919/yt-gui/issues/334) | `format_edited_file` hook のフェイルオープン 2 分岐にテストを足す（policy §8.1 A12 の実例） | [policy.md](../testing/policy.md) §8.1 A12 / A2 / A1 |
