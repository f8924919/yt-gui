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
  ため「失効リスクが完全にゼロ」ではない（design-review 指摘）。同梱
  トラストルートによるオフライン検証を既定とし、検証不能時は手動
  ダウンロードへ誘導することで「self-update 自体が壊れる」自己矛盾を
  避ける。オフライン検証の成立可否は PoC（Phase B-1）で確認する。
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
  sha256 を算出 → その digest で attestations API を照会 →
  `Verifier.verify_artifact()` に**実バイト**を渡して sigstore 側に
  再計算・照合させる（「digest で照会して存在したら OK」という循環を禁止）。
- `policy.Identity` は本リポジトリの `release.yml` の証明書 identity
  （workflow パス）＋ issuer `https://token.actions.githubusercontent.com`
  を厳格にピンする。ref 成分の扱い（タグ ref を許容する範囲）は
  Phase B-1 実装時に確定する。
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
- `.bak` は 1 世代残し、次回の正常起動時に削除する。
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

## 参考リンク

- [tufup](https://github.com/dennisvang/tufup) / [tufup-example](https://github.com/dennisvang/tufup-example)（PyUpdater 後継、python-tuf ベース）
- [Velopack](https://velopack.io/) / [Python Getting Started](https://docs.velopack.io/getting-started/python)
- [PyUpdater](https://github.com/Digital-Sapphire/PyUpdater)（アーカイブ済み・不採用）
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations) / [attestations API](https://docs.github.com/en/rest/repos/repos#list-attestations)
- [sigstore-python](https://github.com/sigstore/sigstore-python)（`Verifier` / `policy.Identity` によるバンドル検証）
- [TUF FAQ（鍵の online/offline 分離・expiry 指針）](https://theupdateframework.io/docs/faq/)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) / [About releases（2 GiB/file・帯域上限なし）](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
