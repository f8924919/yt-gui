# アプリ更新 Phase B-2: Windows 実体更新の適用（差し替え・UI）

- Issue: [#253](https://github.com/f8924919/yt-gui/issues/253)（受け入れ条件の正本）
- 前提: Phase B-1 = [#252](https://github.com/f8924919/yt-gui/issues/252)（PR #255・マージ済み）
- ブランチ: `feature/253-self-update-apply`
- 関連 docs: [spec/features/app-update.md](../spec/features/app-update.md) Phase B 節 / [arch/self_update.md](../arch/self_update.md) / [arch/app.md](../arch/app.md)

## 設計判断（2026-07-17・ユーザー確認済み）

| 論点 | 決定 |
|---|---|
| 差し替えスクリプトの実装方式 | **PowerShell（.ps1）生成**。`powershell.exe -NoProfile -ExecutionPolicy Bypass -File` で起動。GPO で ExecutionPolicy を強制する企業環境は既知の制限として割り切る |
| ロールバックのテスト担保 | **自動テスト必須**。生成した実スクリプトを temp ディレクトリで実行し、失敗段階を parametrize（Windows 限定・skipif）。手動手順による代替は不可 |
| `.bak` 削除の「正常起動」定義 | **メインウィンドウ表示後**に削除（簡易ヘルスチェック。起動直後クラッシュ時は `.bak` が残り手動復旧可能）。削除失敗はサイレント持ち越し |
| 多重起動 | **対象外と明記**（既知の制限）。rename 失敗 → リトライ → ロールバックで fail-closed に落ち、インストールは壊れない |

criteria-review の指摘反映（2026-07-17）: 受け入れ条件を分割・fail-closed の明示条件化・PID 待機タイムアウト・二重失敗時の挙動・進捗ダイアログのモーダル化を Issue 本文へ反映済み。

design-review の指摘反映（2026-07-17）:

- プロセス完全終了が差し替えの前提（ワーカーは daemon スレッド・非デーモンスレッドを終了経路に持ち込まない）を arch に明記。
- PowerShell へのパス埋め込みはシングルクォートリテラル＋`'`→`''` 二重化でエスケープ（特殊文字パスのテストを追加）。
- 起動時掃除を `.bak` に加え `{name}.update-staging` の無条件削除へ拡張（`cleanup_leftovers`）。
- スクリプト起動（Popen）失敗時はアプリを終了せず「更新失敗」通知へ戻す。
- finished(SUCCESS) ハンドラでキャンセル状態を再確認してから適用に踏み切る。
- ロールバック成功時は復旧した旧 exe を再起動（バージョン不変が実質的な失敗通知。無通知のまま消えない）。
- PID 待機はプロセス名照合を併用（PID 再利用の誤検知対策）。
- スクリプト自体のクラッシュ窓（.bak 退避後・新配置前）は既知の制限として spec に明記（`.bak` から手動復旧可能）。

## 進捗

- [x] investigate / criteria-review / Issue 本文改訂
- [x] docs 先行（spec Phase B 節・arch self_update / app）
- [x] design-review（§5.5 発火: 新 API・新画面・外部プロセス連携）→ 指摘を docs へ反映
- [x] テスト先行（test_self_update.py へ B-2 追記・test_app.py へ UI テスト追記）
- [x] 実装 → green（569 passed・ruff / mypy クリーン）
- [ ] verify-gate（verify / docs-check / evaluator）
- [ ] Windows 実機 E2E（下記手順を実施・結果を記録）
- [ ] PR

## E2E 手動確認手順（正常系・実施後に結果を記録）

1. 旧バージョンの release zip（例 v0.5.0）を展開し、ユーザー書き込み可能な
   フォルダ（例 `%USERPROFILE%\apps\yt-gui`）へ配置する（開発 venv 外の
   実インストール状態）。
2. `yt-gui.exe` を起動 → 起動時チェックの新版検出ダイアログに
   「更新して再起動」が表示されることを確認。
3. 押下 → 進捗ダイアログで DL・検証が進み、完了後アプリが終了 →
   自動で新バージョンが起動することを確認。
4. `{フォルダ名}.bak` が親ディレクトリに残っていること、新プロセスの
   メインウィンドウ表示後（数秒以内）に削除されることを確認。
5. バージョン情報ダイアログで新バージョンになっていることを確認。

（失敗系・ロールバック・タイムアウト・二重失敗は自動テストで担保。Issue 参照）

### 実施結果

（未実施）
