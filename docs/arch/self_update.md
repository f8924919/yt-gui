# self_update — アプリ本体の実体更新コア（Phase B-1）

> 関連仕様: [アプリ本体（yt-gui）の更新チェック・通知](../spec/features/app-update.md)（Phase B 節は B-2 実装時に追加）

アプリ本体（yt-gui）の実体自動更新（Phase B）のコア（ダウンロード＋attestation
検証＋展開）の実装意図・接続点をまとめる。方式決定の経緯・設計原則の正本は
[research/app-update.md](../research/app-update.md) の「追加調査と方式決定
（2026-07-16）」。実装 Issue は
[#252](https://github.com/f8924919/yt-gui/issues/252)（B-1: 本モジュール）/
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
     `attestations[].bundle` にバンドル JSON 埋め込み・複数返り得る）で
     バンドルを取得する。
   - sigstore-python の **`Verifier.verify_dsse(bundle, policy)`** で検証する
     （attest-build-provenance は DSSE / in-toto 形式のため。
     `verify_artifact` は hashedrekord 用で使えない）。
   - **`verify_dsse` は subject digest とアセットの照合を行わない**ため、
     返却された in-toto Statement の `subject[].digest.sha256` と自算出
     digest の一致確認を必ず自前で行う。複数 attestation は 1 件ずつ検証し、
     ポリシー通過＋digest 一致が 1 件あれば成功（「digest で API 照会して
     存在すれば OK」という循環は禁止）。
   - ポリシーは `policy.Identity` で **identity =
     `https://github.com/f8924919/yt-gui/.github/workflows/release.yml@refs/tags/v{version}`
     （対象バージョンのタグに完全一致）・issuer =
     `https://token.actions.githubusercontent.com`** を厳格にピンする。
   - Verifier は通常 `Verifier.production()`（オンライン TUF 更新。実体更新は
     どのみちオンライン時にしか行えない）。同梱トラストルート＋
     `offline=True` の成立性は PoC で確認し、採用構成は research メモに記録。
5. **展開**: 検証済み zip をアプリ内（同一プロセス）で展開する。
   **zip slip / 絶対パスエントリ対策**として、全エントリの展開先が指定
   ディレクトリ配下に収まることを確認してから展開する。展開後の差し替え
   （rename・ロールバック）は B-2 のスクリプトが担う。

## テストの注入点

- HTTP（Releases API・attestations API・アセット DL）は `fetch` 相当の
  引数差し替え（[app_update.md](app_update.md) と同方針）。
- sigstore 検証は Verifier / 検証関数を差し替え可能な引数として設計する
  （「有効な署名だが identity 不一致」等の失敗系は fetch 差し替えだけでは
  構成できないため）。
- すべてオフラインで単体テスト可能にする（[testing/policy.md](../testing/policy.md)）。

## 接続点

| 要素 | 接続点・責務 |
|---|---|
| 現行バージョン | 既存 `yt_gui.get_version()`（[entry.md](entry.md)） |
| 単調性比較 | `yt_dlp_update.compare_versions()` / `UpdateStatus` を再利用（利用者 3 件目。中立モジュールへの切り出しは見送り、B-2 完了後に再評価） |
| 更新チェック（Phase A） | [app_update.md](app_update.md)。B-2 で「新版あり」ダイアログから本モジュールの DL → 検証 → 展開を呼ぶ |
| UI・スレッド | B-2 で `app.py` に進捗シグナル付きワーカーを新設（`run_in_thread` は進捗を持たないため流用しない） |
| PyInstaller 同梱 | `yt-gui.spec` に sigstore のトラストルート data files・`copy_metadata('sigstore')`・`rfc3161_client`（Rust 拡張）等の収集を追加（PoC で確定） |

## 既存コードへの影響範囲

| ファイル | 影響 |
|---|---|
| `yt_gui/self_update.py` | **新規**。アセット解決・DL（進捗/キャンセル）・attestation 検証・安全展開の純関数群と結果型 |
| `yt_gui/yt_dlp_update.py` | 変更なし（`compare_versions` / `UpdateStatus` を提供） |
| `yt_gui/app_update.py` | 変更なし（B-2 で UI 接続時に連携） |
| `pyproject.toml` | `sigstore==`（バージョン完全固定）を追加。従属（`rfc3161-client` 等）は sigstore 側のピンに従わせ重ねてピンしない |
| `yt-gui.spec` | sigstore / tuf / rfc3161_client の data・native 収集、`copy_metadata('sigstore')` |
| `tests/` | 新規テスト（fetch / 検証関数差し替えによるオフライン単体テスト） |
