# #262 self-update: attestations API の bundle_url 化への追従

- Issue: [#262](https://github.com/f8924919/yt-gui/issues/262)（背景・実測仕様・失敗種別マッピング・受け入れ条件の正本）
- ブランチ: `bugfix/262-attestation-bundle-url`
- 設計の正本: [arch/self_update.md](../arch/self_update.md) 検証モデル（バンドル解決 2 経路・snappy デコーダ・失敗種別マッピング）/ 経緯: [research/app-update.md](../research/app-update.md) 「GitHub attestations API の破壊的変更（2026-07-18）」

## 主要判断

| 論点 | 判断 |
|---|---|
| snappy 展開手段 | 純 Python の private デコーダを `self_update.py` 内に実装（案 A）。依存追加なし・展開のみ・非圧縮長 10 MB 上限 |
| 失敗種別 | 新 Enum 追加なし。bundle_url GET 失敗（全滅時）→ `NETWORK_ERROR`、展開/パース失敗・両方 null（全滅時）→ `VERIFICATION_FAILED`（Issue の表が正本） |
| 実アセット確認 | 受け入れ条件から分離し、修正版での `download_and_verify_update` ヘッドレス駆動を手動確認として本メモに記録 |
| design-review | §5.5 トリガ非該当（新モジュール・複数モジュール横断・依存追加いずれもなし）のため省略（investigate 推奨 no） |

## 進捗

- [x] Issue 起票・受け入れ条件の具体化（criteria-review 指摘反映）
- [x] docs 先行（arch/self_update.md・research/app-update.md）
- [x] テスト先行（test_self_update.py: バンドル解決 7 系・snappy デコーダ 16 件。実 v0.6.1 応答のフィクスチャ `tests/data/attestation_bundle_v061.snappy` を追加）
- [x] 実装 → green（79 passed）
- [ ] verify-gate
- [x] 手動確認（実 v0.6.1 アセットへのヘッドレス駆動）と結果記録
- [ ] PR

## 手動確認の結果（2026-07-18 実施）

修正版の `download_and_verify_update("0.6.0", staging)` を実 API・実 sigstore
検証で実行し **SUCCESS**（8.9 秒）。DL → attestations API 照会（bundle null）→
`bundle_url` GET → snappy 展開 → `Verifier.verify_dsse` → subject digest 照合 →
ステージング展開（`yt-gui.exe` 存在確認）まで本番同等経路で成立。
修正前の同駆動は `VERIFICATION_FAILED`（本 Issue の症状）だったことも確認済み。
