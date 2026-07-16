# アプリ更新 Phase B-1: 更新アーカイブの取得と attestation 検証（コア・PoC）

- **対応 Issue**: [#252](https://github.com/f8924919/yt-gui/issues/252)
- **ブランチ**: `feature/252-self-update-core`
- **設計の正本**: [research/app-update.md](../research/app-update.md) の「追加調査と方式決定（2026-07-16）」「設計詳細」（Phase B 全体設計は design-review 済み）
- **後続**: Phase B-2 = [#253](https://github.com/f8924919/yt-gui/issues/253)（Windows 差し替え＋UI。本タスクの完了が前提）

## 目的

Phase B（実体自動更新）の第一段として、非破壊のコア（DL → attestation 検証 → 展開）を `yt_gui/self_update.py` に UI 非依存で実装し、方式の成否を左右する不確実性（sigstore-python の PyInstaller 同梱可否・オフライン検証可否）を PoC として潰す。

## PoC 計測・記録欄（Issue の成果物・2026-07-16 実施）

| 項目 | 結果 |
|---|---|
| sigstore 同梱ビルド | **成立**。`yt-gui.spec` に `collect_all('sigstore'/'tuf'/'rfc3161_client')`＋`copy_metadata('sigstore')` を追加して `uv run pyinstaller yt-gui.spec` が成功。同一収集設定のコンソール PoC バンドルでバンドル内検証（オンライン/オフライン）とも SUCCESS |
| sigstore 同梱後のバンドルサイズ増 | **非圧縮 約 21.4 MB**（v0.5.0 リリース実体とのファイル単位差分で sigstore 依存ツリー起因分のみを抽出。内訳上位: cryptography 9.5 / rfc3161_client 5.7 / pydantic_core 5.0 MB。配布 zip 225 MB に対し 10% 未満。記録のみ・中断トリガー外） |
| 完全オフライン検証（Rekor / TUF 非接続）の成立可否 | **成立**。`Verifier.production(offline=True)` は TUF キャッシュを退避した新規マシン相当でも、`collect_all('sigstore')` で同梱される埋め込みトラストルートにより検証成功。採用構成は「通常オンライン（既定）」のままとし、オフラインフォールバックの実装は不要と確認 |
| 実リリースアセットでの E2E 検証 | **成立**。手順は下記 |

### E2E 手動確認手順（実リリース v0.5.0・開発環境）

1. `download_and_verify_update("0.4.0", work_dir)` を実行（current を旧版に偽装して新版扱いにする）→ `SUCCESS`、`work_dir/yt-gui-0.5.0-new/` に展開、zip は残らないことを確認。
2. 実 zip を 1 バイト改変 → sha256 が変わり attestations API が **HTTP 404** → `NO_ATTESTATION`（fail-closed）を確認。
3. identity を改変（`release.yml` → `evil.yml`）した `policy.Identity` では sigstore が `VerificationError` で拒否することを確認。
4. `Verifier.production(offline=True)` で同一バンドルの検証が成功（digest 一致含む）することを確認。

副産物: 実 attestation の証明書 SAN は `.../release.yml@refs/heads/main`（release.yml が main push 起動でタグを同一実行内に作るため、タグ ref ではない）。identity ピンを `refs/heads/main` 固定へ修正した。

## 進捗メモ

- 2026-07-16: タスク開始。investigate（実装レベルの内部接続点）＋外部調査（sigstore-python API・オフライン検証・PyInstaller 同梱）を並行実施。
- 2026-07-16: criteria-review 実施。指摘（失敗表現の明確化・PoC 判定基準・zip slip テスト・通信異常系・ref 記録・一時ファイル後始末）を採用し Issue #252 本文を改訂。ユーザー判断 2 点（サイズ増は記録のみ・失敗は正規化した結果型で返す）を確定。
- 2026-07-16: sigstore-python 調査結果（sigstore 4.4.0 / `verify_dsse`＋subject digest 突合が必須 / ref はタグ完全一致ピン / トラストルートは年数回ローテーション→オンライン既定）を設計へ反映。design-review は investigate 推奨 no（Phase B 全体設計レビュー済み）につきスキップ。
- 2026-07-16: docs 先行完了（arch/self_update.md 新設・arch/index.md・testing/policy.md・research メモの検証モデル修正）。テスト先行へ。
- 2026-07-16: テスト先行（30 ケース）→ コア実装 green（sigstore==4.4.0 追加）。
- 2026-07-16: PoC 実施（上記の表）。実 attestation の SAN が `refs/heads/main` と判明し、identity ピンをタグ動的生成から固定文字列へ修正（コード・docs・Issue 反映）。全 PoC 成立、Issue へ結果コメント済み。
