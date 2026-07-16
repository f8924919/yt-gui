# 研究・設計メモ目次

実装前の調査・選定・設計メモを置きます。採否が確定し実装に入った内容は `docs/spec/` / `docs/arch/` /
`docs/build.md` 等の正式版へ転記し、本フォルダには設計経緯の記録として残します。

| メモ | 内容 |
|---|---|
| [gallery-dl 統合機能 設計書](gallery-dl-integration.md) | gallery-dl 連携の設計検討 |
| [複数音声トラックのダウンロード機能 踏査メモ](multi-audio-download.md) | 多言語・複数音声トラック取得の実装案 |
| [プラグイン管理機能 踏査メモ](plugin-manager-research.md) | プラグイン管理機能の検討 |
| [Qt UI テストのサンドボックス内実行 可否調査](qt-ui-testing-feasibility.md) | サンドボックス環境での Qt UI テスト可否 |
| [リファクタリング候補の調査メモ](refactoring-analysis.md) | リファクタリング候補の洗い出し |
| [同梱バイナリのサプライチェーン対策と更新運用 設計メモ](binary-supply-chain.md) | バイナリのピン留め・ハッシュ検証・更新運用方針 |
| [リポジトリ public 化と実メール露出 調査レポート](repo-public-email.md) | コミット履歴の実メール露出調査・履歴書き換えのリスク・実行計画草案 |
| [yt-dlp CLI 機能ギャップ調査メモ](yt-dlp-feature-gap.md) | CLI にあって UI から使えない機能の洗い出しと追加候補の優先度 |
| [ライブ配信を最初から / 配信待ち 機能 調査メモ](live-stream-download.md) | `--live-from-start` / `--wait-for-video` 対応の仕様案と実装課題 |
| [アプリ本体の自動更新方式 調査メモ](app-update.md) | tufup / Velopack / 自前アップデータの比較と Phase B 方式決定の経緯（tufup を棄却し「Releases ＋ Sigstore attestation 検証」の自前方式を採用。実装は #252 / #253） |
