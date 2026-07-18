# #276 自己更新（Phase B）の撤去

- Issue: [#276](https://github.com/f8924919/yt-gui/issues/276)（撤去範囲・参照判定範囲・受け入れ条件の正本）
- ブランチ: `feature/276-remove-self-update`
- 経緯の記録: [research/app-update.md](../research/app-update.md) 「Phase B の撤去（2026-07-18・#276）」/ spec の撤去記録節

## 主要判断

| 論点 | 判断 |
|---|---|
| `_create_app_update_box` | `(box, open_btn)` の 2 値へ簡素化。`test_app_update_box_*` は Phase A 表示テストへ改修して残し、`open_btn` → `openUrl` の回帰テストを追加 |
| 参照の判定範囲 | 生きた参照（yt_gui/・tests/・spec/・arch/・ビルド設定）のみ。research と task archive の歴史的言及は意図的に保持 |
| 依存 | `uv remove sigstore`（tuf / rfc3161-client も lock から消えること）。yt-gui.spec の collect_all 群を撤去 |
| 残骸 | `.update-staging` / `.bak` の自動掃除は撤去。リリースノートで手動削除を案内 |

## 進捗

- [x] Issue 起票・受け入れ条件の具体化（criteria-review 指摘反映: arch/app.md 追加・フィクスチャ明記・openUrl 回帰・ビルド検証手段の具体化・参照範囲の明文化）
- [x] docs 先行（spec Phase B 節の撤去記録化・arch/self_update.md 削除・arch/app.md・arch/index.md・testing/policy.md・research 追記）
- [x] design-review（指摘反映: yt-gui.spec の `_hidden_imports` 初期化行を残す・`collect_all` import 整理・research のデッドリンクをテキスト化・research/index に撤去注記。リリースノートは「旧版から手動 DL 必要」＋残骸削除案内の両方を記載）
- [x] テスト先行（box 2 値化＋openUrl 回帰＋Close 非遷移の 3 件・red 確認済み）
- [x] 実装 → green（506 passed・ruff/mypy クリーン・生きた参照ゼロを grep 確認）
- [x] ローカル PyInstaller ビルド確認（sigstore/tuf/rfc3161 の混入 0 件・exe 正常・dist 617MB）
- [ ] verify-gate
- [ ] PR

## マージ後の後処理

- #275（TUF symlink）・#274（失敗通知出し分け）を撤去により不要としてクローズ
- リリース（バージョンは要相談）とリリースノートに残骸の手動削除案内
