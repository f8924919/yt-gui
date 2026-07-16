# アプリ更新 Phase B-1: 更新アーカイブの取得と attestation 検証（コア・PoC）

- **対応 Issue**: [#252](https://github.com/f8924919/yt-gui/issues/252)
- **ブランチ**: `feature/252-self-update-core`
- **設計の正本**: [research/app-update.md](../research/app-update.md) の「追加調査と方式決定（2026-07-16）」「設計詳細」（Phase B 全体設計は design-review 済み）
- **後続**: Phase B-2 = [#253](https://github.com/f8924919/yt-gui/issues/253)（Windows 差し替え＋UI。本タスクの完了が前提）

## 目的

Phase B（実体自動更新）の第一段として、非破壊のコア（DL → attestation 検証 → 展開）を `yt_gui/self_update.py` に UI 非依存で実装し、方式の成否を左右する不確実性（sigstore-python の PyInstaller 同梱可否・オフライン検証可否）を PoC として潰す。

## PoC 計測・記録欄（Issue の成果物）

| 項目 | 結果 |
|---|---|
| sigstore 同梱後のバンドルサイズ増 | （未計測） |
| 完全オフライン検証（Rekor 非接続）の成立可否 | （未確認） |
| 実リリースアセットでの E2E 検証手順 | （未実施） |

## 進捗メモ

- 2026-07-16: タスク開始。investigate（実装レベルの内部接続点）＋外部調査（sigstore-python API・オフライン検証・PyInstaller 同梱）を並行実施。
- 2026-07-16: criteria-review 実施。指摘（失敗表現の明確化・PoC 判定基準・zip slip テスト・通信異常系・ref 記録・一時ファイル後始末）を採用し Issue #252 本文を改訂。ユーザー判断 2 点（サイズ増は記録のみ・失敗は正規化した結果型で返す）を確定。
- 2026-07-16: sigstore-python 調査結果（sigstore 4.4.0 / `verify_dsse`＋subject digest 突合が必須 / ref はタグ完全一致ピン / トラストルートは年数回ローテーション→オンライン既定）を設計へ反映。design-review は investigate 推奨 no（Phase B 全体設計レビュー済み）につきスキップ。
- 2026-07-16: docs 先行完了（arch/self_update.md 新設・arch/index.md・testing/policy.md・research メモの検証モデル修正）。テスト先行へ。
