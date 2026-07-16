# アプリ本体更新 Phase B: 方式設計の確定（調査タスク）

- **対応 Issue**: なし（docs のみの調査タスク）。成果として実装 Issue [#252](https://github.com/f8924919/yt-gui/issues/252)（Phase B-1: コア・PoC）/ [#253](https://github.com/f8924919/yt-gui/issues/253)（Phase B-2: Windows 差し替え・UI）を起票
- **ブランチ**: `docs/app-update-phase-b-design`
- **起点**: [research/app-update.md](../../research/app-update.md)（Phase B 未決。tufup 第一候補）・[spec/features/app-update.md](../../spec/features/app-update.md) の Phase B 節予約

## 目的

アプリ本体（yt-gui）の実体自動更新（Phase B）について、実装 Issue を起票できる水準まで方式設計を確定する。成果物は research メモの更新（設計判断の記録）と実装 Issue の起票。

## 検討事項（残課題の整理）

1. **ホスティング方式の確定**（先決・最大の課題）
   - GitHub Pages（メタデータのみ・容量約 1GB 制限）vs 固定タグのローリングリリース（`releases/download/updates/`）
   - 差分更新（bsdiff パッチ）アセットの蓄積と削除ポリシー、飛び級更新時のパッチチェーン
2. **鍵管理・署名運用**
   - root 鍵のオフライン保管手順（保管・バックアップ・リカバリ）
   - online 鍵（targets/snapshot/timestamp）の CI Secrets 運用・ローテーション・失効手順
   - メタデータ有効期限と**定期再署名 workflow**（リリースが無い期間の timestamp 再署名）
3. **CI（release.yml）への組み込み**
   - tufup ターゲット（tar.gz）＋メタデータ生成・署名ステップの挿入位置（既存 zip と共存）
   - 初回ブートストラップ（`root.json` のアプリ同梱）とアップデータ入り初リリースの段取り
   - provenance attestation の対象に tufup ターゲットを含めるか
4. **クライアント側の更新フロー・UX**
   - 照会先の一本化（Phase A の GitHub Releases API vs TUF メタデータ）
   - 通知 → ダウンロード進捗 → 再起動適用の UI 仕様、失敗時ロールバック、設定の粒度
   - Windows 実行中 exe の差し替え・macOS `.app`（未署名・Gatekeeper）での成立性 → PoC 前提
5. **プラットフォームスコープ**
   - Linux（AppImage）は Phase A 据え置きの正式決定（必要時に AppImageUpdate を別検討）
   - Velopack 再評価トリガ（コード署名 #39 着手時）の明文化

## 進捗メモ

- 2026-07-16: タスク起票。investigate（内部接続点）＋外部調査（tufup 実挙動・ホスティング/鍵運用）を並行実施。
- 2026-07-16: 調査完了。tufup は運用コスト（timestamp=1 日既定の失効リスク・cron 再署名常時運用・オフライン鍵管理・macOS 非対応）から棄却し、**自前アップデータ（Releases ＋ Sigstore attestation 検証）・Windows のみ先行・手動適用のみ**をユーザー確認のうえ決定。詳細は [research/app-update.md](../../research/app-update.md) の「追加調査と方式決定（2026-07-16）」。
- 2026-07-16: design-review（§5.5 該当: 新モジュール・複数モジュール横断・方式候補複数）を実施。指摘（DL 実バイト検証・fail-closed・同一ボリューム staging・PID 待ち・進捗/キャンセル機構・sigstore のトラストルート失効・yt-gui.spec 変更の見込み・Issue 分割）を research メモ「設計詳細」へ反映。UX/スコープ 3 点（Issue 2 分割・キュー実行中は無効化・書き込み不可時は手動 DL フォールバック）はユーザー確認のうえ決定。
- 2026-07-16: 実装 Issue #252（Phase B-1: DL＋attestation 検証＋sigstore 同梱 PoC）・#253（Phase B-2: Windows 差し替え＋UI、#252 完了が前提）を起票し、本調査タスク完了。
