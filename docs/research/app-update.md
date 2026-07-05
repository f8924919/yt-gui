# アプリ本体の自動更新方式 調査メモ

[← 研究メモ目次](.)

> **採否**: Phase A（更新チェック＋通知）を採用し [#198](https://github.com/f8924919/yt-gui/issues/198)
> で実装（仕様: [spec/features/app-update.md](../spec/features/app-update.md)）。
> Phase B（実体の自動更新）は**未決**。本メモは Phase B 着手時の判断材料として、
> 方式比較・ホスティング課題・鍵管理の検討を記録する（調査日: 2026-07-05）。

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

## 推奨案（結論）

1. **Phase A（更新チェック＋通知）を先行** — 実施済み（#198）。低コストで
   「新版に気づけない」問題を解消する。
2. **Phase B は tufup を第一候補**とする。ポータブル配布・既存 CI を維持でき、
   サプライチェーン方針（sha256 ピン・provenance）とも整合するため。
   ただし着手前に**ホスティング方式（Pages vs 固定タグ）と鍵管理の設計を
   先に固める調査タスク**を切ること。
3. **Velopack は配布形態を替える判断をしたときに再評価**する。コード署名
   （#39）に取り組むタイミングが再評価の適期。
4. **Linux（AppImage）は当面 Phase A（通知のみ）**に留める。実体更新が
   必要になったら AppImageUpdate（zsync）を別途検討する。

## 参考リンク

- [tufup](https://github.com/dennisvang/tufup) / [tufup-example](https://github.com/dennisvang/tufup-example)（PyUpdater 後継、python-tuf ベース）
- [Velopack](https://velopack.io/) / [Python Getting Started](https://docs.velopack.io/getting-started/python)
- [PyUpdater](https://github.com/Digital-Sapphire/PyUpdater)（アーカイブ済み・不採用）
