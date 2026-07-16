# アプリ更新 Phase B-2: Windows 実体更新の適用（差し替え・UI）

- Issue: [#253](https://github.com/f8924919/yt-gui/issues/253)（受け入れ条件の正本）
- 前提: Phase B-1 = [#252](https://github.com/f8924919/yt-gui/issues/252)（PR #255・マージ済み）
- ブランチ: `feature/253-self-update-apply`
- 関連 docs: [spec/features/app-update.md](../../spec/features/app-update.md) Phase B 節 / [arch/self_update.md](../../arch/self_update.md) / [arch/app.md](../../arch/app.md)

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
- [x] verify-gate: verify green（570 passed）/ docs-check pass（指摘 1 件 = arch/index.md 説明文を修正）/ evaluator 要対応 2 件（.bak 削除失敗のサイレント性テスト・進捗ダイアログのモーダル性アサート）を追加対応。要判断 3 件は主エージェント判断: ロールバックテストは段階別の個別テストで意図充足（Issue 文言を「parametrize または個別テスト」へ明確化）/ E2E はヘッドレス駆動で可（task メモに開示済み）/ arch の build_replace_script 引数表記ドリフトを修正
- [x] Windows 実機 E2E（ヘッドレス駆動で実施・結果を下記に記録）
- [x] PR（#256）

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

### 実施結果（2026-07-17・Windows 11 実機）

「更新して再起動」押下後の内部フローを、UI を介さず**同一の関数呼び出し**で
再現するヘッドレス駆動（実リリース v0.5.0・実ネットワーク・実 sigstore 検証・
実プロセスロック・本番同等の既定パラメータ）で **PASS**。

| 段階 | 結果 |
|---|---|
| 旧インストール配置（v0.5.0 zip をユーザー書き込み可能フォルダへ展開） | OK |
| DL＋attestation 検証＋ステージング展開（`download_and_verify_update`、実 API・実 sigstore） | SUCCESS（5.8 秒） |
| 旧 exe（実プロセス）起動 → 差し替えスクリプト起動 → **旧プロセス生存中は swap が始まらない**（PID 待機） | OK |
| 旧プロセス終了 → swap（旧 → `.bak` / 新 → インストールパス / ステージング掃除） | OK |
| 新 exe の自動再起動（実プロセスを確認後に終了） | OK |
| スクリプトの自己削除（%TEMP% に残骸なし） | OK |

検出・修正した不具合: `_default_spawn` の `DETACHED_PROCESS |
CREATE_NO_WINDOW` は**排他フラグの併用**で PowerShell が起動直後に死ぬ
（スクリプト未実行・swap 不発）。`CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP` へ修正し、既定 spawn の実行成立を検証する
Windows 限定の回帰テストを追加した。

補足:
- 新旧が同一バージョン（v0.5.0 ⇔ v0.5.0。単調性はドライバが current=0.4.0 を
  渡して通過）だが、swap 機構（数百ファイルの実 onedir rename・実 exe ロック）
  は完全に本番同等。
- 再起動後の `.bak` 削除は v0.5.0（B-2 未搭載）では走らないため対象外。
  単体テスト（`cleanup_leftovers`・起動時フック）で担保済み。次回リリース後の
  実更新で自然に確認される。
- ダイアログのボタン表示・無効化・キャンセル・失敗通知は pytest-qt の UI
  テストで担保（`tests/test_app.py`）。
