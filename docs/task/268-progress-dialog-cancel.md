# #268 self-update: 進捗ダイアログ close() の canceled 発火で適用がサイレント放棄される

- Issue: [#268](https://github.com/f8924919/yt-gui/issues/268)（原因の実証・修正方針・受け入れ条件の正本）
- ブランチ: `bugfix/268-progress-dialog-cancel`
- 設計の正本: [arch/self_update.md](../arch/self_update.md) UI 接続節の設計注意（#268）

## 主要判断

| 論点 | 判断 |
|---|---|
| 修正 | `was_cancelled` を close 前に評価＋`dialog.canceled.disconnect()` してから close（防御の重複） |
| テスト | `_start_self_update()` 経由の実ダイアログ配線に統一。既存 6 件の `dialog=None` 直呼びテストを実配線へ更新（並存させない）。monkeypatch は `self.close()` / `launch_replace_script` / `download_and_verify_update` 等のみで `dialog.close()` は実物 |
| investigate | 省略（主エージェントが原因行の特定＋最小再現で実証済み。CLAUDE.md の軽い確認の範囲） |
| design-review | §5.5 トリガ非該当（単一モジュール・新規経路なし）のため省略 |

## 進捗

- [x] Issue 起票・受け入れ条件の具体化（criteria-review 指摘反映: close の対象明確化・後段失敗 2 分岐の追加・キャンセル 2 経路の分離・既存テスト更新の明記）
- [x] docs 先行（arch/self_update.md に設計注意を追記）
- [x] テスト先行（既存 6 件を `_start_self_update()` 経由の実配線へ更新＋実キャンセル競合を再現。red で成功経路・失敗通知 3 分岐の 4 件がバグを検出することを確認）
- [x] 実装 → green（`was_cancelled` を close 前に評価＋`canceled.disconnect()`。600 passed・ruff/mypy クリーン）
- [x] verify-gate（verify green 600 passed / docs-check pass / evaluator PASS）
- [ ] 実 GUI E2E 再検証（0.6.2 → 0.6.4 を想定・結果を記録）
- [x] PR（#269）

## 実 GUI E2E の結果（実施後に記録）

（未実施）
