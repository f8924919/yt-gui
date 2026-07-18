# アプリ本体の自動更新方式 調査メモ

[← 研究メモ目次](.)

> **採否**: Phase A（更新チェック＋通知）を採用し [#198](https://github.com/f8924919/yt-gui/issues/198)
> で実装（仕様: [spec/features/app-update.md](../spec/features/app-update.md)）。
> Phase B（実体の自動更新）は追加調査（2026-07-16、後述）の結果、**tufup では
> なく自前アップデータ（GitHub Releases ＋ Sigstore attestation 検証）を採用**し、
> 対象は Windows 先行・手動適用のみとする方針をユーザー確認のうえ決定した。
> 初回調査（2026-07-05）の方式比較・ホスティング課題・鍵管理の検討は
> 判断の経緯として下記に残す。

yt-dlp 更新（#119/#179）はアプリに同梱された yt-dlp の更新を扱うが、
**アプリ本体（yt-gui）の更新**は別問題である。本メモはアプリ本体の
自動更新（self-update）の実現方式を比較する。

---

## 前提（調査時点の配布形態）

- リポジトリは **public**（Release アセットの無認証ダウンロードが可能。
  private のままだとどの方式も成立しなかった）。
- 成果物は `yt-gui-{version}-windows-x64.zip` / `-macos-{arch}.zip` /
  `.AppImage` の**ポータブル配布**。インストーラなし・コード署名なし
  （[#39](https://github.com/f8924919/yt-gui/issues/39)）。
- PyInstaller **onedir**（`dist/yt-gui/`）ビルド。tufup / Velopack いずれも
  onedir が前提（onefile は不可）で、この点は適合する。
- リリースは `release.yml` により `v{version}` タグで自動発行され、
  provenance 署名（attestation）付き（[build.md](../build.md)）。

## 方式比較

| 観点 | tufup | Velopack | 自前アップデータ |
|---|---|---|---|
| a) ホスティング要件 | TUF メタデータ＋ターゲットを**安定したベース URL** で配信する必要あり（後述の最大課題） | GitHub Releases を**そのまま更新ソースにできる**（GithubSource） | GitHub Releases の既存 zip をそのまま利用 |
| b) 鍵管理・署名 | TUF ロール鍵（root はオフライン保管、targets/snapshot/timestamp は CI Secrets）。鍵ローテーション・失効の設計が必要 | 不要（HTTPS ＋パッケージチェックサム） | 不要（`SHA256SUMS` をリリースアセットに追加して照合） |
| c) 対応プラットフォーム | Windows / macOS（フォルダ差し替え型）。**AppImage は単一ファイルのため対象外** | Windows / macOS / Linux。ただし macOS は署名・公証なしだと体験が不安定 | zip 展開＋差し替えを自前実装する範囲で Win/mac。AppImage は単純なファイル置換で対応可能 |
| d) 実装・運用コスト | 中〜高: CI に tufup リポジトリツール（tar.gz ターゲット＋メタデータ生成・署名）を追加。既存 zip とは**共存可能**（tufup 用 tar.gz を追加生成すればよく、zip の置き換えは不要） | 高: 配布形態が**インストーラ型へ全面移行**（Windows は Setup.exe → `%LocalAppData%`）。CI に .NET ツール（`vpk`）依存追加。Python バインディングあり | 中: 取得・sha256 照合は Phase B(#179) と同じ道具立て（stdlib `urllib`）だが、**実行中 exe の差し替え**（Windows のファイルロック、旧フォルダ rename→新配置、中断時ロールバック）の堅牢化を自前で負う |
| e) 既知のリスク | CI 鍵の漏えいで TUF の防御が減衰（それでも素の HTTPS 取得より強い）。python-tuf 依存の追加 | ポータブル配布の放棄はユーザー影響が大きい。未署名 macOS の更新フローが未検証 | 「TUF なしの tufup 再発明」になりがち。セキュリティは HTTPS＋同一オリジン sha256（転送路の完全性のみ。リポジトリ/CI 侵害には無力） |
| 差分更新 | あり（bsdiff パッチ） | あり（delta パッケージ） | なし（フル zip、1 リリース数百 MB） |

## tufup のホスティング課題（Phase B の先決事項）

課題の本質は「リリースが zip か tar.gz か」ではなく**安定 URL でのホスティング**。

- TUF クライアントはメタデータ・ターゲットの固定ベース URL を要求するが、
  GitHub Release のアセット URL はタグごとに変わる。
- 候補 1: **GitHub Pages** でメタデータを配信。ただし Pages はサイト容量
  約 1GB 制限があり、1 リリース 3 OS 分で数百 MB のフルアーカイブは置けない
  （メタデータのみ Pages、ターゲットは別解が必要）。
- 候補 2: **固定タグのローリングリリース**（例 `updates` タグ）にメタデータと
  ターゲットを集約し、`releases/download/updates/` を固定ベース URL にする。
  動作はするが、リリースのアセットを更新し続ける変則運用になる。
- 鍵管理: root 鍵のオフライン保管手順、CI Secrets に置くオンライン鍵の
  ローテーション方針を決めてから実装 Issue 化する。

## 推奨案（初回調査時点の結論・2026-07-05）

> **注**: 下記 2. の「tufup 第一候補」は追加調査（次節）で覆した。
> 現在の結論は「追加調査と方式決定」を参照。

1. **Phase A（更新チェック＋通知）を先行** — 実施済み（#198）。低コストで
   「新版に気づけない」問題を解消する。
2. ~~**Phase B は tufup を第一候補**とする~~ → 追加調査で棄却（次節）。
3. **Velopack は配布形態を替える判断をしたときに再評価**する。コード署名
   （#39）に取り組むタイミングが再評価の適期。
4. **Linux（AppImage）は当面 Phase A（通知のみ）**に留める。実体更新が
   必要になったら AppImageUpdate（zsync）を別途検討する。

---

## 追加調査と方式決定（2026-07-16）

tufup 前提で先決事項（ホスティング・鍵管理）を固める調査を実施したところ、
tufup フル運用の負担が個人 OSS には過剰であること、および既存 CI の
provenance attestation を活かした自前方式が成立することが判明した。
以下の事実に基づき、**方式・対象 OS・適用フローをユーザー確認のうえ決定**した。

### tufup を棄却した根拠（追加調査で判明した事実）

- **メタデータ失効の運用リスク**: tufup 既定の expiry は
  root=365 / targets=7 / snapshot=7 / **timestamp=1 日**。python-tuf は期限切れ
  メタデータを拒否するため、expiry を緩めても **cron 定期再署名 workflow の
  常時運用が必須**になり、これが止まると全ユーザーの更新チェックが失効する
  （リリース停滞期でも止められない）。root も年 1 回の再署名を忘れると全滅。
- **鍵管理の負担**: root 鍵のオフライン保管（閾値署名・パスフレーズ暗号化・
  複数バックアップ）＋ online 鍵（timestamp 等）の CI Secrets 運用・
  ローテーションが必要。tufup 自体は鍵運用・アップロードの指針もツールも
  持たず（「実装依存」）、CI 自動化の公式サンプルも無い。
- **macOS 非対応が実質確定**: tufup の install は
  `shutil.copytree(symlinks=False)` 既定で、`.app` 内 framework の
  シンボリックリンクを実体展開しバンドル構造を破壊しうる。再署名・
  quarantine 対応も無く、未署名 `.app` での実績は確認できなかった
  （install の自作が必要）。
- **中断時ロールバックなし**: Windows の差し替え（終了後に `.bat` +
  robocopy `/purge`）にトランザクション性は無い。
- **プロジェクト健全性**: 0.x・単一メンテナ・最終正式リリース 2024-10
  （master への commit は 2025 も継続）。採用するならバージョン固定＋
  更新サイクルの自前 E2E テストが前提になる。
- ホスティング自体は成立可能と確認（metadata / targets は別 URL 指定可。
  metadata=Pages（メタデータのみなら 1GB/100GB soft limit に対し余裕）、
  targets=固定タグのローリングリリース（`gh release upload --clobber`、
  AppImage の `continuous` 等で実績あり。ただし **Immutable Releases を
  有効化しない**こと・CDN キャッシュの数分遅延に留意）。棄却理由は
  ホスティングではなく上記の鍵・失効運用の重さ。

### 採用方式: 自前アップデータ（GitHub Releases ＋ Sigstore attestation 検証）

初回調査で自前方式の弱点とした「HTTPS＋sha256 は転送路の完全性のみ」は、
**GitHub artifact attestation のアプリ内検証**で解消できることが分かった。

- 本リポジトリは既に `release.yml` で配布成果物（zip / AppImage）へ
  Sigstore provenance attestation を付与済み（[build.md](../build.md)）。
  **CI 側の追加変更は不要**。
- attestation は GitHub API
  （`/repos/{owner}/{repo}/attestations/sha256:{digest}`、public repo は
  無認証で取得可）でバンドルを取得し、**sigstore-python の `Verifier` +
  `policy.Identity`** でアプリ内から programmatic に検証できる
  （certificate identity = 本リポジトリの `release.yml`、
  issuer = `https://token.actions.githubusercontent.com` を固定）。
- セキュリティ上 TUF に劣るのはロールバック / freeze 防御の厳密さのみ。
  ロールバックは**バージョン単調性チェック**（現行より新しい版のみ適用。
  Phase A の `compare_versions` を流用）で実用上カバーする。freeze
  （更新を隠される）は通知機能の性質上、実害が限定的なため許容する。
- 鍵運用ゼロ（Sigstore は keyless / OIDC）で、ホスティング課題そのものが
  消滅する（通常リリースをそのまま更新ソースに使う。Phase A の照会先
  GitHub Releases API とも一本化されたまま）。
- ただし sigstore-python は**内部で TUF を使いトラストルートを管理**する
  ため「失効リスクが完全にゼロ」ではない（design-review 指摘）。トラスト
  ルートは年数回ローテーションするため完全静的同梱のみに依存すると将来の
  attestation が検証不能になりうる（sigstore-python 追加調査・2026-07-16）。
  そこで**通常はオンライン TUF 更新（`Verifier.production()`。実体更新は
  どのみちオンライン時にしか行えない）**とする。PoC（#252・2026-07-16）で
  同梱トラストルート＋`offline=True` でも検証が成立することを確認済み
  （TUF キャッシュなしの新規マシン相当で成功。`collect_all('sigstore')` が
  埋め込みトラストルートを同梱するため）で、オフラインフォールバックの
  実装は不要と判断した。検証不能時は手動ダウンロードへ誘導し
  「self-update 自体が壊れる」自己矛盾を避ける。
- トレードオフ: 差分更新なし（毎回フル zip 数百 MB）。更新頻度・
  ユーザー規模的に許容し、帯域が問題化したら差分方式を再検討する。

### 決定事項（2026-07-16・ユーザー確認済み）

| 論点 | 決定 |
|---|---|
| 方式 | 自前アップデータ（Releases フル zip ＋ sigstore-python で attestation 検証 ＋ バージョン単調性チェック） |
| 対象 OS | **Windows のみ先行**。macOS / Linux は Phase A（通知のみ）を継続し、macOS の実体更新はコード署名（#39）後に再検討 |
| 適用トリガー | **手動適用のみ**。新版通知ダイアログに「更新して再起動」を追加し、押下時のみダウンロード（進捗表示）→ 検証 → 終了時差し替え → 再起動。自動ダウンロードはしない（新設定も追加しない） |
| 差し替え方式 | tufup と同型の「終了後スクリプト」方式（アプリ終了 → バッチが旧フォルダを退避 rename → 新フォルダ配置 → 新 exe 起動。失敗時は退避フォルダを書き戻すロールバック付き。詳細設計は実装 Issue で確定） |
| CI | `release.yml` は変更不要（attestation 付与済み）。ただし `yt-gui.spec` は sigstore のトラストルート data files / hiddenimports の同梱変更が必要な見込み |
| 依存追加 | `sigstore`（sigstore-python）。**バージョン固定**とし、バンドルサイズ・依存ツリーへの影響は PoC で実測 |
| Issue 分割 | **2 分割**。Phase B-1: 非破壊のコア（DL＋attestation 検証＋sigstore 同梱 PoC）→ Phase B-2: Windows 差し替え＋UI。sigstore の PyInstaller 同梱可否が方式の成否を左右するため PoC を先行させる |

### 設計詳細（design-review 反映・2026-07-16）

design-review（[git-workflow.md](../git-workflow.md) §5.5 発火: 新モジュール・
複数モジュール横断・方式候補複数）の指摘を取り込んだ設計上の不変条件・
方針。実装 Issue の前提とする。

**検証モデル（fail-closed）**

- 検証が通るまで一切 実行/展開/差し替えしない。検証失敗・attestation 取得
  失敗はすべて「更新失敗」に落とし、手動ダウンロード（リリースページ）へ誘導。
- 検証は必ず**ダウンロードした実バイト**に対して行う: DL した zip の
  sha256 を算出 → その digest で attestations API を照会（複数返り得る。
  当初は `attestations[].bundle` にバンドル JSON が埋め込みだったが、
  2026-07 の API 破壊的変更で `bundle_url` 参照へ移行。後述の
  「GitHub attestations API の破壊的変更（2026-07-18）」参照）→
  **`Verifier.verify_dsse(bundle, policy)`** で署名・証明書チェーン・
  透明性ログを検証する（attest-build-provenance は DSSE / in-toto 形式の
  ため。`verify_artifact` は hashedrekord 用で使えない。
  sigstore-python 追加調査・2026-07-16）。
- **`verify_dsse` は subject digest とアセットの照合を行わない**ため、
  返却された in-toto Statement の `subject[].digest.sha256` と自算出
  digest の一致確認を必ず自前で行う。複数 attestation は 1 件ずつ検証し、
  ポリシー通過＋digest 一致が 1 件あれば成功とする（「digest で照会して
  存在したら OK」という循環を禁止）。
- `policy.Identity` は本リポジトリの `release.yml` の証明書 identity
  （workflow パス）＋ issuer `https://token.actions.githubusercontent.com`
  を厳格にピンする。**ref 成分は確定済み（2026-07-16・#252 PoC で実
  attestation を確認）**: 本リポジトリの `release.yml` は main への push で
  起動しタグを同一実行内で作成するため、証明書 SAN の ref は**タグ ref では
  なく `refs/heads/main`** になる。よって
  `https://github.com/f8924919/yt-gui/.github/workflows/release.yml@refs/heads/main`
  の固定文字列に**完全一致**でピンする。この identity を得られるのは本
  リポジトリの main push で走る release.yml のみでピン強度は同等であり、
  バージョンとの紐付けは subject digest 照合＋単調性チェックが担う。
- zip の展開は検証直後に**アプリ内（同一プロセス）**で行い、差し替え
  スクリプトには「配置済みフォルダの rename」だけをさせる（TOCTOU 回避）。

**Windows 差し替え（Phase B-2）**

- 新バージョンは**インストール先と同じ親ディレクトリ**にステージングする
  （同一ボリュームの rename を保証。別ドライブの %TEMP% だと rename が
  非原子的な copy+delete になるため）。
- 手順: アプリ終了 → スクリプトが旧プロセス PID の消滅を待つ →
  旧フォルダを `.bak` へ rename → 新フォルダを rename で配置 → 新 exe 起動。
  途中失敗時は `.bak` を書き戻すロールバック。rename は AV / OneDrive の
  一時ロックを想定し指数バックオフでリトライ。
- スクリプトは対象ツリー外の中立な場所へコピーして実行し、末尾で自己削除。
- `.bak` は 1 世代残し、次回の正常起動時に削除する（「正常起動」は
  メインウィンドウ表示後と定義。2026-07-17 の B-2 設計で確定、正本は
  [spec/features/app-update.md](../spec/features/app-update.md) Phase B 節）。
- **事前プリフライト**でインストール先の書き込み可否を判定し、不可
  （Program Files 配置等）なら「更新して再起動」を出さず従来の
  「リリースページを開く」のみ表示（UAC 昇格は持ち込まない。ユーザー確認済み）。
- **ダウンロードキュー実行中は「更新して再起動」を無効化**する
  （yt-dlp / ffmpeg がインストール先の exe をロックしているため。
  ユーザー確認済み）。

**アーキテクチャ**

- 新モジュールは `app_update.py`（チェック専用・軽依存）とは**分離**して
  新設する（例 `yt_gui/self_update.py`）。sigstore の import は遅延させ、
  起動速度と Phase A 経路へ波及させない。
- 数百 MB のダウンロードには進捗シグナル付きの専用ワーカー＋キャンセル機構
  が必要（既存 `run_in_thread` は進捗を持たない。中断は QueueController の
  中断フラグ方式に倣う）。

**PoC（Phase B-1）で確認する事項**

- sigstore-python の PyInstaller 同梱可否（data files / hiddenimports /
  copy_metadata）とバンドルサイズ増の実測。
- 同梱トラストルートによる完全オフライン検証（Rekor 非接続）の成立可否。
- 実リリースアセットに対する検証の E2E 成立。

実装 Issue は
[#252](https://github.com/f8924919/yt-gui/issues/252)（Phase B-1: コア・PoC）/
[#253](https://github.com/f8924919/yt-gui/issues/253)（Phase B-2: Windows
差し替え・UI）として起票済み（調査タスクの経緯は
[task/archive/app-update-phase-b.md](../task/archive/app-update-phase-b.md)）。
spec への Phase B 節追加・arch 新設は実装タスク側の docs 先行で行う。

## GitHub attestations API の破壊的変更（2026-07-18）

v0.6.1 リリース直後の実地 E2E（0.6.0 → 0.6.1）で attestation 検証が
`VERIFICATION_FAILED` となり、自己更新の不能を確認した（Issue
[#262](https://github.com/f8924919/yt-gui/issues/262)）。

- GitHub REST API の破壊的変更（[API version 2026-03-10](https://docs.github.com/en/rest/about-the-rest-api/breaking-changes?apiVersion=2026-03-10)）
  により、attestation 照会レスポンスの `attestations[].bundle` 埋め込みが
  廃止され、`attestations[].bundle_url`（Azure blob URL）参照へ移行した。
- 実測（2026-07-18）: `bundle` は null。`bundle_url` は無認証 GET 可・
  `Content-Type: application/x-snappy`・**raw snappy block format**（framing
  なし）で圧縮されたバンドル JSON（約 11 KB）。`X-GitHub-Api-Version:
  2022-11-28` を指定しても旧動作には戻らない（バージョン指定での回避不可）。
- #253 の E2E（2026-07-17・実 API）は成功していたため、デフォルト挙動の
  切り替えはその直後に行われた。**過去リリース（v0.6.0 等）の attestation も
  同形式で返るため、既存インストールは修正版を一度手動導入するまで自己更新
  不能**。
- 対応方針（#262）: `bundle` 埋め込みがあれば従来どおり、null なら
  `bundle_url` を GET → 純 Python の snappy デコーダ（展開のみ・依存追加
  なし・非圧縮長 10 MB 上限）で展開 → 従来の検証へ。設計の正本は
  `arch/self_update.md` の検証モデルだった（#276 の Phase B 撤去に伴い削除済み。
  内容は git 履歴を参照）。

## Phase B の撤去（2026-07-18・#276）

Phase B（実体の自動更新）は #252/#253 で実装・リリース（v0.6.0〜）したが、
短期間に次の問題が連続し、一般ユーザー環境で安定稼働に至らなかった:

1. **GitHub attestations API の破壊的変更**（#262）: `bundle` 埋め込み廃止 →
   `bundle_url` + snappy 化。クライアント側修正（v0.6.2）を要した。
2. **Qt シグナルによる適用のサイレント放棄**（#268）: `QProgressDialog.close()`
   の `canceled` 発火。ヘッドレス E2E では検出できず、実 GUI 検証で発覚
   （修正 v0.6.4）。
3. **python-tuf の Windows symlink 特権問題**（#275）: 通常権限では
   `Verifier.production()` の TUF 更新が `WinError 1314` で必ず失敗。開発
   環境（昇格済みセッション）の E2E では検出不能だった。
4. 管理者権限での実行時にも差し替え失敗（ロールバック動作）を観測。

いずれもクライアント側の修正を要する＝**既存インストールは修正版を手動導入
するまで自己更新できない**構造で、「更新の手間を減らす」という機能価値が
成立しない。運用コスト（外部 API・sigstore/TUF・Windows 権限モデル・Qt の
細部への追従）に見合わないため、**Phase B を撤去し Phase A（通知＋リリース
ページ誘導）のみへ戻す**ことをユーザーが決定した（#276）。

本ドキュメントの方式調査・設計記録、および `docs/task/archive/`（#252/#253/
#262/#268）の実装記録は、将来の再検討（例: パッケージマネージャ経由の配布、
winget / Scoop 等）の材料として保持する。

## 参考リンク

- [tufup](https://github.com/dennisvang/tufup) / [tufup-example](https://github.com/dennisvang/tufup-example)（PyUpdater 後継、python-tuf ベース）
- [Velopack](https://velopack.io/) / [Python Getting Started](https://docs.velopack.io/getting-started/python)
- [PyUpdater](https://github.com/Digital-Sapphire/PyUpdater)（アーカイブ済み・不採用）
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations) / [attestations API](https://docs.github.com/en/rest/repos/repos#list-attestations)
- [sigstore-python](https://github.com/sigstore/sigstore-python)（`Verifier` / `policy.Identity` によるバンドル検証）
- [TUF FAQ（鍵の online/offline 分離・expiry 指針）](https://theupdateframework.io/docs/faq/)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) / [About releases（2 GiB/file・帯域上限なし）](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
