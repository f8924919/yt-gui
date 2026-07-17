# self_update — アプリ本体の実体更新（Phase B）

> 関連仕様: [アプリ本体（yt-gui）の更新チェック・通知](../spec/features/app-update.md)（Phase B 節）

アプリ本体（yt-gui）の実体自動更新（Phase B）のコア（ダウンロード＋attestation
検証＋展開 = B-1）と適用（プリフライト・差し替えスクリプト・`.bak` 管理 = B-2）
の実装意図・接続点をまとめる。方式決定の経緯・設計原則の正本は
[research/app-update.md](../research/app-update.md) の「追加調査と方式決定
（2026-07-16）」。実装 Issue は
[#252](https://github.com/f8924919/yt-gui/issues/252)（B-1: コア）/
[#253](https://github.com/f8924919/yt-gui/issues/253)（B-2: Windows 差し替え・UI）。

## 設計方針

- **`app_update.py`（チェック専用・軽依存）とは分離**した新モジュール
  `yt_gui/self_update.py` に、UI 非依存（PySide6 / Qt への import・
  Signal/Slot を含まない）の関数群として実装する。UI・スレッド接続
  （進捗ダイアログ・終了フロー）は B-2 で `app.py` 側に置く。
- **sigstore の import は遅延**させる（関数内 import）。Phase A の起動経路・
  更新チェック経路に sigstore の import コスト・依存を波及させない。
- **fail-closed**: 検証が通るまで一切展開・配置しない。あらゆる失敗
  （通信エラー・タイムアウト・attestation 無し・検証失敗・digest 不一致・
  バージョン単調性違反・キャンセル・zip 不正）は**例外ではなく正規化された
  結果型**（`UpdateStatus` / `UpdateCheckResult` に倣った Enum ＋ frozen
  dataclass。失敗種別を区別可能）で呼び出し元へ返し、例外を漏らさない。
  B-2 の UI は失敗種別で文言を出し分ける。

## 処理フローと検証モデル

1. **アセット解決**: GitHub Releases API のレスポンス `assets[]` から
   Windows 用 zip（`yt-gui-{version}-windows-x64.zip`）の
   `browser_download_url` を解決する（`assets[].name` のマッチで解決。
   命名規則の組み立てハードコードはしない）。
2. **単調性チェック**: 対象バージョンが現行より新しいことを
   `yt_dlp_update.compare_versions()` の再利用で確認する（ロールバック
   攻撃の実用的防御）。
3. **ダウンロード**: 進捗コールバック（累計/総バイト数）を挟みながら
   チャンク受信する。キャンセルは `threading.Event`
   （[downloader.md](downloader.md) の `_cancel_requested` パターン）。
   キャンセル・失敗時は一時ファイルを残さない。
4. **attestation 検証**:
   - DL した zip の**実バイト**から sha256 を算出し、GitHub attestations API
     （`GET /repos/f8924919/yt-gui/attestations/sha256:{digest}`、無認証可・
     複数返り得る）でバンドルを取得する。
   - **バンドルの解決は attestation 1 件ごとに 2 経路**（#262。API version
     2026-03-10 の破壊的変更で `attestations[].bundle` の埋め込みが廃止され、
     `attestations[].bundle_url` 参照へ移行したため。旧 API バージョン指定でも
     旧動作には戻らない）:
     1. `bundle` が dict ならそのまま使う（後方互換）。
     2. `bundle` が null/欠落で `bundle_url` があれば GET する。応答は
        `Content-Type: application/x-snappy` の **raw snappy block format**
        （framing なし）で圧縮されたバンドル JSON（実測 約 11 KB）。先頭
        バイトが JSON でなければ snappy 展開してから `json.loads` し、素の
        JSON ならそのままパースする（将来の仕様変更への耐性）。
   - snappy 展開は**純 Python の private デコーダ**（`self_update.py` 内・
     展開のみ・新規依存なし）で行う。非圧縮長の上限（10 MB）を設け、超過・
     不正 varint・copy オフセット範囲外・宣言長と実出力の不一致はすべて
     不正入力として失敗させる（fail-closed）。
   - バンドル解決の失敗種別マッピング: `bundle` / `bundle_url` 両方 null、
     snappy 展開失敗、JSON パース失敗は当該 attestation をスキップし、全滅
     なら `VERIFICATION_FAILED`。`bundle_url` GET の HTTP エラー・タイム
     アウトも当該 attestation をスキップするが、1 件も検証成功せず
     ネットワーク起因のスキップがあった場合は `NETWORK_ERROR` を返す
     （attestations API 一覧取得自体の 404 → `NO_ATTESTATION` / その他 →
     `NETWORK_ERROR` は従来どおり）。
   - sigstore-python の **`Verifier.verify_dsse(bundle, policy)`** で検証する
     （attest-build-provenance は DSSE / in-toto 形式のため。
     `verify_artifact` は hashedrekord 用で使えない）。
   - **`verify_dsse` は subject digest とアセットの照合を行わない**ため、
     返却された in-toto Statement の `subject[].digest.sha256` と自算出
     digest の一致確認を必ず自前で行う。複数 attestation は 1 件ずつ検証し、
     ポリシー通過＋digest 一致が 1 件あれば成功（「digest で API 照会して
     存在すれば OK」という循環は禁止）。
   - ポリシーは `policy.Identity` で **identity =
     `https://github.com/f8924919/yt-gui/.github/workflows/release.yml@refs/heads/main`
     （完全一致）・issuer = `https://token.actions.githubusercontent.com`**
     を厳格にピンする。`release.yml` は main への push で起動しタグを同一
     実行内で作成するため、証明書 SAN の ref は**タグ ref ではなく
     `refs/heads/main`** になる（実 attestation で確認済み・#252）。
     バージョンとの紐付けは subject digest 照合と単調性チェックが担う。
   - Verifier は `Verifier.production()`（オンライン TUF 更新。実体更新は
     どのみちオンライン時にしか行えない）。同梱トラストルート＋
     `offline=True` でも検証が成立することは PoC で確認済み（TUF キャッシュ
     なしの新規マシン相当で成功）。オフラインフォールバックの実装は不要。
5. **展開**: 検証済み zip をアプリ内（同一プロセス）で展開する。
   **zip slip / 絶対パスエントリ対策**として、全エントリの展開先が指定
   ディレクトリ配下に収まることを確認してから展開する。展開後の差し替え
   （rename・ロールバック）は B-2 のスクリプトが担う。

## 適用（Phase B-2）: プリフライト・差し替え・`.bak` 管理

動作仕様（表示条件・フロー・失敗時挙動・既知の制限）の正本は
[spec/features/app-update.md](../spec/features/app-update.md) の Phase B 節。
ここでは実装 API と設計判断を記す。

### API（すべて UI 非依存・`self_update.py` に追加）

| 関数 | 責務 |
|---|---|
| `get_install_dir()` | frozen（PyInstaller）時に `Path(sys.executable).parent` を返す。非 frozen は `None`（開発環境の無効化を兼ねる） |
| `is_parent_writable(install_dir)` | **親ディレクトリ**への一時ファイル作成・削除で書き込み可否を判定（差し替えは親でのフォルダ rename のため親が判定対象）。`OSError` は `False` |
| `can_self_update(*, platform, current, install_dir)` | 表示条件の集約（Windows・frozen・バージョン解決済み・書き込み可）。判定材料を引数で注入しテスト可能にする |
| `resolve_staging_dir(install_dir)` | `install_dir.parent / f"{install_dir.name}.update-staging"` を返す純関数。呼び出し側は開始時に残骸を削除してから `download_and_verify_update(work_dir=...)` へ渡す |
| `looks_like_app_dir(new_dir, exe_name)` | 展開結果のルート直下に exe があるかの健全性確認（release.yml の zip はルートプレフィックスなし。`Compress-Archive -Path dist/yt-gui/*`） |
| `build_replace_script(...)` | 差し替え PowerShell スクリプトのソースを返す**純関数**（下記） |
| `launch_replace_script(script_text, script_dir)` | スクリプトを対象ツリー外（%TEMP%）へ書き出し、`powershell.exe -NoProfile -ExecutionPolicy Bypass -File` を `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` で起動する（`DETACHED_PROCESS` は排他フラグで PowerShell が即死するため使わない。#253 E2E で検出）。書き出し・起動の失敗は例外を漏らさず失敗として返す（呼び出し側はアプリを終了せず「更新失敗」通知へ戻す） |
| `cleanup_leftovers(install_dir)` | `{name}.bak` と `{name}.update-staging` を `shutil.rmtree(ignore_errors=True)` で削除（`.bak` はヘルスチェックのため次回起動まで残るが、staging は起動時点で常に不要のため無条件削除）。失敗はサイレント持ち越し（起動を妨げない） |

### 差し替えスクリプト（PowerShell）

- 実装方式は **PowerShell（.ps1）生成**（2026-07-17 ユーザー確認済み。バッチは
  構文が脆くロールバックロジックのテスト性が低い。GPO で ExecutionPolicy を
  強制する環境は既知の制限として割り切る）。
- `build_replace_script(*, install_dir, new_dir, pid, exe_relpath,
  wait_timeout_sec, retry_count, retry_initial_ms, show_dialog_on_failure)`
  が全パラメータを埋め込んだソースを返す（`.bak`・ステージングのパスは
  `install_dir` から内部導出し、他所での導出との食い違いを防ぐ）。待機・
  リトライ値を引数化しているのは**テストで短い値を注入して実スクリプトを
  高速実行する**ため。`show_dialog_on_failure=False` は二重失敗テストで
  メッセージボックスがテストをブロックしないための注入点。
- **パス埋め込みのエスケープ**: 埋め込む値（インストール先等）はユーザー環境
  由来でシングルクォート・`$`・バッククォートを含みうる。PowerShell の
  シングルクォートリテラル（`$`・バッククォート非展開）で囲み、`'` は `''` へ
  二重化する。生成内容テストに特殊文字パス（例 `O'Brien`）を含める。
- スクリプトの構造:
  1. PID 消滅待機（`Get-Process -Id` のポーリング＋デッドライン。**PID 再利用の
     誤検知を避けるためプロセス名も併せて照合**し、名前が異なれば消滅扱いと
     する。タイムアウト時はインストール先へ一切触れず終了）。
  2. rename ヘルパ（指数バックオフ: `retry_count` 回・`retry_initial_ms` から
     倍々。AV / OneDrive の一時ロック対策）。
  3. 既存 `.bak` 削除 → 旧 → `.bak` rename → 新 → 旧パス rename。
  4. 失敗時ロールバック（`.bak` → 旧パスへ書き戻し）。ロールバック成功時は
     **復旧した旧 exe を再起動**する（バージョン不変が実質的な失敗通知）。
     二重失敗時は `.bak`・ステージングを残し
     `System.Windows.Forms.MessageBox` で手動復旧を案内
     （`show_dialog_on_failure` で制御）。
  5. 成功時のみ新 exe を起動（起動失敗はロールバックしない・無視）→
     ステージング残骸削除 → スクリプト自己削除（PowerShell はスクリプトを
     読み込み後に実行するため自己削除可能）。
- スクリプトは exit code で結果を返す（0=成功 / 1=タイムアウト /
  2=ロールバック済み失敗 / 3=二重失敗）。実行時に読む消費者はいない
  （アプリは終了済み）が、実行テストが状態と併せて検証する。
- staged バイトの rename 直前の再検証は行わない（検証はプロセス内で完結させ
  スクリプトは rename のみを担う。ステージングへの書き込みはローカル同一権限
  が前提のため、残存 TOCTOU は脅威モデル上許容。research の設計詳細参照）。

### UI 接続（B-2・`app.py` 側）

- 新版検出ダイアログ `_show_app_update_available` に「更新して再起動」を追加
  （表示条件は `can_self_update`、キュー実行中は `queue.is_running` で無効化）。
- ダウンロード〜展開は専用ワーカー（`threading.Thread`）で実行し、進捗・完了は
  `_AppSignals` の新シグナル経由でメインスレッドへ戻す（[app.md](app.md)）。
  進捗 UI はモーダルの `QProgressDialog`（キャンセルで `threading.Event` を
  set。`downloader.py` の中断パターンと同型）。
- 成功時はキャンセル状態を**再確認**したうえで（検証完了とキャンセルの競合
  対策）スクリプト起動 → `close()` でアプリ終了（スクリプト側が PID 消滅を
  待つため、起動→終了の順で競合しない）。スクリプトの起動自体に失敗した
  場合はアプリを終了せず「更新失敗」通知へ戻す。
- 差し替えは**アプリプロセスの完全終了**（実行中 exe のロック解放）が前提。
  非デーモンスレッドの残存はスクリプトの PID 待機タイムアウト（サイレント
  失敗）に直結するため、実体更新ワーカーは daemon スレッドとし、終了経路に
  非デーモンスレッドを持ち込まない。
- 次回起動時の `.bak`・staging 削除（`cleanup_leftovers`）はメインウィンドウ
  表示後に `run_in_thread` でバックグラウンド実行する（簡易ヘルスチェックの
  位置づけ。[spec](../spec/features/app-update.md) 参照）。

## テストの注入点

- HTTP（Releases API・attestations API・bundle_url・アセット DL）は `fetch`
  相当の引数差し替え（[app_update.md](app_update.md) と同方針）。バンドル解決
  の各系（埋め込み / bundle_url + snappy / bundle_url + 素 JSON / 両方 null /
  GET 失敗 / 展開・パース失敗 / 複数 attestation 混在）をオフラインで検証する。
- snappy デコーダは既知ベクタ（literal のみ・copy 含む・複数バイト長
  エンコード）と実 attestation レスポンスを録ったフィクスチャ、および不正
  入力（不正 varint・copy オフセット範囲外・宣言長不一致・長さ上限超過）で
  単体テストする（#262）。
- sigstore 検証は Verifier / 検証関数を差し替え可能な引数として設計する
  （「有効な署名だが identity 不一致」等の失敗系は fetch 差し替えだけでは
  構成できないため）。
- すべてオフラインで単体テスト可能にする（[testing/policy.md](../testing/policy.md)）。
- **差し替えスクリプト（B-2）**は 2 層でテストする:
  1. 生成内容の検証（純関数 `build_replace_script` の出力にパス・PID・
     リトライ設定・自己削除が埋め込まれていること）— 全 OS で実行。
  2. **実行テスト**（生成した実スクリプトを `tmp_path` 上のダミー
     インストール構成で `powershell.exe` 実行し、正常差し替え・失敗段階を
     parametrize したロールバック・タイムアウト・二重失敗を exit code と
     ファイルシステム状態で検証）— Windows 限定（`skipif`）。待機・リトライは
     短い値を注入して高速化し、二重失敗は `show_dialog_on_failure=False` で
     ブロックを防ぐ（2026-07-17 ユーザー確認済み・手動手順による代替は不可）。
- `can_self_update` / `is_parent_writable` は判定材料（platform・バージョン・
  ディレクトリ）を引数注入して境界（書き込み不可・存在しないディレクトリ・
  非 Windows・`"unknown"`）を単体テストする。
- UI 表示条件・キュー実行中の無効化・進捗シグナルの配線は pytest-qt
  （`tests/test_app.py` の既存パターン）で検証する。実プロセスの終了・再起動を
  伴うフル E2E は自動テスト対象外とし、手動手順を task メモに記録する
  （[testing/policy.md](../testing/policy.md) のスコープ方針）。

## 接続点

| 要素 | 接続点・責務 |
|---|---|
| 現行バージョン | 既存 `yt_gui.get_version()`（[entry.md](entry.md)） |
| 単調性比較 | `yt_dlp_update.compare_versions()` / `UpdateStatus` を再利用（利用者 3 件目。中立モジュールへの切り出しは見送り、B-2 完了後に再評価） |
| 更新チェック（Phase A） | [app_update.md](app_update.md)。「新版あり」ダイアログ（`_show_app_update_available`）から本モジュールの DL → 検証 → 展開 → 差し替えを呼ぶ |
| UI・スレッド | `app.py` の進捗シグナル付きワーカー（`run_in_thread` は進捗を持たないため流用しない）。シグナル一覧は [app.md](app.md) |
| キュー実行中判定 | `QueueController.is_running`（[queue_controller.md](queue_controller.md)）で「更新して再起動」を無効化 |
| PyInstaller 同梱 | `yt-gui.spec` で `collect_all('sigstore')` / `collect_all('tuf')` / `collect_all('rfc3161_client')`（埋め込みトラストルート・TUF メタデータ・Rust 拡張の収集）＋`copy_metadata('sigstore')`。サイズ増は非圧縮約 21 MB（PoC 実測・#252） |

## 既存コードへの影響範囲

| ファイル | 影響 |
|---|---|
| `yt_gui/self_update.py` | B-1: アセット解決・DL（進捗/キャンセル）・attestation 検証・安全展開の純関数群と結果型。B-2: プリフライト・差し替えスクリプト生成/起動・`.bak` 削除を追加 |
| `yt_gui/app.py` | B-2: 「更新して再起動」ボタン・進捗ダイアログ・専用ワーカー・終了フロー・起動時 `.bak` 削除 |
| `yt_gui/locales/` | B-2: 翻訳キー追加（全ロケール対称） |
| `yt_gui/yt_dlp_update.py` | 変更なし（`compare_versions` / `UpdateStatus` を提供） |
| `yt_gui/app_update.py` | 変更なし（新版検出ダイアログ側から連携） |
| `pyproject.toml` | `sigstore==`（バージョン完全固定）を追加。従属（`rfc3161-client` 等）は sigstore 側のピンに従わせ重ねてピンしない |
| `yt-gui.spec` | sigstore / tuf / rfc3161_client の data・native 収集、`copy_metadata('sigstore')` |
| `tests/` | 新規テスト（fetch / 検証関数差し替えによるオフライン単体テスト） |
