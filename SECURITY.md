# セキュリティポリシー

## 脆弱性の報告

セキュリティ上の問題を見つけた場合は、**公開 Issue を作成せず**、GitHub の
[Private Vulnerability Reporting](https://github.com/f8924919/yt-gui/security/advisories/new)
から非公開で報告してください（リポジトリの **Security** タブ →「Report a vulnerability」）。

報告には、可能な範囲で以下を含めてください。

- 影響を受けるバージョン（リリースタグまたはコミット）
- 再現手順または PoC
- 想定される影響範囲

非公開報告を受領後、修正方針と公開時期について GitHub Security Advisory 上でやり取りします。

## 対象範囲

このアプリは yt-dlp・ffmpeg・deno などの外部バイナリを同梱して配布します
（[docs/build.md](docs/build.md) を参照）。同梱バイナリ自体の脆弱性は各上流プロジェクトへ報告してください。
本リポジトリでは、配布物の取得・検証・実行に関わる本アプリ側のコードを対象とします。

## サポート対象バージョン

最新リリースのみをサポート対象とします。脆弱性修正は最新リリース系列に対して提供します。
